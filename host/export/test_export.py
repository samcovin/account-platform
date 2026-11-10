# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline tests: simulated Docker boundary, never contact real services."""
import importlib.util
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('exporter', Path(__file__).with_name('covin-account-export.py'))
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)

class ExportTests(unittest.TestCase):
    def setUp(self):
        reviewed = patch.dict(os.environ, {'ACCOUNT_PLATFORM_RUNTIME_REVIEWED': '1'})
        reviewed.start()
        self.addCleanup(reviewed.stop)

    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                exporter.relative_file(Path(d), '../secret')

    def test_encrypted_message_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'cur').mkdir()
            (root / 'cur/1').write_bytes(b'CRYPTED\x03opaque')
            with self.assertRaises(ValueError):
                exporter.inspect_mail(root)

    def test_nested_mail_count(self):
        self.assertEqual(exporter.mail_count('INBOX messages=3 vsize=40\nTest/INBOX messages=3 vsize=40\n'), 6)
        with self.assertRaises(ValueError):
            exporter.mail_count('unexpected output')

    def test_recipient_readme_explains_package_in_plain_language(self):
        readme = exporter.recipient_readme()
        for item in ('files/', 'calendars/', 'contacts/', 'mail/',
                     'nextcloud-report.json', 'checksums.json'):
            self.assertIn(item, readme)
        self.assertIn('did not delete or change your account', readme)
        self.assertIn('Reply to the delivery email', readme)
        self.assertNotIn('cross-service snapshot', readme)
        self.assertNotIn('manifest-aware tooling', readme)

    def scenario(self, marker=True, changed=False, cleanup_failure=False):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            calls = []
            state = {'mail_status': 0}
            real_stat = Path.stat

            def simulated_stat(path, *args, **kwargs):
                result = real_stat(path, *args, **kwargs)
                if path == root / 'exports':
                    fields = list(result)
                    fields[4] = 0  # Simulate root ownership only for the export root.
                    return os.stat_result(fields)
                return result
            message = b'From: test@example.invalid\r\nSubject: Test\r\n\r\nBody\r\n'

            def fake(command, stdout=None, stderr=None):
                calls.append(command)
                text = ''
                if command[:2] == ['docker', 'cp']:
                    src, dst = command[2:]
                    if src.startswith(exporter.NC + ':'):
                        p = Path(dst)
                        p.mkdir()
                        for sub in ('files', 'contacts', 'calendars'):
                            (p / sub).mkdir()
                        (p / 'files/sample.txt').write_text('hello')
                        (p / 'contacts/addressbook-1.vcf').write_text('BEGIN:VCARD\nVERSION:3.0\nFN:Test\nEND:VCARD\n')
                        (p / 'nextcloud-report.json').write_text(json.dumps({
                            'complete': True, 'user': 'test-user',
                            'files': [{'path': 'sample.txt', 'bytes': 5, 'sha256': exporter.digest(p / 'files/sample.txt')}],
                            'calendars': [{'id': '1', 'uri': 'personal'}],
                            'addressbooks': [], 'excluded_storage_paths': []}))
                    elif src.startswith(exporter.MAIL + ':'):
                        p = Path(dst)
                        (p / 'cur').mkdir(parents=True)
                        (p / 'new').mkdir()
                        (p / 'cur/1:2,S').write_bytes(message)
                        # Must never be copied into the deliverable.
                        (p / 'dovecot-attributes').write_text('private-key-fixture')
                elif command[:2] == ['docker', 'exec']:
                    args = command[5:]
                    if args[:2] == ['php', 'occ'] and 'calendar:export' in args:
                        text = 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n'
                    elif args[:2] == ['php', '-r']:
                        text = 'CALENDAR_PARSED'
                    elif args and args[0] == 'php' and len(args) > 2 and args[1].endswith('/export.php'):
                        text = 'NEXTCLOUD_EXPORT_COMPLETE\n' if marker else ''
                    elif args[:3] == ['doveadm', 'mailbox', 'status']:
                        state['mail_status'] += 1
                        count = 2 if changed and state['mail_status'] == 2 else 1
                        text = f'INBOX messages={count} vsize=99\n'
                    elif args[:2] == ['rm', '-rf'] and cleanup_failure:
                        return subprocess.CompletedProcess(command, 1)
                if stdout == subprocess.PIPE:
                    return subprocess.CompletedProcess(command, 0, stdout=text.encode())
                if text and stdout is not None:
                    stdout.write(text.encode())
                return subprocess.CompletedProcess(command, 0)

            with patch.object(exporter, 'ROOT', root / 'exports'), \
                 patch.object(Path, 'stat', simulated_stat), \
                 patch.object(exporter.os, 'geteuid', return_value=0), \
                 patch.object(exporter.os, 'chown'), \
                 patch.object(exporter.subprocess, 'run', side_effect=fake), \
                 patch('sys.argv', ['exporter', 'test-user']):
                if not marker or changed or cleanup_failure:
                    with self.assertRaises((RuntimeError, ValueError)):
                        exporter.main()
                    self.assertFalse(list((root / 'exports').rglob('EXPORT_COMPLETE')))
                else:
                    exporter.main()
                    self.assertEqual(len(list((root / 'exports').rglob('EXPORT_COMPLETE'))), 1)
                    payload = next((root / 'exports').glob('*/payload'))
                    self.assertEqual((payload / 'mail/message-00000001.eml').read_bytes(), message)
                    self.assertIn('What is included', (payload / 'README.txt').read_text())
                    self.assertFalse(list(payload.rglob('dovecot-*')))
                    for entry in json.loads((payload / 'checksums.json').read_text()):
                        self.assertEqual(exporter.digest(payload / entry['path']), entry['sha256'])
                self.assertTrue(any('rm' in command for command in calls))
                self.assertFalse(any('user:delete' in command or 'expunge' in command for command in calls))

    def test_success_excludes_private_mail_metadata(self):
        self.scenario()

    def test_missing_completion_fails(self):
        self.scenario(marker=False)

    def test_changed_mailbox_fails(self):
        self.scenario(changed=True)

    def test_cleanup_failure_has_no_success_marker(self):
        self.scenario(cleanup_failure=True)

if __name__ == '__main__':
    unittest.main()
