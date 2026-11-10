#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Encrypt, upload and email a completed portable account export."""

from __future__ import annotations

import argparse
import datetime as dt
import email.policy
from email.message import EmailMessage
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import secrets
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote, urlparse


CONFIG_DEFAULT = Path('/etc/covin/export-delivery.conf')
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
EMAIL = re.compile(r'^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$')


def fail(message):
    raise RuntimeError(message)


def load_config(path):
    values = {}
    for number, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            fail(f'Invalid configuration line {number}.')
        key, value = (part.strip() for part in line.split('=', 1))
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            fail(f'Invalid configuration key on line {number}.')
        if key in values:
            fail(f'Duplicate configuration key on line {number}.')
        values[key] = value
    required = {
        'DELIVERY_ROOT', 'EXPORT_ROOT', 'NEXTCLOUD_URL', 'NEXTCLOUD_USER',
        'NEXTCLOUD_APP_PASSWORD_FILE', 'NEXTCLOUD_REMOTE_FOLDER',
        'MAILCOW_SENDMAIL_CONTAINER', 'FROM_ADDRESS', 'REPLY_TO', 'EXPIRY_DAYS',
        'MASTER_RETENTION_DAYS',
    }
    missing = sorted(required - values.keys())
    if missing:
        fail('Missing configuration keys: ' + ', '.join(missing))
    return values


def require_private_file(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        fail(f'Private file must be a regular file, not a link: {path}')
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
        fail(f'Private file must be root-owned and mode 0600 or stricter: {path}')


def private_directory(path, *, create=False):
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        fail(f'Expected a real directory, not a link: {path}')
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
        fail(f'Directory must be root-owned and mode 0700 or stricter: {path}')


def beneath(path, root, label):
    resolved = path.resolve(strict=True)
    root_resolved = root.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        fail(f'{label} must be beneath {root_resolved}.')
    return resolved


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def utc_today():
    return dt.datetime.now(dt.timezone.utc).date()


def safe_payload_file(payload, relative):
    value = Path(relative)
    if value.is_absolute() or not value.parts or '..' in value.parts:
        fail('Unsafe checksum path in completed export.')
    target = payload / value
    if target.is_symlink() or not target.is_file():
        fail('Missing or unsafe payload file in completed export.')
    if not target.resolve().is_relative_to(payload.resolve()):
        fail('Payload path escapes the completed export.')
    return target


def validate_export(export_dir):
    private_directory(export_dir)
    marker = export_dir / 'EXPORT_COMPLETE'
    payload = export_dir / 'payload'
    if not marker.is_file() or marker.is_symlink():
        fail('Export has no safe EXPORT_COMPLETE marker.')
    if not payload.is_dir() or payload.is_symlink():
        fail('Export has no safe payload directory.')
    for entry in payload.rglob('*'):
        mode = entry.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            fail(f'Unsupported payload entry: {entry.relative_to(payload)}')
    report = json.loads((payload / 'nextcloud-report.json').read_text(encoding='utf-8'))
    username = report.get('user', '')
    if report.get('complete') is not True or not SAFE_ID.fullmatch(username):
        fail('Completed export report is invalid.')
    checksums = json.loads((payload / 'checksums.json').read_text(encoding='utf-8'))
    if not isinstance(checksums, list) or not checksums:
        fail('Completed export checksum manifest is invalid.')
    seen = set()
    for item in checksums:
        if not isinstance(item, dict) or set(item) != {'path', 'bytes', 'sha256'}:
            fail('Unexpected checksum manifest entry.')
        if item['path'] in seen:
            fail('Duplicate checksum manifest path.')
        seen.add(item['path'])
        target = safe_payload_file(payload, item['path'])
        if target.stat().st_size != item['bytes'] or digest(target) != item['sha256']:
            fail('Completed export payload no longer matches its manifest.')
    return username, payload, len(checksums)


def command_path(name):
    value = shutil.which(name)
    if not value:
        fail(f'Required command is missing: {name}')
    return value


def create_archive(seven_zip, export_dir, archive, password):
    """Use a pseudo-terminal so the archive password never appears in argv."""
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [seven_zip, 'a', '-tzip', '-mem=AES256', '-p', str(archive), 'payload'],
        cwd=export_dir, stdin=slave, stdout=slave, stderr=slave, close_fds=True,
    )
    os.close(slave)
    transcript = bytearray()
    prompts = 0
    deadline = time.monotonic() + 7200
    try:
        while process.poll() is None:
            if time.monotonic() > deadline:
                process.kill()
                fail('Archive creation timed out.')
            ready, _, _ = select.select([master], [], [], 1)
            if not ready:
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            transcript.extend(chunk)
            seen = bytes(transcript[-4096:]).lower().count(b'password')
            while prompts < min(seen, 2):
                os.write(master, password.encode('utf-8') + b'\n')
                prompts += 1
        return_code = process.wait(timeout=10)
    finally:
        os.close(master)
    if return_code != 0 or not archive.is_file():
        tail = bytes(transcript[-2000:]).decode('utf-8', 'replace').replace(password, '[REDACTED]')
        fail('7-Zip failed to create the archive. Output tail:\n' + tail)
    os.chmod(archive, 0o600)


class NextcloudClient:
    def __init__(self, config, password):
        self.base = config['NEXTCLOUD_URL'].rstrip('/')
        self.user = config['NEXTCLOUD_USER']
        self.curl = command_path('curl')
        handle = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             prefix='covin-curl-', delete=False)
        self.config_path = Path(handle.name)
        os.chmod(self.config_path, 0o600)
        escaped = f'{self.user}:{password}'.replace('\\', '\\\\').replace('"', '\\"')
        handle.write(f'user = "{escaped}"\nsilent\nshow-error\nfail-with-body\n')
        handle.close()

    def close(self):
        self.config_path.unlink(missing_ok=True)

    def dav_url(self, remote):
        user = quote(self.user, safe='')
        path = '/'.join(quote(part, safe='') for part in remote.strip('/').split('/'))
        return f'{self.base}/remote.php/dav/files/{user}/{path}'

    def run(self, arguments):
        return subprocess.run([self.curl, '--config', str(self.config_path), *arguments],
                              text=True, capture_output=True, check=False)

    def ensure_collection(self, remote):
        result = self.run(['--request', 'MKCOL', self.dav_url(remote),
                           '--write-out', '\n%{http_code}'])
        status = result.stdout.rsplit('\n', 1)[-1]
        if status not in {'201', '405'}:
            fail(f'Nextcloud could not create a delivery folder (HTTP {status}).')

    def upload(self, local, remote):
        result = self.run(['--upload-file', str(local), self.dav_url(remote),
                           '--write-out', '\n%{http_code}'])
        status = result.stdout.rsplit('\n', 1)[-1]
        if status not in {'200', '201', '204'}:
            fail(f'Nextcloud upload failed (HTTP {status}).')

    def create_share(self, remote, expires):
        result = self.run([
            '--request', 'POST', '--header', 'OCS-APIRequest: true',
            '--header', 'Accept: application/json', '--data-urlencode', f'path=/{remote}',
            '--data', 'shareType=3', '--data', 'permissions=1',
            '--data-urlencode', f'expireDate={expires.isoformat()}',
            f'{self.base}/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json',
        ])
        if result.returncode:
            fail('Nextcloud share creation failed.')
        try:
            payload = json.loads(result.stdout)
            meta = payload['ocs']['meta']
            data = payload['ocs']['data']
            if str(meta['status']).lower() != 'ok' or int(meta['statuscode']) not in {100, 200}:
                fail('Nextcloud rejected share creation.')
            url, share_id = str(data['url']), str(data['id'])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            fail('Nextcloud returned an invalid share response.')
        if not url.startswith(self.base + '/'):
            fail('Nextcloud returned an unexpected share URL.')
        return share_id, url

    def delete_remote(self, remote):
        self.run(['--request', 'DELETE', self.dav_url(remote)])


def send_email(config, recipient, display_name, archive_password, share_url,
               expires, archive_sha256):
    message = EmailMessage(policy=email.policy.SMTP)
    message['From'] = f'Account Services <{config["FROM_ADDRESS"]}>'
    message['To'] = recipient
    message['Reply-To'] = config['REPLY_TO']
    message['Subject'] = 'Your account export is ready'
    message['Message-ID'] = f'<account-export-{secrets.token_hex(12)}@example.test>'
    message.set_content(
        f'Hello {display_name},\n\nYour account export is ready.\n\n'
        f'Download: {share_url}\nArchive password: {archive_password}\n'
        f'Available through: {expires.isoformat()}\nSHA256: {archive_sha256}\n\n'
        'To open the encrypted ZIP, use 7-Zip or another extractor that supports '
        'AES-256 ZIP encryption. On Windows, do not use File Explorer or Extract '
        'All; they may show the filenames but fail with error 0x80004005.\n'
        'Download 7-Zip: https://www.7-zip.org/download.html\n\n'
        'The password above protects only this export. It is not your account '
        'password, app password, MFA code, or recovery code.\n\n'
        'After downloading, keep the archive and password somewhere safe. '
        'Reply to this message if you need assistance.\n\nAccount Services\n'
    )
    result = subprocess.run(
        [command_path('docker'), 'exec', '-i', config['MAILCOW_SENDMAIL_CONTAINER'],
         '/usr/sbin/sendmail', '-t', '-i'],
        input=message.as_bytes(), capture_output=True, check=False,
    )
    if result.returncode:
        fail('Mailcow rejected the export notification.')


def write_json_atomic(path, payload):
    temporary = path.with_name(path.name + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            os.chmod(temporary, 0o600)
            json.dump(payload, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG_DEFAULT)
    parser.add_argument('--export-dir', type=Path, required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--display-name', required=True)
    parser.add_argument('--recipient', required=True)
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    if os.environ.get('ACCOUNT_PLATFORM_RUNTIME_REVIEWED') != '1':
        raise RuntimeError('review service targets and policy before setting ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1')
    if os.geteuid() != 0:
        fail('Run this tool as root.')
    os.umask(0o077)
    require_private_file(args.config)
    config = load_config(args.config)
    if not SAFE_ID.fullmatch(args.request_id):
        fail('Invalid request ID.')
    if (not EMAIL.fullmatch(args.recipient) or not args.display_name.strip()
            or '\n' in args.display_name or '\r' in args.display_name):
        fail('Invalid recipient or display name.')
    if not EMAIL.fullmatch(config['FROM_ADDRESS']) or not EMAIL.fullmatch(config['REPLY_TO']):
        fail('Invalid configured sender or reply-to address.')
    parsed = urlparse(config['NEXTCLOUD_URL'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        fail('NEXTCLOUD_URL must be an HTTPS origin without embedded credentials.')
    parts = config['NEXTCLOUD_REMOTE_FOLDER'].strip('/').split('/')
    if not parts or any(part in {'', '.', '..'} for part in parts):
        fail('NEXTCLOUD_REMOTE_FOLDER is invalid.')
    expiry_days = int(config['EXPIRY_DAYS'])
    if not 1 <= expiry_days <= 30:
        fail('EXPIRY_DAYS must be between 1 and 30.')
    master_retention_days = int(config['MASTER_RETENTION_DAYS'])
    if not 90 <= master_retention_days <= 180:
        fail('MASTER_RETENTION_DAYS must be between 90 and 180.')
    export_root = Path(config['EXPORT_ROOT'])
    private_directory(export_root)
    export_dir = beneath(args.export_dir, export_root, 'Completed export directory')
    username, payload, manifest_count = validate_export(export_dir)
    secret_file = Path(config['NEXTCLOUD_APP_PASSWORD_FILE'])
    require_private_file(secret_file)
    delivery_root = Path(config['DELIVERY_ROOT'])
    if delivery_root.exists():
        private_directory(delivery_root)
    if args.dry_run:
        print(json.dumps({'status': 'dry-run-valid', 'request_id': args.request_id,
                          'username': username, 'manifest_files': manifest_count,
                          'expires_days': expiry_days, 'notification_channel': 'email'},
                         separators=(',', ':')))
        return

    seven_zip = command_path('7zz')
    command_path('curl')
    command_path('docker')
    private_directory(delivery_root, create=True)
    delivery_id = secrets.token_urlsafe(18)
    password = secrets.token_urlsafe(24)
    archive = delivery_root / f'covin-account-export-{args.request_id}-{delivery_id[:8]}.zip'
    receipt = delivery_root / f'delivery-{delivery_id}.json'
    today = utc_today()
    expires = today + dt.timedelta(days=expiry_days)
    master_delete_after = today + dt.timedelta(days=master_retention_days)
    remote_root = config['NEXTCLOUD_REMOTE_FOLDER'].strip('/')
    remote_dir = f'{remote_root}/{delivery_id}'
    remote_file = f'{remote_dir}/{archive.name}'
    client = None
    remote_created = False
    email_sent = False
    try:
        create_archive(seven_zip, export_dir, archive, password)
        archive_sha256 = digest(archive)
        app_password = secret_file.read_text(encoding='utf-8').strip()
        if not app_password or any(value in app_password for value in '\r\n\x00'):
            fail('Nextcloud app-password file is empty or invalid.')
        client = NextcloudClient(config, app_password)
        app_password = ''
        client.ensure_collection(remote_root)
        client.ensure_collection(remote_dir)
        remote_created = True
        client.upload(archive, remote_file)
        share_id, share_url = client.create_share(remote_file, expires)
        receipt_data = {
            'version': 1, 'delivery_id': delivery_id, 'request_id': args.request_id,
            'username': username, 'archive_path': str(archive),
            'archive_sha256': archive_sha256, 'nextcloud_remote_path': remote_file,
            'nextcloud_share_id': share_id, 'expires_on': expires.isoformat(),
            'notification_channel': 'email', 'state': 'pending-email',
            'source_export_path': str(export_dir),
            'source_manifest_sha256': digest(payload / 'checksums.json'),
            'master_delete_after': master_delete_after.isoformat(),
        }
        write_json_atomic(receipt, receipt_data)
        send_email(config, args.recipient, args.display_name, password, share_url,
                   expires, archive_sha256)
        email_sent = True
        receipt_data['state'] = 'sent'
        write_json_atomic(receipt, receipt_data)
        subprocess.run(['logger', '-t', 'covin-export-delivery',
                        f'sent request_id={args.request_id} delivery_id={delivery_id} channel=email'],
                       check=False)
        print(json.dumps({'status': 'sent', 'delivery_id': delivery_id,
                          'expires_on': expires.isoformat(), 'sha256': archive_sha256},
                         separators=(',', ':')))
    except Exception:
        if not email_sent:
            if client and remote_created:
                client.delete_remote(remote_dir)
            archive.unlink(missing_ok=True)
            receipt.unlink(missing_ok=True)
        else:
            subprocess.run(['logger', '-t', 'covin-export-delivery',
                            f'reconcile request_id={args.request_id} delivery_id={delivery_id}'],
                           check=False)
        raise
    finally:
        password = ''
        if client:
            client.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP:', str(exc), file=sys.stderr)
        sys.exit(1)
