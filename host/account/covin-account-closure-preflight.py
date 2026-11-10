#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Read-only closure inventory. No commit, deletion or authorization interface."""

import argparse
import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


USERNAME_PATTERN = r'^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$'
PROTECTED_USERNAMES = {
    'admin', 'administrator', 'akadmin', 'root', 'covin-export-delivery',
}
DOMAIN = 'example.test'
NOT_ASSESSED = [
    'fresh-final-export-and-recipient-validation',
    'independent-encrypted-recovery-and-tested-restore',
    'mailcow-aliases-delegation-and-remaining-service-data',
    'full-application-data-and-encryption-dependency-coverage',
    'approval-resend-freeze-and-username-reuse-policy',
    'separate-final-closure-authorization',
]


class PreflightError(RuntimeError):
    pass


def parse_json(text, label):
    try:
        return json.loads(text)
    except (ValueError, TypeError) as error:
        raise PreflightError(f'{label} returned invalid JSON') from error


def count(value, label):
    if type(value) is not int or value < 0:
        raise PreflightError(f'{label} is not a nonnegative integer')
    return value


def flag(value, label):
    if type(value) is not bool:
        raise PreflightError(f'{label} is not a boolean')
    return value


def unique_marker(output, label):
    lines = [line[len('COVIN_JSON='):] for line in output.splitlines()
             if line.startswith('COVIN_JSON=')]
    if len(lines) != 1:
        raise PreflightError(f'{label} returned no unique result marker')
    return parse_json(lines[0], label)


class SafeRunner:
    """Never echo subprocess output on failure: it may contain private data."""

    def run(self, arguments, *, cwd=None, env=None, input_text=None):
        try:
            result = subprocess.run(
                arguments, cwd=cwd, env=env, input=input_text,
                text=True, capture_output=True, timeout=90, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PreflightError('read-only service command unavailable or timed out') from error
        if result.returncode:
            raise PreflightError(
                f'read-only service command failed (status {result.returncode})')
        return result.stdout


def load_access_module(path):
    loader = importlib.machinery.SourceFileLoader('covin_readonly_access', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def readonly_access_backend(module, runner):
    class ReadOnlyAccess(module.ProductionBackend):
        def deny(self, *args, **kwargs):
            raise PreflightError('mutation is forbidden in closure preflight')

        set_nextcloud_enabled = deny
        delete_nextcloud_tokens = deny
        set_authentik_active = deny
        delete_authentik_sessions = deny
        set_mailcow_access = deny
        delete_mailcow_app_passwords = deny
        delete_mailcow_web_sessions = deny
        kick_mailbox = deny

        def mailcow_request(self, method, path, payload=None):
            if method != 'GET' or payload is not None:
                self.deny()
            return super().mailcow_request(method, path)

        def mailcow_web_session_operation(self, mailbox, delete=False):
            if delete:
                self.deny()
            return super().mailcow_web_session_operation(mailbox, delete=False)

    return ReadOnlyAccess(runner=runner)


class ProductionBackend:
    def __init__(self, runner=None, access_path=None, helper_path=None):
        directory = Path(__file__).resolve().parent
        if access_path is None:
            access_path = directory / (
                'covin-account-access.py' if directory.name == 'account'
                else 'covin-account-access')
        self.access = load_access_module(access_path)
        self.runner = runner or SafeRunner()
        self.reader = readonly_access_backend(self.access, self.runner)
        self.helper = helper_path or directory / 'nextcloud-closure-preflight.php'

    def nextcloud_account(self, username):
        return parse_json(
            self.reader.occ('user:info', username, '--output=json'),
            'Nextcloud account metadata',
        )

    def access_state(self, username, mailbox):
        state = self.access.preflight(self.reader, username, mailbox)
        return self.access.public_state(state)

    def receipt(self, username, mailbox):
        root = self.access.RECEIPT_ROOT
        if root.exists() or root.is_symlink():
            self.access.require_private(root, directory=True)
        receipt = self.access.load_receipt(root / f'{username}.json', username, mailbox)
        attempts = receipt['attempts']
        latest = attempts[-1] if attempts else {}
        if not isinstance(latest, dict):
            raise PreflightError('access receipt latest attempt has an unexpected structure')
        return {
            'state': receipt['state'],
            'last_action': latest.get('action'),
            'last_status': latest.get('status'),
        }

    def identity(self, username):
        return self.reader.authentik(username, r'''
import json
import os
from authentik.core.models import User
from authentik.stages.invitation.models import Invitation

username = os.environ["COVIN_ACCESS_USERNAME"]
mailbox = username + "@example.test"
users = User.objects.filter(username=username)
result = {"user_count": users.count()}
if result["user_count"] == 1:
    user = users.get()
    result.update({
        "active": bool(user.is_active),
        "mailbox_matches": user.email == mailbox,
        "nextcloud_user_id_matches":
            isinstance(user.attributes, dict) and
            user.attributes.get("nextcloud_user_id") == username,
    })
result.update({
    "invitations_by_username":
        Invitation.objects.filter(fixed_data__username=username).count(),
    "invitations_by_mailbox":
        Invitation.objects.filter(fixed_data__email=mailbox).count(),
    "invitation_identity_conflicts":
        Invitation.objects.filter(fixed_data__email=mailbox)
        .exclude(fixed_data__username=username).count(),
})
print("COVIN_JSON=" + json.dumps(result, separators=(",", ":")))
''')

    def resources(self, username, groups):
        environment = os.environ.copy()
        environment['COVIN_CLOSURE_UID'] = username
        environment['COVIN_CLOSURE_GROUPS'] = json.dumps(groups)
        output = self.runner.run([
            'docker', 'exec', '-i', '-u', 'www-data',
            '-e', 'COVIN_CLOSURE_UID', '-e', 'COVIN_CLOSURE_GROUPS',
            self.access.NEXTCLOUD_CONTAINER, 'php',
        ], env=environment, input_text=self.helper.read_text(encoding='utf-8'))
        return unique_marker(output, 'Nextcloud resource inventory')

    def mounts(self, username):
        commands = {
            'team_folders': ('groupfolders:list', f'--user={username}'),
            'personal_external_mounts': ('files_external:list', username),
            'admin_external_mounts': ('files_external:list',),
        }
        counts = {}
        for name, command in commands.items():
            rows = parse_json(
                self.reader.occ(*command, '--output=json'), name)
            # The installed interfaces return arrays. Unknown wrappers are NOT zero.
            if not isinstance(rows, list):
                raise PreflightError(f'{name} listing has an unexpected structure')
            counts[name] = len(rows)
        return counts


def inspect(backend, username):
    if not re.fullmatch(USERNAME_PATTERN, username):
        raise PreflightError('username must be 2–64 lowercase account characters')
    if username in PROTECTED_USERNAMES:
        raise PreflightError('refusing to inspect a protected service or administrator account')
    mailbox = f'{username}@{DOMAIN}'
    account = backend.nextcloud_account(username)
    if not isinstance(account, dict) or account.get('user_id') != username:
        raise PreflightError('Nextcloud did not return the exact requested account')
    if account.get('email') != mailbox or account.get('backend') != 'user_oidc':
        raise PreflightError('Nextcloud identity mapping or backend requires manual review')
    groups = account.get('groups')
    if (not isinstance(groups, list)
            or any(not isinstance(item, str) or not item for item in groups)
            or len(groups) != len(set(groups))):
        raise PreflightError('Nextcloud group listing has an unexpected structure')
    if 'admin' in groups:
        raise PreflightError('refusing to inspect a Nextcloud administrator for closure')
    enabled = flag(account.get('enabled'), 'Nextcloud enabled state')
    state = backend.access_state(username, mailbox)
    if not isinstance(state, dict):
        raise PreflightError('access state has an unexpected structure')
    required_flags = (
        'nextcloud_enabled', 'authentik_active', 'mailcow_active',
        'mailcow_sogo_access', 'mailcow_imap_access', 'mailcow_pop3_access',
        'mailcow_smtp_access', 'mailcow_sieve_access',
    )
    required_counts = (
        'authentik_sessions', 'nextcloud_tokens', 'mailcow_app_passwords',
        'mailcow_web_sessions',
    )
    # Whitelist output; never copy internal token/password IDs into the report.
    access_report = {key: flag(state.get(key), key) for key in required_flags}
    access_report.update({key: count(state.get(key), key) for key in required_counts})
    if enabled != access_report['nextcloud_enabled']:
        raise PreflightError('Nextcloud state changed during inspection; retry read-only')
    receipt = backend.receipt(username, mailbox)
    if (not isinstance(receipt, dict) or not isinstance(receipt.get('state'), str)
            or receipt.get('last_action') not in (None, 'suspend', 'resume')
            or receipt.get('last_status') not in (None, 'pending', 'complete', 'failed')):
        raise PreflightError('access receipt summary has an unexpected structure')
    identity = backend.identity(username)
    if not isinstance(identity, dict) or count(identity.get('user_count'), 'identity count') != 1:
        raise PreflightError('Authentik did not return exactly one identity')
    if not flag(identity.get('mailbox_matches'), 'Authentik mailbox mapping'):
        raise PreflightError('Authentik mailbox mapping requires manual review')
    if not flag(identity.get('nextcloud_user_id_matches'), 'Authentik Nextcloud mapping'):
        raise PreflightError('Authentik Nextcloud mapping requires manual review')
    identity_report = {'active': flag(identity.get('active'), 'Authentik active state')}
    if identity_report['active'] != access_report['authentik_active']:
        raise PreflightError('Authentik state changed during inspection; retry read-only')
    for key in ('invitations_by_username', 'invitations_by_mailbox', 'invitation_identity_conflicts'):
        identity_report[key] = count(identity.get(key), key)
    resources = backend.resources(username, groups)
    if not isinstance(resources, dict):
        raise PreflightError('resource inventory has an unexpected structure')
    resource_report = {}
    for key in (
        'owned_calendars', 'owned_addressbooks', 'calendar_recipient_shares',
        'addressbook_recipient_shares', 'published_owned_calendars',
        'file_shares_owned_or_initiated', 'direct_user_file_shares_received',
        'group_file_shares_received',
    ):
        resource_report[key] = count(resources.get(key), key)
    requests = resources.get('requests')
    if not isinstance(requests, list):
        raise PreflightError('request inventory has an unexpected structure')
    request_report = []
    for item in requests:
        if (not isinstance(item, dict) or type(item.get('id')) is not int
                or item['id'] <= 0
                or item.get('status') not in {'pending', 'queued', 'running', 'completed', 'failed', 'rejected'}
                or item.get('job_type') not in {'provision', 'resend'}):
            raise PreflightError('request inventory entry requires manual review')
        request_report.append({
            'id': item['id'], 'status': item['status'], 'job_type': item['job_type'],
            'username_matches': flag(item.get('username_matches'), 'request username mapping'),
            'mailbox_matches': flag(item.get('mailbox_matches'), 'request mailbox mapping'),
        })
    mounts = backend.mounts(username)
    if not isinstance(mounts, dict):
        raise PreflightError('mount inventory has an unexpected structure')
    mount_report = {key: count(mounts.get(key), key) for key in (
        'team_folders', 'personal_external_mounts', 'admin_external_mounts')}
    blockers = []
    if (receipt['state'] != 'suspended' or receipt.get('last_action') != 'suspend'
            or receipt.get('last_status') != 'complete'):
        blockers.append('no-completed-suspension-receipt')
    if any(access_report[key] for key in required_flags if key != 'mailcow_active'):
        blockers.append('interactive-access-is-not-fully-suspended')
    if not access_report['mailcow_active']:
        blockers.append('mailbox-inbound-state-requires-review')
    if any(access_report[key] for key in required_counts):
        blockers.append('sessions-or-app-credentials-remain')
    if any(identity_report[key] for key in identity_report if key != 'active'):
        blockers.append('enrollment-invitations-require-reconciliation')
    if any(resource_report[key] for key in resource_report if key not in ('owned_calendars', 'owned_addressbooks')):
        blockers.append('sharing-dependencies-require-disposition')
    if any(mount_report.values()):
        blockers.append('team-or-external-storage-requires-review')
    if (len(request_report) != 1
            or any(not item['username_matches'] or not item['mailbox_matches']
                   or item['status'] != 'completed' for item in request_report)):
        blockers.append('approval-records-require-reconciliation')
    return {
        'status': 'closure-inspection-complete', 'username': username, 'mailbox': mailbox,
        'sampled_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'data_deletion': False, 'closure_authorized': False, 'ready_for_deletion': False,
        'snapshot_is_atomic': False,
        'group_source': 'occ-user-info', 'group_membership_count': len(groups),
        'access': access_report, 'access_receipt': {
            key: receipt.get(key) for key in ('state', 'last_action', 'last_status')},
        'identity': identity_report, 'resources': resource_report,
        'requests': request_report, 'mounts': mount_report,
        'observed_blockers': blockers, 'not_assessed': list(NOT_ASSESSED),
    }


def main(argv=None, backend=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', required=True)
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        raise PreflightError('run this read-only inventory as root')
    # Validate before loading dependencies or issuing service queries.
    if (not re.fullmatch(USERNAME_PATTERN, args.username)
            or args.username in PROTECTED_USERNAMES):
        raise PreflightError('invalid or protected target account')
    if backend is None and os.environ.get('ACCOUNT_PLATFORM_RUNTIME_REVIEWED') != '1':
        raise PreflightError('review service targets and policy before setting ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1')
    report = inspect(backend or ProductionBackend(), args.username)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Never emit backend response text, session values or private paths.
        message = str(error) if isinstance(error, PreflightError) else type(error).__name__
        print(f'STOP: {message}', file=sys.stderr)
        raise SystemExit(1)
