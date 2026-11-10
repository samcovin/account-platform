# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline retention tests; never contact Nextcloud or delete a real export."""

import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
from contextlib import redirect_stdout
from unittest.mock import patch


TOOL = Path(__file__).with_name('covin-export-cleanup.py')
spec = importlib.util.spec_from_file_location('cleanup', TOOL)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class FakeClient:
    base = 'https://cloud.example.test'

    def __init__(self, *, fail_share=False):
        self.fail_share = fail_share
        self.calls = []

    def dav_url(self, remote):
        return 'https://cloud.example.test/dav/' + remote

    def run(self, arguments):
        self.calls.append(arguments)
        if '/ocs/' in arguments[-1]:
            if self.fail_share:
                return subprocess.CompletedProcess([], 1, stdout='not json')
            return subprocess.CompletedProcess([], 0, stdout=json.dumps({
                'ocs': {'meta': {'status': 'ok', 'statuscode': 200}}
            }))
        return subprocess.CompletedProcess([], 0, stdout='\n204')


class CleanupTests(unittest.TestCase):
    def setUp(self):
        reviewed = patch.dict(os.environ, {'ACCOUNT_PLATFORM_RUNTIME_REVIEWED': '1'})
        reviewed.start()
        self.addCleanup(reviewed.stop)

    def simulated_root_ownership(self, *paths):
        protected = {str(path) for path in paths}
        real_lstat = Path.lstat

        def simulated_lstat(path, *args, **kwargs):
            result = real_lstat(path, *args, **kwargs)
            if str(path) in protected:
                fields = list(result)
                fields[4] = 0
                return os.stat_result(fields)
            return result

        return patch.object(Path, 'lstat', simulated_lstat)

    def fixture(self, root, *, registered=True):
        export_root = root / 'exports'
        delivery_root = root / 'deliveries'
        export = export_root / 'test-user-20260922T000000Z-deadbeef'
        payload = export / 'payload'
        payload.mkdir(parents=True, mode=0o700)
        delivery_root.mkdir(mode=0o700)
        export_root.chmod(0o700)
        (export / 'EXPORT_COMPLETE').write_text('complete\n')
        (export / 'operator.log').write_text('private diagnostics\n')
        (payload / 'sample.txt').write_text('portable export\n')
        (payload / 'nextcloud-report.json').write_text(json.dumps({
            'complete': True, 'user': 'test-user', 'files': [],
        }) + '\n')
        entries = []
        for path in sorted(payload.iterdir()):
            entries.append({'path': path.name, 'bytes': path.stat().st_size,
                            'sha256': cleanup.delivery.digest(path)})
        (payload / 'checksums.json').write_text(json.dumps(entries) + '\n')
        for path in export.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
        export.chmod(0o700)

        delivery_id = 'deadbeef1234'
        archive = delivery_root / 'covin-account-export-request-1-deadbeef.zip'
        archive.write_bytes(b'encrypted archive fixture')
        archive.chmod(0o600)
        data = {
            'version': 1, 'delivery_id': delivery_id, 'request_id': 'request-1',
            'username': 'test-user', 'archive_path': str(archive),
            'archive_sha256': cleanup.delivery.digest(archive),
            'nextcloud_remote_path':
                f'Account Exports/{delivery_id}/covin-account-export-request-1-deadbeef.zip',
            'nextcloud_share_id': '9', 'expires_on': '2026-09-29',
            'notification_channel': 'email', 'state': 'sent',
        }
        if registered:
            data.update({
                'source_export_path': str(export),
                'source_manifest_sha256': cleanup.delivery.digest(
                    payload / 'checksums.json'),
                'master_delete_after': '2027-03-21',
            })
        receipt = delivery_root / f'delivery-{delivery_id}.json'
        receipt.write_text(json.dumps(data) + '\n')
        receipt.chmod(0o600)
        config = {
            'DELIVERY_ROOT': str(delivery_root),
            'EXPORT_ROOT': str(export_root),
            'NEXTCLOUD_REMOTE_FOLDER': 'Account Exports',
            'MASTER_RETENTION_DAYS': '180',
        }
        return config, receipt, archive, export

    def test_delivery_and_master_have_separate_retention(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, receipt, archive, export = self.fixture(Path(temporary))
            data = json.loads(receipt.read_text())
            paths = (receipt, archive, export)
            with self.simulated_root_ownership(*paths):
                cleanup.clean_delivery(receipt, data, Path(config['DELIVERY_ROOT']),
                                       config, FakeClient(),
                                       dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc))
                self.assertFalse(archive.exists())
                self.assertTrue(export.exists())
                self.assertEqual(json.loads(receipt.read_text())['state'],
                                 'delivery-cleaned')
                cleanup.clean_master(receipt, data, config,
                                     dt.datetime(2027, 3, 22,
                                                 tzinfo=dt.timezone.utc))
            self.assertFalse(export.exists())
            self.assertEqual(json.loads(receipt.read_text())['state'], 'cleaned')

    def test_cleanup_failure_remains_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, receipt, archive, export = self.fixture(Path(temporary))
            data = json.loads(receipt.read_text())
            with self.simulated_root_ownership(receipt, archive, export), \
                    self.assertRaises(RuntimeError):
                cleanup.clean_delivery(receipt, data, Path(config['DELIVERY_ROOT']),
                                       config, FakeClient(fail_share=True),
                                       dt.datetime(2026, 9, 30,
                                                   tzinfo=dt.timezone.utc))
            self.assertTrue(archive.exists())
            self.assertTrue(export.exists())
            self.assertEqual(json.loads(receipt.read_text())['state'],
                             'delivery-cleanup-pending')

    def test_existing_receipt_requires_explicit_master_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, receipt, _, export = self.fixture(Path(temporary), registered=False)
            data = json.loads(receipt.read_text())
            with self.simulated_root_ownership(receipt, export):
                deadline = cleanup.register_master(
                    receipt, data, export, config, dt.date(2026, 9, 23))
            updated = json.loads(receipt.read_text())
            self.assertEqual(deadline, '2027-03-22')
            self.assertEqual(updated['source_export_path'], str(export))
            self.assertEqual(updated['master_delete_after'], deadline)

    def test_archive_outside_delivery_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, receipt, archive, export = self.fixture(root)
            data = json.loads(receipt.read_text())
            outside = root / 'outside.zip'
            outside.write_bytes(archive.read_bytes())
            data['archive_path'] = str(outside)
            with self.simulated_root_ownership(receipt, archive, export, outside), \
                    self.assertRaises(RuntimeError):
                cleanup.safe_local_archive(data, Path(config['DELIVERY_ROOT']))

    def test_export_root_itself_cannot_be_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, receipt, _, export = self.fixture(Path(temporary), registered=False)
            data = json.loads(receipt.read_text())
            export_root = Path(config['EXPORT_ROOT'])
            with self.simulated_root_ownership(receipt, export, export_root), \
                    self.assertRaises(RuntimeError):
                cleanup.register_master(
                    receipt, data, export_root, config, dt.date(2026, 9, 23))

    def test_pending_cleanup_accepts_already_removed_delivery_copies(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, receipt, archive, export = self.fixture(Path(temporary))
            data = json.loads(receipt.read_text())
            data['state'] = 'delivery-cleanup-pending'
            receipt.write_text(json.dumps(data) + '\n')
            archive.unlink()

            class MissingClient(FakeClient):
                def run(self, arguments):
                    if '/ocs/' in arguments[-1]:
                        return subprocess.CompletedProcess([], 22, stdout=json.dumps({
                            'ocs': {'meta': {'status': 'failure', 'statuscode': 404}}
                        }))
                    return subprocess.CompletedProcess([], 22, stdout='\n404')

            with self.simulated_root_ownership(receipt, export):
                cleanup.clean_delivery(
                    receipt, data, Path(config['DELIVERY_ROOT']), config,
                    MissingClient(), dt.datetime(2026, 9, 30,
                                                 tzinfo=dt.timezone.utc))
            self.assertEqual(json.loads(receipt.read_text())['state'],
                             'delivery-cleaned')
            self.assertTrue(export.exists())

    def test_dry_run_has_no_cleanup_side_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_values, receipt, archive, export = self.fixture(root)
            secret = root / 'secret'
            secret.write_text('test-only-token\n')
            secret.chmod(0o600)
            config = root / 'config'
            config.write_text(
                f'DELIVERY_ROOT={config_values["DELIVERY_ROOT"]}\n'
                f'EXPORT_ROOT={config_values["EXPORT_ROOT"]}\n'
                'NEXTCLOUD_URL=https://cloud.example.test\n'
                'NEXTCLOUD_USER=covin-export-delivery\n'
                f'NEXTCLOUD_APP_PASSWORD_FILE={secret}\n'
                'NEXTCLOUD_REMOTE_FOLDER=Account Exports\n'
                'MAILCOW_SENDMAIL_CONTAINER=postfix-test\n'
                'FROM_ADDRESS=requests@example.test\n'
                'REPLY_TO=requests@example.test\n'
                'EXPIRY_DAYS=7\nMASTER_RETENTION_DAYS=180\n')
            config.chmod(0o600)
            output = io.StringIO()
            arguments = [str(TOOL), '--config', str(config), '--dry-run']
            paths = (config, receipt, archive, export,
                     Path(config_values['DELIVERY_ROOT']),
                     Path(config_values['EXPORT_ROOT']))
            with self.simulated_root_ownership(*paths), \
                    patch.object(cleanup.os, 'geteuid', return_value=0), \
                    patch.object(sys, 'argv', arguments), redirect_stdout(output):
                cleanup.main()
            result = json.loads(output.getvalue())
            self.assertEqual(result['status'], 'dry-run-valid')
            self.assertEqual(result['receipts'], 1)
            self.assertTrue(archive.exists())
            self.assertTrue(export.exists())
            self.assertNotIn('test-only-token', output.getvalue())


if __name__ == '__main__':
    unittest.main()
