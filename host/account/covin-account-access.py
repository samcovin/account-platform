#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Suspend or resume one account without deleting account data."""

import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid


DOMAIN = 'example.test'
NEXTCLOUD_CONTAINER = 'nextcloud-app'
MAILCOW_DIR = Path('/opt/mailcow-dockerized')
MAILCOW_HOST = 'box.example.test'
AUTHENTIK_DIR = Path('/opt/authentik')
DOVECOT_CONTAINER = 'mailcowdockerized-dovecot-mailcow-1'
MAILCOW_PHP_SERVICE = 'php-fpm-mailcow'
MAILCOW_ACCESS_FIELDS = (
    'sogo_access',
    'imap_access',
    'pop3_access',
    'smtp_access',
    'sieve_access',
)
RECEIPT_ROOT = Path('/opt/covin-account-access')
LOCK_FILE = Path('/run/lock/covin-account-access.lock')
USERNAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$')
OPERATOR_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._@-]{0,126}[A-Za-z0-9]$')
PROTECTED_USERNAMES = {
    'admin',
    'administrator',
    'akadmin',
    'covin-export-delivery',
    'root',
}


class AccessError(RuntimeError):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def iso_now():
    return utc_now().isoformat()


def parse_json_output(value, label):
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise AccessError(f'{label} returned invalid JSON') from error


def boolean(value):
    if value in (True, 1, '1', 'true', 'True', 'yes', 'y'):
        return True
    if value in (False, 0, '0', 'false', 'False', 'no', 'n'):
        return False
    raise AccessError(f'cannot interpret boolean value: {value!r}')


class Runner:
    def completed(self, arguments, *, cwd=None, env=None, input_text=None):
        return subprocess.run(
            arguments,
            cwd=cwd,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def run(self, arguments, *, cwd=None, env=None, input_text=None):
        result = self.completed(
            arguments, cwd=cwd, env=env, input_text=input_text)
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or 'no output'
            raise AccessError(
                f'command failed with status {result.returncode}: {message}')
        return result.stdout


class ProductionBackend:
    def __init__(self, runner=None):
        self.runner = runner or Runner()

    def occ(self, *arguments):
        return self.runner.run([
            'docker', 'exec', '-u', 'www-data', NEXTCLOUD_CONTAINER,
            'php', 'occ', *arguments, '--no-ansi', '--no-interaction',
            '--no-warnings',
        ])

    def nextcloud_info(self, username):
        output = self.occ('user:info', username, '--output=json')
        data = parse_json_output(output, 'Nextcloud user lookup')
        if not isinstance(data, dict) or data.get('user_id') != username:
            raise AccessError('Nextcloud did not return the exact requested account')
        return {'enabled': boolean(data.get('enabled'))}

    def nextcloud_tokens(self, username):
        output = self.occ('user:auth-tokens:list', username, '--output=json')
        data = parse_json_output(output, 'Nextcloud token listing')
        if isinstance(data, dict):
            if data == {}:
                data = []
            elif isinstance(data.get('tokens'), list):
                data = data['tokens']
            elif isinstance(data.get('data'), list):
                data = data['data']
            else:
                raise AccessError(
                    'Nextcloud token listing has an unexpected object structure')
        if not isinstance(data, list):
            raise AccessError('Nextcloud token listing has an unexpected structure')
        tokens = []
        for item in data:
            if not isinstance(item, dict) or 'id' not in item:
                raise AccessError('Nextcloud token entry has an unexpected structure')
            token_id = str(item['id'])
            if not token_id.isdigit():
                raise AccessError('Nextcloud returned an invalid token ID')
            tokens.append(token_id)
        if len(tokens) != len(set(tokens)):
            raise AccessError('Nextcloud returned duplicate token IDs')
        return tokens

    def set_nextcloud_enabled(self, username, enabled):
        command = 'user:enable' if enabled else 'user:disable'
        self.occ(command, username)

    def delete_nextcloud_tokens(self, username, token_ids):
        for token_id in token_ids:
            self.occ('user:auth-tokens:delete', username, token_id)

    def authentik(self, username, program, extra_env=None):
        environment = os.environ.copy()
        environment['COVIN_ACCESS_USERNAME'] = username
        if extra_env:
            environment.update(extra_env)
        exposed = ['-e', 'COVIN_ACCESS_USERNAME']
        for name in sorted(extra_env or {}):
            exposed.extend(['-e', name])
        output = self.runner.run([
            'docker', 'compose', 'exec', '-T',
            *exposed,
            'server', 'ak', 'shell', '-c', program,
        ], cwd=AUTHENTIK_DIR, env=environment)
        markers = [line.removeprefix('COVIN_JSON=') for line in output.splitlines()
                   if line.startswith('COVIN_JSON=')]
        if len(markers) != 1:
            raise AccessError('Authentik command returned no unique result marker')
        return parse_json_output(markers[0], 'Authentik command')

    def authentik_info(self, username):
        return self.authentik(username, r'''
import json
import os
from authentik.core.models import AuthenticatedSession, User

username = os.environ["COVIN_ACCESS_USERNAME"]
users = User.objects.filter(username=username)
if users.count() != 1:
    result = {"count": users.count()}
else:
    user = users.get()
    result = {
        "count": 1,
        "active": bool(user.is_active),
        "sessions": AuthenticatedSession.objects.filter(user=user).count(),
    }
print("COVIN_JSON=" + json.dumps(result, separators=(",", ":")))
''')

    def set_authentik_active(self, username, active):
        program = r'''
import json
import os
from authentik.core.models import User

username = os.environ["COVIN_ACCESS_USERNAME"]
active = os.environ["COVIN_ACCESS_ACTIVE"] == "1"
user = User.objects.get(username=username)
user.is_active = active
user.save(update_fields=["is_active"])
print("COVIN_JSON=" + json.dumps({"active": bool(user.is_active)}, separators=(",", ":")))
'''
        result = self.authentik(
            username, program,
            {'COVIN_ACCESS_ACTIVE': '1' if active else '0'})
        if result != {'active': active}:
            raise AccessError('Authentik did not confirm the requested active state')

    def delete_authentik_sessions(self, username):
        result = self.authentik(username, r'''
import json
import os
from authentik.core.models import AuthenticatedSession, User

username = os.environ["COVIN_ACCESS_USERNAME"]
user = User.objects.get(username=username)
query = AuthenticatedSession.objects.filter(user=user)
count = query.count()
query.delete()
remaining = AuthenticatedSession.objects.filter(user=user).count()
print("COVIN_JSON=" + json.dumps({"deleted": count, "remaining": remaining}, separators=(",", ":")))
''')
        if result.get('remaining') != 0:
            raise AccessError('Authentik sessions remain after revocation')
        return int(result.get('deleted', 0))

    def mailcow_request(self, method, path, payload=None):
        script = r'''
set -Eeuo pipefail
cd "$COVIN_MAILCOW_DIR"
. ./mailcow.conf
MAILCOW_HOST_VALUE=${MAILCOW_HOST:-${MAILCOW_HOSTNAME:-$COVIN_MAILCOW_HOST}}
: "${API_KEY:?Mailcow API key is unavailable}"
: "${MAILCOW_HOST_VALUE:?Mailcow hostname is unavailable}"
{
  printf 'silent\n'
  printf 'show-error\n'
  printf 'fail\n'
  printf 'header = "X-API-Key: %s"\n' "$API_KEY"
  printf 'resolve = "%s:443:127.0.0.1"\n' "$MAILCOW_HOST_VALUE"
} | {
  if [[ -n ${COVIN_PAYLOAD_FILE:-} ]]; then
    curl --config - --request "$COVIN_METHOD" \
      --header 'Content-Type: application/json' \
      --data-binary "@$COVIN_PAYLOAD_FILE" \
      "https://${MAILCOW_HOST_VALUE}${COVIN_PATH}"
  else
    curl --config - --request "$COVIN_METHOD" \
      "https://${MAILCOW_HOST_VALUE}${COVIN_PATH}"
  fi
}
'''
        environment = os.environ.copy()
        environment.update({
            'COVIN_MAILCOW_DIR': str(MAILCOW_DIR),
            'COVIN_MAILCOW_HOST': MAILCOW_HOST,
            'COVIN_METHOD': method,
            'COVIN_PATH': path,
        })
        temporary = None
        try:
            if payload is not None:
                temporary = tempfile.NamedTemporaryFile(
                    mode='w', encoding='utf-8', delete=False,
                    prefix='covin-account-access.', suffix='.json')
                json.dump(payload, temporary, separators=(',', ':'))
                temporary.write('\n')
                temporary.close()
                os.chmod(temporary.name, 0o600)
                environment['COVIN_PAYLOAD_FILE'] = temporary.name
            output = self.runner.run(['bash', '-c', script], env=environment)
            return parse_json_output(output, 'Mailcow API')
        finally:
            if temporary is not None:
                Path(temporary.name).unlink(missing_ok=True)

    def mailcow_info(self, mailbox):
        data = self.mailcow_request('GET', '/api/v1/get/mailbox/all')
        if not isinstance(data, list):
            raise AccessError('Mailcow mailbox listing has an unexpected structure')
        matches = [item for item in data if isinstance(item, dict)
                   and item.get('username') == mailbox]
        if len(matches) != 1:
            raise AccessError('Mailcow did not return exactly one requested mailbox')
        attributes = matches[0].get('attributes')
        if not isinstance(attributes, dict):
            raise AccessError('Mailcow mailbox attributes have an unexpected structure')
        access = {}
        for field in MAILCOW_ACCESS_FIELDS:
            if field not in attributes:
                raise AccessError(f'Mailcow mailbox is missing {field}')
            access[field] = boolean(attributes[field])
        return {
            'active': boolean(matches[0].get('active')),
            'access': access,
        }

    def set_mailcow_access(self, mailbox, access):
        access = validate_mailcow_access(access)
        protocols = ['0']
        for protocol in ('imap', 'pop3', 'smtp', 'sieve'):
            if access[f'{protocol}_access']:
                protocols.append(protocol)
        self.mailcow_request('POST', '/api/v1/edit/mailbox', {
            'items': [mailbox],
            'attr': {
                'active': '1',
                'sogo_access': '1' if access['sogo_access'] else '0',
                'protocol_access': protocols,
            },
        })
        current = self.mailcow_info(mailbox)
        if not current['active'] or current['access'] != access:
            raise AccessError('Mailcow did not confirm the requested access state')

    def mailcow_app_passwords(self, mailbox):
        data = self.mailcow_request(
            'GET', f'/api/v1/get/app-passwd/all/{mailbox}')
        if data == {}:
            return []
        if not isinstance(data, list):
            raise AccessError('Mailcow app-password listing has an unexpected structure')
        ids = []
        for item in data:
            if not isinstance(item, dict) or 'id' not in item:
                raise AccessError('Mailcow app-password entry has an unexpected structure')
            item_id = str(item['id'])
            if not item_id.isdigit():
                raise AccessError('Mailcow returned an invalid app-password ID')
            ids.append(int(item_id))
        if len(ids) != len(set(ids)):
            raise AccessError('Mailcow returned duplicate app-password IDs')
        return ids

    def delete_mailcow_app_passwords(self, mailbox, password_ids):
        if not password_ids:
            return
        self.mailcow_request(
            'POST', '/api/v1/delete/app-passwd', {'items': password_ids})
        remaining = set(self.mailcow_app_passwords(mailbox))
        if remaining.intersection(password_ids):
            raise AccessError('Mailcow app passwords remain after revocation')

    def mailcow_web_session_operation(self, mailbox, delete=False):
        environment = os.environ.copy()
        environment.update({
            'COVIN_ACCESS_MAILBOX': mailbox,
            'COVIN_ACCESS_DELETE': '1' if delete else '0',
        })
        program = r'''<?php
$target = getenv('COVIN_ACCESS_MAILBOX');
$delete = getenv('COVIN_ACCESS_DELETE') === '1';
$needle = 'mailcow_cc_username|s:' . strlen($target) . ':"' . $target . '";';

$redis = new Redis();
$redis->connect('redis', 6379);
$redis->auth(getenv('REDISPASS'));

function matching_sessions($redis, $needle) {
    $matches = [];
    $iterator = null;
    do {
        $keys = $redis->scan($iterator, 'PHPREDIS_SESSION:*', 500);
        if ($keys === false) {
            continue;
        }
        foreach ($keys as $key) {
            if ($redis->type($key) !== Redis::REDIS_STRING) {
                continue;
            }
            $value = $redis->get($key);
            if (is_string($value) && str_contains($value, $needle)) {
                $matches[$key] = true;
            }
        }
    } while ($iterator !== 0);
    return array_keys($matches);
}

$matches = matching_sessions($redis, $needle);
$deleted = 0;
if ($delete) {
    foreach ($matches as $key) {
        $deleted += $redis->del($key);
    }
}
$remaining = count(matching_sessions($redis, $needle));

echo 'COVIN_JSON=' . json_encode([
    'before' => count($matches),
    'deleted' => $deleted,
    'remaining' => $remaining,
], JSON_UNESCAPED_SLASHES) . PHP_EOL;
'''
        output = self.runner.run([
            'docker', 'compose', 'exec', '-T',
            '-e', 'COVIN_ACCESS_MAILBOX',
            '-e', 'COVIN_ACCESS_DELETE',
            MAILCOW_PHP_SERVICE, 'php',
        ], cwd=MAILCOW_DIR, env=environment, input_text=program)
        markers = [line.removeprefix('COVIN_JSON=') for line in output.splitlines()
                   if line.startswith('COVIN_JSON=')]
        if len(markers) != 1:
            raise AccessError(
                'Mailcow web-session command returned no unique result marker')
        result = parse_json_output(markers[0], 'Mailcow web-session command')
        if (not isinstance(result, dict)
                or set(result) != {'before', 'deleted', 'remaining'}
                or any(type(result[name]) is not int or result[name] < 0
                       for name in result)):
            raise AccessError(
                'Mailcow web-session command returned an unexpected structure')
        if delete:
            if result['deleted'] != result['before'] or result['remaining'] != 0:
                raise AccessError('Mailcow web sessions remain after revocation')
        elif result['deleted'] != 0 or result['remaining'] != result['before']:
            raise AccessError('Mailcow web-session inspection changed state')
        return result

    def mailcow_web_sessions(self, mailbox):
        return self.mailcow_web_session_operation(mailbox)['before']

    def delete_mailcow_web_sessions(self, mailbox):
        return self.mailcow_web_session_operation(mailbox, delete=True)['deleted']

    def kick_mailbox(self, mailbox):
        result = self.runner.completed([
            'docker', 'exec', DOVECOT_CONTAINER,
            'doveadm', 'kick', mailbox,
        ])
        if result.returncode == 0:
            return
        message = result.stderr.strip() or result.stdout.strip() or 'no output'
        if result.returncode == 68 and message == 'no users kicked':
            return
        raise AccessError(
            f'command failed with status {result.returncode}: {message}')


def validate_mailcow_access(value):
    if not isinstance(value, dict) or set(value) != set(MAILCOW_ACCESS_FIELDS):
        raise AccessError('Mailcow access state has an unexpected structure')
    return {field: boolean(value[field]) for field in MAILCOW_ACCESS_FIELDS}


def mailcow_access_from_state(state):
    return {
        field: state[f'mailcow_{field}']
        for field in MAILCOW_ACCESS_FIELDS
    }


def preflight(backend, username, mailbox):
    nextcloud = backend.nextcloud_info(username)
    tokens = backend.nextcloud_tokens(username)
    authentik = backend.authentik_info(username)
    if authentik.get('count') != 1:
        raise AccessError('Authentik did not return exactly one requested identity')
    mailcow = backend.mailcow_info(mailbox)
    if not mailcow['active']:
        raise AccessError(
            'Mailcow mailbox is inactive; stop for manual review so inbound mail is not changed')
    app_passwords = backend.mailcow_app_passwords(mailbox)
    web_sessions = backend.mailcow_web_sessions(mailbox)
    return {
        'nextcloud_enabled': nextcloud['enabled'],
        'nextcloud_tokens': len(tokens),
        'nextcloud_token_ids': tokens,
        'authentik_active': boolean(authentik.get('active')),
        'authentik_sessions': int(authentik.get('sessions', 0)),
        'mailcow_active': mailcow['active'],
        **{
            f'mailcow_{field}': enabled
            for field, enabled in mailcow['access'].items()
        },
        'mailcow_app_passwords': len(app_passwords),
        'mailcow_app_password_ids': app_passwords,
        'mailcow_web_sessions': web_sessions,
    }


def public_state(state):
    return {key: value for key, value in state.items()
            if not key.endswith('_ids')}


def require_private(path, directory=False):
    result = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(result.st_mode) or result.st_uid != 0:
        raise AccessError(f'unsafe protected path: {path}')
    if stat.S_IMODE(result.st_mode) & 0o077:
        raise AccessError(f'protected path is accessible outside root: {path}')


@contextmanager
def operation_lock(path=None):
    path = path or LOCK_FILE
    descriptor = os.open(
        path,
        os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        result = os.fstat(descriptor)
        if not stat.S_ISREG(result.st_mode) or result.st_uid != 0:
            raise AccessError('unsafe account-access lock file')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AccessError('another account access operation is running') from error
        yield
    finally:
        os.close(descriptor)


def atomic_write(path, data):
    if path.parent.exists() or path.parent.is_symlink():
        require_private(path.parent, directory=True)
    else:
        path.parent.mkdir(mode=0o700, parents=True)
        require_private(path.parent, directory=True)
    os.chmod(path.parent, 0o700)
    require_private(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        require_private(path)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def load_receipt(path, username, mailbox):
    if not path.exists():
        if path.is_symlink():
            raise AccessError('access receipt must not be a symlink')
        return {
            'version': 1,
            'username': username,
            'mailbox': mailbox,
            'state': 'unmanaged',
            'updated_at': None,
            'attempts': [],
        }
    require_private(path)
    data = parse_json_output(path.read_text(encoding='utf-8'), 'access receipt')
    if (not isinstance(data, dict) or data.get('version') != 1
            or data.get('username') != username or data.get('mailbox') != mailbox
            or not isinstance(data.get('attempts'), list)):
        raise AccessError('existing access receipt has an unexpected structure')
    return data


def validate_final(action, state, mailcow_restore=None):
    if action == 'suspend':
        if (state['nextcloud_enabled'] or state['nextcloud_tokens']
                or state['authentik_active'] or state['authentik_sessions']
                or state['mailcow_app_passwords'] or state['mailcow_web_sessions']
                or not state['mailcow_active']
                or any(mailcow_access_from_state(state).values())):
            raise AccessError('suspension verification did not reach the required state')
    else:
        if (not state['nextcloud_enabled'] or not state['authentik_active']
                or not state['mailcow_active']):
            raise AccessError('resume verification did not reach the required state')
        if mailcow_restore is None:
            raise AccessError('resume has no recorded Mailcow access state')
        if mailcow_access_from_state(state) != mailcow_restore:
            raise AccessError('resume did not restore the recorded Mailcow access state')


def commit_action(backend, action, username, mailbox, operator, reason,
                  receipt_root=None):
    receipt_root = receipt_root or RECEIPT_ROOT
    receipt_path = receipt_root / f'{username}.json'
    receipt = load_receipt(receipt_path, username, mailbox)
    previous_state = receipt['state']
    if action == 'resume' and receipt['state'] not in {
            'suspended', 'suspend-pending', 'resume-pending'}:
        raise AccessError(
            'resume requires a prior suspended or partially suspended receipt')
    if action == 'resume':
        if 'mailcow_restore' not in receipt:
            raise AccessError('resume requires recorded Mailcow access state')
        validate_mailcow_access(receipt['mailcow_restore'])
    attempt = {
        'id': uuid.uuid4().hex,
        'action': action,
        'operator': operator,
        'reason': reason,
        'started_at': iso_now(),
        'completed_at': None,
        'status': 'pending',
        'before': None,
        'after': None,
        'steps': [],
        'revoked_counts': {},
        'error': None,
    }
    receipt['state'] = f'{action}-pending'
    receipt['updated_at'] = iso_now()
    receipt['attempts'].append(attempt)
    atomic_write(receipt_path, receipt)

    try:
        before = preflight(backend, username, mailbox)
        attempt['before'] = public_state(before)
        if action == 'suspend':
            if (previous_state in {'suspend-pending', 'suspended'}
                    and 'mailcow_restore' in receipt):
                validate_mailcow_access(receipt['mailcow_restore'])
            else:
                receipt['mailcow_restore'] = mailcow_access_from_state(before)
        else:
            validate_mailcow_access(receipt['mailcow_restore'])
        atomic_write(receipt_path, receipt)

        if action == 'suspend':
            if before['authentik_active']:
                backend.set_authentik_active(username, False)
            attempt['steps'].append('authentik-disabled')
            atomic_write(receipt_path, receipt)

            if before['nextcloud_enabled']:
                backend.set_nextcloud_enabled(username, False)
            attempt['steps'].append('nextcloud-disabled')
            atomic_write(receipt_path, receipt)

            backend.set_mailcow_access(
                mailbox, {field: False for field in MAILCOW_ACCESS_FIELDS})
            attempt['steps'].append('mailcow-interactive-access-disabled')
            atomic_write(receipt_path, receipt)

            backend.delete_authentik_sessions(username)
            attempt['steps'].append('authentik-sessions-revoked')
            atomic_write(receipt_path, receipt)

            backend.delete_nextcloud_tokens(
                username, before['nextcloud_token_ids'])
            attempt['steps'].append('nextcloud-tokens-revoked')
            atomic_write(receipt_path, receipt)

            backend.delete_mailcow_app_passwords(
                mailbox, before['mailcow_app_password_ids'])
            attempt['steps'].append('mailcow-app-passwords-revoked')
            atomic_write(receipt_path, receipt)

            deleted_sessions = backend.delete_mailcow_web_sessions(mailbox)
            attempt['revoked_counts']['mailcow_web_sessions'] = deleted_sessions
            attempt['steps'].append('mailcow-web-sessions-revoked')
            atomic_write(receipt_path, receipt)

            backend.kick_mailbox(mailbox)
            attempt['steps'].append('dovecot-connections-kicked')
            atomic_write(receipt_path, receipt)
        else:
            if not before['nextcloud_enabled']:
                backend.set_nextcloud_enabled(username, True)
            attempt['steps'].append('nextcloud-enabled')
            atomic_write(receipt_path, receipt)

            if not before['authentik_active']:
                backend.set_authentik_active(username, True)
            attempt['steps'].append('authentik-enabled')
            atomic_write(receipt_path, receipt)

            backend.set_mailcow_access(
                mailbox, validate_mailcow_access(receipt['mailcow_restore']))
            attempt['steps'].append('mailcow-access-restored')
            atomic_write(receipt_path, receipt)

        after = preflight(backend, username, mailbox)
        validate_final(action, after, receipt.get('mailcow_restore'))
        attempt['after'] = public_state(after)
        attempt['status'] = 'complete'
        attempt['completed_at'] = iso_now()
        receipt['state'] = 'suspended' if action == 'suspend' else 'active'
        receipt['updated_at'] = iso_now()
        atomic_write(receipt_path, receipt)
        return public_state(after)
    except Exception as error:
        attempt['status'] = 'failed'
        attempt['error'] = str(error)[:1000]
        attempt['completed_at'] = iso_now()
        receipt['updated_at'] = iso_now()
        atomic_write(receipt_path, receipt)
        raise


def arguments(argv=None):
    parser = argparse.ArgumentParser(
        description='Suspend or resume an account without deleting data.')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--suspend', action='store_true')
    action.add_argument('--resume', action='store_true')
    parser.add_argument('--username', required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--commit', action='store_true',
                        help='Apply changes; without this option, only preflight runs.')
    parser.add_argument('--confirm', choices=('SUSPEND', 'RESUME'))
    return parser.parse_args(argv)


def main(argv=None, backend=None):
    args = arguments(argv)
    if os.geteuid() != 0:
        raise AccessError('run this command as root')

    username = args.username.lower()
    if args.username != username or not USERNAME_PATTERN.fullmatch(username):
        raise AccessError('username must be 2–64 lowercase account characters')
    if username in PROTECTED_USERNAMES:
        raise AccessError('refusing to manage a protected service or administrator account')
    if not OPERATOR_PATTERN.fullmatch(args.operator):
        raise AccessError('operator must be a 2–128 character identifier')
    reason = args.reason.strip()
    if not reason or len(reason) > 500 or '\n' in reason or '\r' in reason:
        raise AccessError('reason must be 1–500 characters on one line')

    action = 'suspend' if args.suspend else 'resume'
    expected = action.upper()
    if args.commit and args.confirm != expected:
        raise AccessError(f'commit mode requires --confirm {expected}')
    if not args.commit and args.confirm is not None:
        raise AccessError('--confirm is accepted only with --commit')

    mailbox = f'{username}@{DOMAIN}'
    if backend is None and os.environ.get('ACCOUNT_PLATFORM_RUNTIME_REVIEWED') != '1':
        raise AccessError('review service targets and policy before setting ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1')
    backend = backend or ProductionBackend()
    state = preflight(backend, username, mailbox)
    result = {
        'status': 'dry-run-valid',
        'action': action,
        'username': username,
        'mailbox': mailbox,
        'current': public_state(state),
        'data_deletion': False,
        'mailbox_delivery_preserved': True,
    }
    if args.commit:
        with operation_lock():
            result['current'] = commit_action(
                backend, action, username, mailbox, args.operator, reason)
        result['status'] = f'{action}-complete'
    print(json.dumps(result, separators=(',', ':'), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except AccessError as error:
        print(f'STOP: {error}', file=sys.stderr)
        raise SystemExit(1)
