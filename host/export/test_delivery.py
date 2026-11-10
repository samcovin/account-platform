# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline delivery tests; never contact Nextcloud, Mailcow or a recipient."""

import importlib.util
import io
import json
import os
import email.policy
from email.parser import BytesParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


TOOL = Path(__file__).with_name('covin-export-delivery.py')
spec = importlib.util.spec_from_file_location('delivery', TOOL)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
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

    def test_retention_calendar_uses_utc(self):
        instant = delivery.dt.datetime(
            2026, 9, 23, 3, 5, tzinfo=delivery.dt.timezone.utc)
        with patch.object(delivery.dt, 'datetime', wraps=delivery.dt.datetime) as clock:
            clock.now.return_value = instant
            self.assertEqual(delivery.utc_today(), delivery.dt.date(2026, 9, 23))

    def completed_export(self, root):
        export = root / 'exports' / 'test-user-20260922T000000Z-deadbeef'
        payload = export / 'payload'
        payload.mkdir(parents=True, mode=0o700)
        (root / 'exports').chmod(0o700)
        (export / 'EXPORT_COMPLETE').write_text('complete\n')
        (payload / 'sample.txt').write_text('portable export\n')
        (payload / 'nextcloud-report.json').write_text(json.dumps({
            'complete': True, 'user': 'test-user', 'files': [],
        }) + '\n')
        (payload / 'README.txt').write_text('test fixture\n')
        entries = []
        for path in sorted(payload.iterdir()):
            entries.append({'path': path.name, 'bytes': path.stat().st_size,
                            'sha256': delivery.digest(path)})
        (payload / 'checksums.json').write_text(json.dumps(entries) + '\n')
        for path in export.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
        export.chmod(0o700)
        return export

    def test_completed_export_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            export = self.completed_export(Path(temporary))
            with self.simulated_root_ownership(export):
                user, payload, count = delivery.validate_export(export)
                self.assertEqual(user, 'test-user')
                self.assertEqual(payload, export / 'payload')
                self.assertEqual(count, 3)
                (payload / 'sample.txt').write_text('changed\n')
                with self.assertRaises(RuntimeError):
                    delivery.validate_export(export)

    def test_dry_run_has_no_delivery_side_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = self.completed_export(root)
            delivery_root = root / 'deliveries'
            delivery_root.mkdir(mode=0o700)
            secret = root / 'secret'
            secret.write_text('test-only-token\n')
            secret.chmod(0o600)
            config = root / 'config'
            config.write_text(
                f'DELIVERY_ROOT={delivery_root}\nEXPORT_ROOT={root / "exports"}\n'
                'NEXTCLOUD_URL=https://cloud.example.test\n'
                'NEXTCLOUD_USER=covin-export-delivery\n'
                f'NEXTCLOUD_APP_PASSWORD_FILE={secret}\n'
                'NEXTCLOUD_REMOTE_FOLDER=Account Exports\n'
                'MAILCOW_SENDMAIL_CONTAINER=mailcowdockerized-postfix-mailcow-1\n'
                'FROM_ADDRESS=requests@example.test\nREPLY_TO=requests@example.test\n'
                'EXPIRY_DAYS=7\nMASTER_RETENTION_DAYS=180\n')
            config.chmod(0o600)
            arguments = [
                str(TOOL), '--config', str(config), '--dry-run',
                '--export-dir', str(export), '--request-id', 'request-1',
                '--display-name', 'Test User', '--recipient', 'verified@example.test',
            ]
            output = io.StringIO()
            with self.simulated_root_ownership(config, secret, root / 'exports',
                                               export, delivery_root), \
                    patch.object(delivery.os, 'geteuid', return_value=0), \
                    patch.object(sys, 'argv', arguments), redirect_stdout(output):
                delivery.main()
            self.assertEqual(json.loads(output.getvalue())['status'], 'dry-run-valid')
            self.assertFalse(list(delivery_root.iterdir()))
            self.assertNotIn('test-only-token', output.getvalue())

    def test_archive_password_not_in_argv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = self.completed_export(root)
            fake = root / 'fake-7zz'
            arguments = root / 'arguments'
            fake.write_text(
                '#!/usr/bin/env bash\nset -eu\n'
                f'printf "%s\\n" "$@" > "{arguments}"\n'
                'printf "Enter password (will not be echoed):"\nIFS= read -r first\n'
                'printf "Reenter password (will not be echoed):"\nIFS= read -r second\n'
                'test "$first" = "$second"\ntouch "$5"\n')
            fake.chmod(0o700)
            archive = root / 'delivery.zip'
            password = 'test-password-never-an-argument'
            delivery.create_archive(str(fake), export, archive, password)
            self.assertTrue(archive.is_file())
            self.assertNotIn(password, arguments.read_text())

    def test_ocs_100_and_200_are_success(self):
        client = object.__new__(delivery.NextcloudClient)
        client.base = 'https://cloud.example.test'
        for code in (100, 200):
            response = subprocess.CompletedProcess([], 0, stdout=json.dumps({
                'ocs': {'meta': {'status': 'ok', 'statuscode': code},
                        'data': {'url': 'https://cloud.example.test/s/abc', 'id': 9}}
            }))
            with patch.object(client, 'run', return_value=response):
                self.assertEqual(client.create_share('Account Exports/a/file.zip',
                                                     delivery.dt.date(2026, 9, 29)),
                                 ('9', 'https://cloud.example.test/s/abc'))

    def test_email_explains_aes_compatible_extraction(self):
        config = {
            'FROM_ADDRESS': 'requests@example.test',
            'REPLY_TO': 'requests@example.test',
            'MAILCOW_SENDMAIL_CONTAINER': 'postfix-test',
        }
        completed = subprocess.CompletedProcess([], 0)
        with patch.object(delivery, 'command_path', return_value='/usr/bin/docker'), \
                patch.object(delivery.subprocess, 'run', return_value=completed) as run:
            delivery.send_email(
                config, 'verified@example.test', 'Test User', 'test-password',
                'https://cloud.example.test/s/test', delivery.dt.date(2026, 9, 29),
                'a' * 64,
            )
        message = BytesParser(policy=email.policy.default).parsebytes(
            run.call_args.kwargs['input']).get_content()
        self.assertIn('use 7-Zip', message)
        self.assertIn('AES-256 ZIP encryption', message)
        self.assertIn('do not use File Explorer or Extract All', message)
        self.assertIn('https://www.7-zip.org/download.html', message)


if __name__ == '__main__':
    unittest.main()
