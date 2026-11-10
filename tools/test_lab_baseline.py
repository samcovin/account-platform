# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline baseline provenance/copy checks using synthetic source fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('baseline', Path(__file__).with_name('check-lab-baseline.py'))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'reference'
        self.app = self.source / baseline.APP_ROOT
        (self.app / 'appinfo').mkdir(parents=True)
        (self.app / 'appinfo/info.xml').write_text('<info><id>covin_account_admin</id><version>0.4.0</version></info>')
        (self.app / 'LICENSE').write_text('Synthetic license fixture; no new license granted.\n')
        self.manifest = self.root / 'baseline.json'
        self.pin()

    def pin(self):
        self.manifest.write_text(json.dumps({
            'schema': 1, 'app_id': 'covin_account_admin', 'version': '0.4.0',
            'files': {p.relative_to(self.source).as_posix(): {
                'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'mode': p.stat().st_mode & 0o777,
            } for p in self.app.rglob('*') if p.is_file()},
        }))

    def check(self):
        return baseline.validated_files(self.source, self.manifest)

    def test_validated_copy_preserves_exact_bytes_and_license(self):
        destination = self.root / 'stage'
        destination.mkdir()
        self.assertEqual(baseline.copy_baseline(self.source, self.manifest, destination), 2)
        for relative, (data, mode) in self.check().items():
            self.assertEqual((destination / relative).read_bytes(), data)
            self.assertEqual((destination / relative).stat().st_mode & 0o777, mode)

    def test_changed_source_is_rejected_before_copy(self):
        (self.app / 'LICENSE').write_text('changed fixture')
        destination = self.root / 'stage'
        destination.mkdir()
        with self.assertRaises(ValueError):
            baseline.copy_baseline(self.source, self.manifest, destination)
        self.assertEqual(list(destination.iterdir()), [])

    def test_missing_pinned_source_is_rejected(self):
        (self.app / 'LICENSE').unlink()
        with self.assertRaises(ValueError): self.check()

    def test_extra_source_is_rejected(self):
        (self.app / 'unexpected.txt').write_text('fixture')
        with self.assertRaises(ValueError): self.check()

    def test_symlink_is_rejected(self):
        (self.app / 'alias').symlink_to('LICENSE')
        with self.assertRaises(ValueError): self.check()

    def test_wrong_version_is_rejected_even_with_matching_file_hash(self):
        path = self.app / 'appinfo/info.xml'
        path.write_text(path.read_text().replace('0.4.0', '0.5.0'))
        self.pin()
        with self.assertRaises(ValueError): self.check()

    def test_wrong_app_id_is_rejected(self):
        path = self.app / 'appinfo/info.xml'
        path.write_text(path.read_text().replace('covin_account_admin', 'unrelated_app'))
        self.pin()
        with self.assertRaises(ValueError): self.check()

    def test_manifest_traversal_is_rejected(self):
        value = json.loads(self.manifest.read_text())
        value['files']['../outside'] = {'sha256': 'a' * 64, 'mode': 0o644}
        self.manifest.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.check()

    def test_existing_output_is_not_overwritten(self):
        destination = self.root / 'stage'
        destination.mkdir()
        (destination / 'keep.txt').write_text('preserve')
        with self.assertRaises(ValueError):
            baseline.copy_baseline(self.source, self.manifest, destination)
        self.assertEqual((destination / 'keep.txt').read_text(), 'preserve')

    def test_source_mode_drift_is_rejected(self):
        (self.app / 'LICENSE').chmod(0o755)
        with self.assertRaises(ValueError): self.check()


if __name__ == '__main__':
    unittest.main()
