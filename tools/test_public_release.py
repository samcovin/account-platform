# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Public-source disclosure and mixed-license boundary regression fixtures."""
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
import os
import subprocess
from contextlib import redirect_stdout
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('public_release', Path(__file__).with_name('check-public-release.py'))
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('LICENSE', 'apps/covin_account_admin/LICENSE',
                     'LICENSES/AGPL-3.0-or-later.txt'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        self.metadata = self.root / 'apps/covin_account_admin/appinfo/info.xml'
        self.metadata.parent.mkdir(parents=True)
        self.metadata.write_text('<info><licence>agpl</licence></info>')
        self.mapping = {'schema': 1, 'files': {}, 'preserved_notices': {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in ('LICENSE', 'apps/covin_account_admin/LICENSE', 'LICENSES/AGPL-3.0-or-later.txt')},
            'release_gates': [{'id': identifier, 'status': 'pending'}
                              for identifier in sorted(release.REQUIRED_GATES)]}
        self.inventory()

    def inventory(self):
        self.mapping['files'] = {name: {'license': release.license_for(name)}
                                 for name in release.source_files(self.root)}

    def check(self):
        return release.check_tree(self.root, self.mapping)

    def test_mixed_license_tree_passes_while_reporting_unresolved_owner_gate(self):
        errors, pending = self.check()
        self.assertEqual(errors, [])
        self.assertEqual(pending, sorted(release.REQUIRED_GATES))

    def test_missing_gate_list_is_not_implicit_clearance(self):
        self.mapping.pop('release_gates')
        self.assertTrue(any('release-gates:' in e for e in self.check()[0]))

    def test_empty_gate_list_is_not_implicit_clearance(self):
        self.mapping['release_gates'] = []
        self.assertTrue(any('release-gates:' in e for e in self.check()[0]))

    def test_duplicate_gate_cannot_replace_a_required_gate(self):
        self.mapping['release_gates'][-1] = dict(self.mapping['release_gates'][0])
        self.assertTrue(any('release-gates:' in e for e in self.check()[0]))

    def test_unknown_status_is_refused(self):
        self.mapping['release_gates'][0]['status'] = 'approved-ish'
        self.assertTrue(any('invalid gate status' in e for e in self.check()[0]))

    def test_malformed_gate_list_is_refused_without_traceback(self):
        self.mapping['release_gates'] = ['not a gate record']
        self.assertTrue(any('release-gates:' in e for e in self.check()[0]))

    def test_non_string_status_is_refused_without_traceback(self):
        self.mapping['release_gates'][0]['status'] = []
        self.assertTrue(any('invalid gate status' in e for e in self.check()[0]))

    def test_non_object_mapping_is_refused_without_traceback(self):
        self.assertEqual(release.check_tree(self.root, [])[0], ['license-map: invalid schema'])

    def test_resolved_gate_requires_resolution_and_evidence(self):
        self.mapping['release_gates'][0]['status'] = 'resolved'
        errors, _ = self.check()
        self.assertTrue(any('lacks a resolution' in e for e in errors))
        self.assertTrue(any('lacks evidence' in e for e in errors))

    def test_evidence_must_be_an_existing_candidate_file(self):
        self.mapping['release_gates'][0].update(status='resolved', resolution='Synthetic fixture', evidence=['../outside'])
        self.assertTrue(any('invalid evidence path' in e for e in self.check()[0]))

    def test_resolved_technical_gate_with_evidence_preserves_other_pending_gates(self):
        gate = next(g for g in self.mapping['release_gates'] if g['id'] == 'PHP-VALIDATION')
        gate.update(status='resolved', resolution='Synthetic fixture evidence', evidence=['LICENSE'])
        errors, pending = self.check()
        self.assertEqual(errors, [])
        self.assertNotIn('PHP-VALIDATION', pending)
        self.assertEqual(len(pending), len(release.REQUIRED_GATES) - 1)

    def test_secret_left_in_index_is_not_hidden_by_clean_worktree(self):
        env = {**os.environ, 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'}
        subprocess.run(['git', '-C', str(self.root), 'init', '--initial-branch=fixture'],
                       env=env, check=True, capture_output=True)
        token = 'ghp_' + 'z' * 40
        secret = self.root / 'fixture.txt'
        secret.write_text(token)
        subprocess.run(['git', '-C', str(self.root), 'add', 'fixture.txt'], env=env, check=True)
        secret.unlink()
        errors, _ = self.check()
        self.assertTrue(any('github-token' in e for e in errors))
        self.assertNotIn(token, '\n'.join(errors))

    def test_release_cli_fails_closed_while_owner_gate_is_pending(self):
        target = self.root / 'LICENSE-MAP.json'
        target.write_text('{}')
        self.inventory()
        target.write_text(json.dumps(self.mapping))
        output = io.StringIO()
        with patch.object(sys, 'argv', ['check-public-release.py', '--release', str(self.root)]), redirect_stdout(output):
            self.assertEqual(release.main(), 2)
        self.assertIn('NOT CLEARED FOR RELEASE', output.getvalue())

    def test_app_cannot_silently_receive_bsd(self):
        self.mapping['files']['apps/covin_account_admin/LICENSE']['license'] = 'BSD-3-Clause'
        errors, _ = self.check()
        self.assertTrue(any('incorrect license assignment' in e for e in errors))

    def test_license_document_is_not_relicensed_as_first_party_bsd(self):
        self.assertEqual(release.license_for('LICENSES/AGPL-3.0-or-later.txt'),
                         'LicenseRef-Verbatim-License-Document')

    def test_changed_original_notice_is_rejected(self):
        (self.root / 'apps/covin_account_admin/LICENSE').write_text('changed fixture')
        errors, _ = self.check()
        self.assertTrue(any('required license notice changed' in e for e in errors))

    def test_removing_notice_pins_does_not_bypass_preservation_check(self):
        self.mapping['preserved_notices'] = {}
        self.assertIn('license-map: mandatory notice pins are missing', self.check()[0])

    def test_changed_app_metadata_license_is_rejected(self):
        self.metadata.write_text('<info><licence>bsd</licence></info>')
        errors, _ = self.check()
        self.assertIn('app metadata: retained AGPL declaration changed', errors)

    def test_unmapped_file_is_rejected(self):
        (self.root / 'extra.txt').write_text('fixture')
        errors, _ = self.check()
        self.assertIn('license-map: file coverage differs from the candidate', errors)

    def test_private_reference_is_excluded_even_when_mapped(self):
        path = self.root / 'private-audit/record.txt'
        path.parent.mkdir()
        path.write_text('fixture')
        self.inventory()
        errors, _ = self.check()
        self.assertTrue(any('private/reference material' in e for e in errors))

    def test_credentials_are_reported_without_exposing_values(self):
        token = 'ghp_' + 'z' * 40
        (self.root / 'source.txt').write_text(token)
        self.inventory()
        errors, _ = self.check()
        self.assertTrue(any('github-token' in e for e in errors))
        self.assertNotIn(token, '\n'.join(errors))

    def test_unapproved_host_is_rejected(self):
        (self.root / 'source.txt').write_text('https://private.example.' + 'com')
        self.inventory()
        errors, _ = self.check()
        self.assertTrue(any('non-example-hostname' in e for e in errors))

    def test_documented_required_attribution_is_allowed(self):
        (self.root / 'NOTICE.md').write_text('Copyright (C) 2026 Covin Family ' + 'Services\n')
        self.inventory()
        self.assertEqual(self.check()[0], [])


if __name__ == '__main__':
    unittest.main()
