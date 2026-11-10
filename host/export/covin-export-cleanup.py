#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Remove expired delivery copies and explicitly registered master exports."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


DELIVERY_TOOL = Path(__file__).resolve().with_name('covin-export-delivery.py')
SPEC = importlib.util.spec_from_file_location('covin_export_delivery', DELIVERY_TOOL)
delivery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delivery)


def fail(message):
    raise RuntimeError(message)


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def parse_date(value, label):
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        fail(f'Invalid {label}.')


def retention_days(config):
    try:
        value = int(config['MASTER_RETENTION_DAYS'])
    except (KeyError, ValueError):
        fail('MASTER_RETENTION_DAYS must be an integer.')
    if not 90 <= value <= 180:
        fail('MASTER_RETENTION_DAYS must be between 90 and 180.')
    return value


def receipt_path(delivery_root, delivery_id):
    if not delivery.SAFE_ID.fullmatch(delivery_id):
        fail('Invalid delivery ID.')
    return delivery_root / f'delivery-{delivery_id}.json'


def load_receipt(path):
    delivery.require_private_file(path)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        fail(f'Invalid delivery receipt: {path.name}')
    required = {
        'version', 'delivery_id', 'request_id', 'username', 'archive_path',
        'archive_sha256', 'nextcloud_remote_path', 'nextcloud_share_id',
        'expires_on', 'notification_channel', 'state',
    }
    if not isinstance(value, dict) or not required.issubset(value):
        fail(f'Incomplete delivery receipt: {path.name}')
    if value['version'] != 1 or not delivery.SAFE_ID.fullmatch(str(value['delivery_id'])):
        fail(f'Unsupported delivery receipt: {path.name}')
    if (not delivery.SAFE_ID.fullmatch(str(value['request_id']))
            or not delivery.SAFE_ID.fullmatch(str(value['username']))
            or not re.fullmatch(r'[a-f0-9]{64}', str(value['archive_sha256']))
            or value['notification_channel'] != 'email'):
        fail(f'Invalid delivery receipt fields: {path.name}')
    allowed_states = {
        'pending-email', 'sent', 'delivery-cleanup-pending',
        'delivery-cleaned', 'master-cleanup-pending', 'cleaned',
    }
    if value['state'] not in allowed_states:
        fail(f'Invalid delivery receipt state: {path.name}')
    if path.name != f'delivery-{value["delivery_id"]}.json':
        fail(f'Delivery receipt name mismatch: {path.name}')
    return value


def safe_local_archive(data, delivery_root, *, allow_missing=False):
    archive = Path(str(data['archive_path']))
    if not archive.is_absolute() or archive.parent.resolve() != delivery_root.resolve():
        fail('Receipt archive path escapes the delivery root.')
    if archive.is_symlink():
        fail('Receipt archive path must not be a link.')
    expected_name = (f'covin-account-export-{data["request_id"]}-'
                     f'{str(data["delivery_id"])[:8]}.zip')
    if archive.name != expected_name:
        fail('Receipt archive name does not match its request and delivery IDs.')
    if not archive.exists():
        if allow_missing:
            return archive
        fail('Retained delivery archive is unexpectedly missing.')
    delivery.require_private_file(archive)
    if delivery.digest(archive) != data['archive_sha256']:
        fail('Retained delivery archive checksum mismatch.')
    return archive


def safe_remote_directory(data, config):
    remote = Path(str(data['nextcloud_remote_path']))
    folder = Path(config['NEXTCLOUD_REMOTE_FOLDER'].strip('/'))
    expected = folder / str(data['delivery_id'])
    if remote.is_absolute() or '..' in remote.parts or remote.parent != expected:
        fail('Receipt remote path does not match its delivery ID.')
    return expected.as_posix()


def delete_share(client, share_id):
    if not str(share_id).isdigit():
        fail('Invalid Nextcloud share ID in receipt.')
    result = client.run([
        '--request', 'DELETE', '--header', 'OCS-APIRequest: true',
        '--header', 'Accept: application/json',
        f'{client.base}/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}?format=json',
    ])
    try:
        meta = json.loads(result.stdout)['ocs']['meta']
        status = str(meta['status']).lower()
        code = int(meta['statuscode'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        fail('Nextcloud returned an invalid share-deletion response.')
    if status == 'ok' and code in {100, 200}:
        return
    if code == 404:
        return
    fail('Nextcloud rejected share deletion.')


def delete_remote_directory(client, remote, *, allow_missing=False):
    result = client.run(['--request', 'DELETE', client.dav_url(remote),
                         '--write-out', '\n%{http_code}'])
    status = result.stdout.rsplit('\n', 1)[-1]
    if status == '404' and allow_missing:
        return
    if status != '204':
        fail(f'Nextcloud delivery-folder deletion failed (HTTP {status}).')


def safe_master_export(data, config, *, allow_missing=False):
    source = Path(str(data['source_export_path']))
    export_root = Path(config['EXPORT_ROOT'])
    if source.is_symlink():
        fail('Registered master export must not be a link.')
    if not source.exists():
        if allow_missing:
            return source
        fail('Registered master export is missing.')
    resolved = delivery.beneath(source, export_root, 'Registered master export')
    if resolved.parent != export_root.resolve():
        fail('Registered master export must be a direct child of the export root.')
    username, payload, _ = delivery.validate_export(resolved)
    if username != data['username']:
        fail('Registered master export user does not match the receipt.')
    if delivery.digest(payload / 'checksums.json') != data['source_manifest_sha256']:
        fail('Registered master export manifest does not match the receipt.')
    for entry in resolved.rglob('*'):
        mode = entry.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            fail('Registered master export contains an unsafe entry.')
    return resolved


def register_master(receipt, data, export_dir, config, today):
    if data['state'] not in {'sent', 'delivery-cleanup-pending', 'delivery-cleaned'}:
        fail('Receipt state does not allow master registration.')
    if 'source_export_path' in data:
        fail('Receipt already has a registered master export.')
    source = Path(export_dir)
    export_root = Path(config['EXPORT_ROOT'])
    resolved = delivery.beneath(source, export_root, 'Master export')
    if resolved.parent != export_root.resolve():
        fail('Master export must be a direct child of the export root.')
    username, payload, _ = delivery.validate_export(resolved)
    if username != data['username']:
        fail('Master export user does not match the delivery receipt.')
    data['source_export_path'] = str(resolved)
    data['source_manifest_sha256'] = delivery.digest(payload / 'checksums.json')
    data['master_delete_after'] = (today + dt.timedelta(
        days=retention_days(config))).isoformat()
    data['master_registered_at'] = utc_now().isoformat()
    delivery.write_json_atomic(receipt, data)
    return data['master_delete_after']


def clean_delivery(receipt, data, delivery_root, config, client, now):
    retry = data['state'] == 'delivery-cleanup-pending'
    archive = safe_local_archive(data, delivery_root, allow_missing=retry)
    remote = safe_remote_directory(data, config)
    if data['state'] == 'sent':
        data['state'] = 'delivery-cleanup-pending'
        delivery.write_json_atomic(receipt, data)
    delete_share(client, data['nextcloud_share_id'])
    delete_remote_directory(client, remote, allow_missing=retry)
    archive.unlink(missing_ok=True)
    data['state'] = 'delivery-cleaned'
    data['delivery_cleaned_at'] = now.isoformat()
    delivery.write_json_atomic(receipt, data)


def clean_master(receipt, data, config, now):
    if data['state'] == 'delivery-cleaned':
        source = safe_master_export(data, config)
        data['state'] = 'master-cleanup-pending'
        delivery.write_json_atomic(receipt, data)
    else:
        source = safe_master_export(data, config, allow_missing=True)
    if source.exists():
        shutil.rmtree(source)
    data['state'] = 'cleaned'
    data['master_cleaned_at'] = now.isoformat()
    delivery.write_json_atomic(receipt, data)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=delivery.CONFIG_DEFAULT)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--register-master', action='store_true')
    parser.add_argument('--delivery-id')
    parser.add_argument('--export-dir', type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    if os.environ.get('ACCOUNT_PLATFORM_RUNTIME_REVIEWED') != '1':
        raise RuntimeError('review service targets and policy before setting ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1')
    if os.geteuid() != 0:
        fail('Run this tool as root.')
    os.umask(0o077)
    delivery.require_private_file(args.config)
    config = delivery.load_config(args.config)
    retention_days(config)
    delivery_root = Path(config['DELIVERY_ROOT'])
    export_root = Path(config['EXPORT_ROOT'])
    delivery.private_directory(delivery_root)
    delivery.private_directory(export_root)
    today = utc_now().date()

    if args.register_master:
        if args.dry_run or not args.delivery_id or not args.export_dir:
            fail('--register-master requires --delivery-id and --export-dir only.')
        receipt = receipt_path(delivery_root, args.delivery_id)
        data = load_receipt(receipt)
        deadline = register_master(receipt, data, args.export_dir, config, today)
        print(json.dumps({'status': 'master-registered',
                          'delivery_id': args.delivery_id,
                          'delete_after': deadline}, separators=(',', ':')))
        return
    if args.delivery_id or args.export_dir:
        fail('--delivery-id and --export-dir require --register-master.')

    receipts = sorted(delivery_root.glob('delivery-*.json'))
    loaded = [(path, load_receipt(path)) for path in receipts]
    delivery_due = [(path, data) for path, data in loaded
                    if data['state'] in {'sent', 'delivery-cleanup-pending'}
                    and today > parse_date(data['expires_on'], 'receipt expiry date')]
    master_due = [(path, data) for path, data in loaded
                  if data['state'] in {'delivery-cleaned', 'master-cleanup-pending'}
                  and 'master_delete_after' in data
                  and today > parse_date(data['master_delete_after'],
                                         'master deletion date')]
    if args.dry_run:
        print(json.dumps({'status': 'dry-run-valid', 'receipts': len(loaded),
                          'delivery_due': len(delivery_due),
                          'master_due': len(master_due)}, separators=(',', ':')))
        return

    client = None
    cleaned_delivery = 0
    cleaned_master = 0
    try:
        if delivery_due:
            secret = Path(config['NEXTCLOUD_APP_PASSWORD_FILE'])
            delivery.require_private_file(secret)
            app_password = secret.read_text(encoding='utf-8').strip()
            if not app_password or any(value in app_password for value in '\r\n\x00'):
                fail('Nextcloud app-password file is empty or invalid.')
            client = delivery.NextcloudClient(config, app_password)
            app_password = ''
            for receipt, data in delivery_due:
                clean_delivery(receipt, data, delivery_root, config, client, utc_now())
                cleaned_delivery += 1
        for receipt, data in loaded:
            if data['state'] in {'delivery-cleaned', 'master-cleanup-pending'} \
                    and 'master_delete_after' in data \
                    and today > parse_date(data['master_delete_after'],
                                           'master deletion date'):
                clean_master(receipt, data, config, utc_now())
                cleaned_master += 1
    finally:
        if client:
            client.close()
    subprocess.run(['logger', '-t', 'covin-export-cleanup',
                    f'delivery_cleaned={cleaned_delivery} master_cleaned={cleaned_master}'],
                   check=False)
    print(json.dumps({'status': 'cleanup-complete',
                      'delivery_cleaned': cleaned_delivery,
                      'master_cleaned': cleaned_master}, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP:', str(exc), file=sys.stderr)
        sys.exit(1)
