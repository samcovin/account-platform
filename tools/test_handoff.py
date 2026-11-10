# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Regression checks for handoff disclosure boundaries; fixtures are synthetic."""
import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verify_handoff', Path(__file__).with_name('verify-handoff.py'))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class HandoffBoundaryTests(unittest.TestCase):
    def test_private_keys_and_tokens_are_rejected_without_echoing_values(self):
        fixtures = [
            b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----',
            b'ghp_' + b'z' * 40,
            b'AKIA' + b'Z' * 16,
        ]
        for value in fixtures:
            with self.subTest(length=len(value)):
                errors = verify.inspect_file('source.txt', value)
                self.assertTrue(errors)
                self.assertNotIn(value.decode(), '\n'.join(errors))

    def test_private_runtime_data_and_archives_are_excluded(self):
        for path in ('private/notes.txt', 'backups/copy.txt', '.env',
                     'export.sql', 'vault.kdbx', 'runtime/receipt.json',
                     '.aws/config', 'snapshot.tar.gz', 'accounts.log'):
            with self.subTest(path=path):
                self.assertIn('excluded-file', verify.inspect_file(path, b'fixture'))

    def test_private_hosts_and_home_paths_are_rejected(self):
        for value in (b'https://private.example.' + b'com', b'ops@personal.example.' + b'org',
                      b'192.168.' + b'24.12', b'/home/' + b'operator/.ssh/key',
                      b'https://user:' + b'fixture-password@cloud.example.test'):
            with self.subTest(value=value):
                self.assertTrue(verify.inspect_file('source.txt', value, initial_import=True))

    def test_escaped_private_hostname_is_rejected(self):
        self.assertIn('non-example-hostname', verify.inspect_file(
            'source.php', rb'/person@example\.' + b'com/', initial_import=True))

    def test_reserved_examples_and_public_documentation_remain_usable(self):
        for value in (b'https://cloud.example.test', b'fixture@example.invalid',
                      b'127.0.0.1', b'https://www.gnu.org/licenses/',
                      b'https://www.7-zip.org/download.html'):
            with self.subTest(value=value):
                self.assertEqual(verify.inspect_file('source.txt', value), [])

    def test_license_notice_is_preserved(self):
        value = b'Copyright (C) 2026 Original Family ' + b'Services'
        self.assertEqual(verify.inspect_file('app/LICENSE', value), [])
        self.assertIn('personal-branding', verify.inspect_file('app/index.html', value, initial_import=True))

    def test_xml_and_text_boundaries(self):
        self.assertEqual(verify.inspect_file('info.xml', b'<info/>'), [])
        self.assertIn('invalid-xml', verify.inspect_file('info.xml', b'<info>'))
        self.assertIn('non-text-file', verify.inspect_file('file.bin', b'\xff'))
        self.assertIn('binary-content', verify.inspect_file('file.txt', b'a\0b'))


class GitHistoryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root = base / 'repo'
        self.root.mkdir()
        template = base / 'empty-template'
        template.mkdir()
        self.env = {**os.environ, 'GIT_CONFIG_GLOBAL': '/dev/null',
                    'GIT_CONFIG_SYSTEM': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'}
        self.git('init', '--initial-branch=main', f'--template={template}')
        self.git('config', 'user.name', 'Sanitized Source Import')
        self.git('config', 'user.email', 'source-import@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        (self.root / 'README.md').write_text('Synthetic handoff fixture\n')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], env=self.env, stderr=subprocess.PIPE)

    def commit(self):
        self.git('add', '--all')
        self.git('commit', '-m', 'Synthetic fixture')

    def test_clean_neutral_import_passes(self):
        errors, counts = verify.scan_repository(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(counts['stored_commits'], 1)

    def test_secret_deleted_from_head_still_fails_git_object_scan(self):
        path = self.root / 'fixture.txt'
        path.write_bytes(b'ghp_' + b'z' * 40)
        self.commit()
        path.unlink()
        self.commit()
        errors, _ = verify.scan_repository(self.root)
        self.assertTrue(any('github-token' in e for e in errors))
        self.assertFalse(any('z' * 40 in e for e in errors))

    def test_deleted_runtime_filename_is_detected_in_history(self):
        path = self.root / '.env'
        path.write_text('SYNTHETIC=fixture\n')
        self.commit()
        path.unlink()
        self.commit()
        errors, _ = verify.scan_repository(self.root)
        self.assertTrue(any('excluded-file' in e and '.env' in e for e in errors))

    def test_unreachable_secret_blob_is_detected(self):
        subprocess.run(['git', '-C', str(self.root), 'hash-object', '-w', '--stdin'],
                       input=b'ghp_' + b'y' * 40, check=True, capture_output=True, env=self.env)
        errors, _ = verify.scan_repository(self.root)
        self.assertTrue(any('github-token' in e for e in errors))

    def test_normal_remote_is_allowed_but_initial_import_refuses_it(self):
        self.git('remote', 'add', 'fixture', 'https://remote.example.test/source.git')
        errors, _ = verify.scan_repository(self.root)
        self.assertEqual(errors, [])
        errors, _ = verify.scan_repository(self.root, initial_import=True)
        self.assertIn('repository: unexpected remote at initial import', errors)

    def test_work_identity_real_domain_and_remote_allow_normal_development(self):
        self.git('config', 'user.name', 'Work Developer')
        self.git('config', 'user.email', 'developer@example.test')
        self.git('remote', 'add', 'fixture', 'https://remote.example.test/source.git')
        (self.root / 'README.md').write_text('Work URL: https://work.example.' + 'com\n')
        self.commit()
        errors, _ = verify.scan_repository(self.root)
        self.assertEqual(errors, [])

    def test_ignored_runtime_file_does_not_block_normal_development(self):
        (self.root / '.gitignore').write_text('.env\n')
        self.commit()
        (self.root / '.env').write_text('SYNTHETIC=offline-fixture\n')
        errors, _ = verify.scan_repository(self.root)
        self.assertEqual(errors, [])
        errors, _ = verify.scan_repository(self.root, initial_import=True)
        self.assertTrue(any('excluded-file' in e and '.env' in e for e in errors))

    def test_initial_import_accepts_unborn_repo_without_forcing_an_author(self):
        root = self.root.parent / 'fresh'
        root.mkdir()
        subprocess.run(['git', '-C', str(root), 'init', '--initial-branch=feature/work-setup',
                        f'--template={self.root.parent / "empty-template"}'],
                       env=self.env, check=True, capture_output=True)
        (root / 'README.md').write_text('Fresh source fixture\n')
        errors, counts = verify.scan_repository(root, initial_import=True)
        self.assertEqual(errors, [])
        self.assertEqual(counts['stored_commits'], 0)

    def test_initial_import_refuses_packaged_author_and_hook_overrides(self):
        self.git('config', 'core.hooksPath', '/dev/null')
        errors, _ = verify.scan_repository(self.root, initial_import=True)
        self.assertIn('repository: local author/hook/signing override at initial import', errors)

    def test_symlinks_are_refused(self):
        (self.root / 'alias.txt').symlink_to('README.md')
        self.commit()
        errors, _ = verify.scan_repository(self.root)
        self.assertTrue(any('unexpected file mode' in e for e in errors))
        self.assertTrue(any('symlink' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
