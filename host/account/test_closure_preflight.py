# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Mock-only closure-inspection tests. Never contact a production service."""

import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'closure_preflight', Path(__file__).with_name('covin-account-closure-preflight.py'))
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.account = {
            'user_id': 'test-user', 'email': 'test-user@example.test',
            'enabled': False, 'groups': ['everyone'], 'backend': 'user_oidc',
        }
        self.access = {
            'nextcloud_enabled': False, 'nextcloud_tokens': 0,
            'authentik_active': False, 'authentik_sessions': 0,
            'mailcow_active': True, 'mailcow_app_passwords': 0,
            'mailcow_web_sessions': 0,
            **{f'mailcow_{protocol}_access': False
               for protocol in ('sogo', 'imap', 'pop3', 'smtp', 'sieve')},
            'nextcloud_token_ids': ['private-token-id'],
        }
        self.access_receipt = {
            'state': 'suspended', 'last_action': 'suspend', 'last_status': 'complete',
            'private_extra': 'must-not-be-printed',
        }
        self.identity_data = {
            'user_count': 1, 'active': False, 'mailbox_matches': True,
            'nextcloud_user_id_matches': True, 'invitations_by_username': 0,
            'invitations_by_mailbox': 0, 'invitation_identity_conflicts': 0,
            'private_extra': 'must-not-be-printed',
        }
        self.resource_data = {
            'owned_calendars': 3, 'owned_addressbooks': 2,
            'calendar_recipient_shares': 0, 'addressbook_recipient_shares': 0,
            'published_owned_calendars': 0, 'file_shares_owned_or_initiated': 0,
            'direct_user_file_shares_received': 0, 'group_file_shares_received': 0,
            'requests': [{
                'id': 42, 'status': 'completed', 'job_type': 'provision',
                'username_matches': True, 'mailbox_matches': True,
                'contact_email': 'must-not-be-printed',
            }],
        }
        self.mount_data = {
            'team_folders': 0, 'personal_external_mounts': 0,
            'admin_external_mounts': 0, 'password': 'must-not-be-printed',
        }

    def nextcloud_account(self, username):
        self.calls.append('account-read')
        return copy.deepcopy(self.account)

    def access_state(self, username, mailbox):
        self.calls.append('access-read')
        return copy.deepcopy(self.access)

    def receipt(self, username, mailbox):
        self.calls.append('receipt-read')
        return copy.deepcopy(self.access_receipt)

    def identity(self, username):
        self.calls.append('identity-read')
        return copy.deepcopy(self.identity_data)

    def resources(self, username, groups):
        self.calls.append(('resources-read', username, tuple(groups)))
        return copy.deepcopy(self.resource_data)

    def mounts(self, username):
        self.calls.append('mounts-read')
        return copy.deepcopy(self.mount_data)


class FixtureRunner:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def run(self, arguments, **kwargs):
        self.calls.append((arguments, kwargs))
        return self.output


class FixtureOcc:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def occ(self, *args):
        self.calls.append(args)
        return json.dumps(self.data)


class ClosurePreflightTests(unittest.TestCase):
    def test_read_only_report_never_authorizes_deletion(self):
        backend = FakeBackend()
        before = copy.deepcopy(backend.__dict__)
        result = closure.inspect(backend, 'test-user')
        self.assertEqual(result['observed_blockers'], [])
        self.assertFalse(result['data_deletion'])
        self.assertFalse(result['closure_authorized'])
        self.assertFalse(result['ready_for_deletion'])
        self.assertFalse(result['snapshot_is_atomic'])
        self.assertEqual(result['not_assessed'], closure.NOT_ASSESSED)
        for key in before:
            if key != 'calls':
                self.assertEqual(backend.__dict__[key], before[key])
        self.assertEqual(len(backend.calls), 6)

    def test_groups_are_taken_from_normal_occ_metadata(self):
        backend = FakeBackend()
        result = closure.inspect(backend, 'test-user')
        self.assertEqual(result['group_membership_count'], 1)
        self.assertEqual(result['group_source'], 'occ-user-info')
        self.assertIn(('resources-read', 'test-user', ('everyone',)), backend.calls)

    def test_private_fields_are_excluded(self):
        text = json.dumps(closure.inspect(FakeBackend(), 'test-user'))
        for private in ('must-not-be-printed', 'private-token-id', 'contact_email', 'private_extra'):
            self.assertNotIn(private, text)
        self.assertNotIn('everyone', text)

    def test_invalid_and_protected_targets_issue_no_queries(self):
        for username in ('admin', 'root', 'covin-export-delivery', 'Test-user', '../test-user', 'x'):
            with self.subTest(username=username):
                backend = FakeBackend()
                with self.assertRaises(closure.PreflightError):
                    closure.inspect(backend, username)
                self.assertEqual(backend.calls, [])

    def test_administrator_membership_is_rejected(self):
        backend = FakeBackend()
        backend.account['groups'].append('admin')
        with self.assertRaises(closure.PreflightError):
            closure.inspect(backend, 'test-user')
        self.assertEqual(backend.calls, ['account-read'])

    def test_identity_mismatches_are_rejected(self):
        for field, value in (('user_id', 'other-user'), ('email', 'other@example.test'), ('backend', 'other')):
            with self.subTest(field=field):
                backend = FakeBackend()
                backend.account[field] = value
                with self.assertRaises(closure.PreflightError):
                    closure.inspect(backend, 'test-user')

    def test_malformed_groups_are_rejected(self):
        for groups in ({}, ['everyone', 'everyone'], [None], ['']):
            backend = FakeBackend()
            backend.account['groups'] = groups
            with self.assertRaises(closure.PreflightError):
                closure.inspect(backend, 'test-user')

    def test_authentik_mapping_mismatch_is_rejected(self):
        for field, value in (('user_count', 0), ('mailbox_matches', False), ('nextcloud_user_id_matches', False)):
            backend = FakeBackend()
            backend.identity_data[field] = value
            with self.assertRaises(closure.PreflightError):
                closure.inspect(backend, 'test-user')

    def test_incomplete_suspension_and_remaining_sessions_are_blockers(self):
        backend = FakeBackend()
        backend.account['enabled'] = True
        backend.access['nextcloud_enabled'] = True
        backend.access['mailcow_sogo_access'] = True
        backend.access['mailcow_web_sessions'] = 1
        backend.access_receipt['state'] = 'suspend-pending'
        result = closure.inspect(backend, 'test-user')
        self.assertIn('no-completed-suspension-receipt', result['observed_blockers'])
        self.assertIn('interactive-access-is-not-fully-suspended', result['observed_blockers'])
        self.assertIn('sessions-or-app-credentials-remain', result['observed_blockers'])

    def test_state_change_during_inspection_is_rejected(self):
        backend = FakeBackend()
        backend.account['enabled'] = True
        with self.assertRaises(closure.PreflightError):
            closure.inspect(backend, 'test-user')

    def test_invitation_and_sharing_dependencies_are_blockers(self):
        backend = FakeBackend()
        backend.identity_data['invitations_by_username'] = 1
        backend.resource_data['group_file_shares_received'] = 2
        backend.resource_data['published_owned_calendars'] = 1
        result = closure.inspect(backend, 'test-user')
        self.assertIn('enrollment-invitations-require-reconciliation', result['observed_blockers'])
        self.assertIn('sharing-dependencies-require-disposition', result['observed_blockers'])

    def test_mounts_and_queued_or_conflicting_requests_are_blockers(self):
        backend = FakeBackend()
        backend.mount_data['admin_external_mounts'] = 1
        backend.resource_data['requests'][0]['status'] = 'queued'
        backend.resource_data['requests'][0]['mailbox_matches'] = False
        result = closure.inspect(backend, 'test-user')
        self.assertIn('team-or-external-storage-requires-review', result['observed_blockers'])
        self.assertIn('approval-records-require-reconciliation', result['observed_blockers'])
        for requests in ([], [copy.deepcopy(backend.resource_data['requests'][0])] * 2):
            backend.resource_data['requests'] = requests
            result = closure.inspect(backend, 'test-user')
            self.assertIn('approval-records-require-reconciliation', result['observed_blockers'])

    def test_missing_or_invalid_counts_never_become_zero(self):
        for value in (None, True, -1, '0'):
            backend = FakeBackend()
            backend.resource_data['owned_calendars'] = value
            with self.assertRaises(closure.PreflightError):
                closure.inspect(backend, 'test-user')

    def test_cli_requires_root_and_rejects_commit(self):
        backend = FakeBackend()
        with patch.object(closure.os, 'geteuid', return_value=1000):
            with self.assertRaises(closure.PreflightError):
                closure.main(['--username', 'test-user'], backend=backend)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                closure.main(['--username', 'test-user', '--commit'], backend=backend)
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(backend.calls, [])

    def test_cli_produces_only_sanitized_json(self):
        output = io.StringIO()
        with patch.object(closure.os, 'geteuid', return_value=0), redirect_stdout(output):
            self.assertEqual(closure.main(['--username', 'test-user'], backend=FakeBackend()), 0)
        self.assertFalse(json.loads(output.getvalue())['ready_for_deletion'])

    def test_backend_forwards_authoritative_groups_to_helper(self):
        runner = FixtureRunner('COVIN_JSON={"group_file_shares_received":0}\n')
        backend = closure.ProductionBackend(runner=runner)
        result = backend.resources('test-user', ['everyone'])
        self.assertEqual(result['group_file_shares_received'], 0)
        args, kwargs = runner.calls[0]
        self.assertEqual(args[-2:], ['nextcloud-app', 'php'])
        self.assertEqual(json.loads(kwargs['env']['COVIN_CLOSURE_GROUPS']), ['everyone'])
        self.assertNotIn('->delete(', kwargs['input_text'])
        self.assertNotIn('executeStatement', kwargs['input_text'])
        self.assertNotIn('setupFS(', kwargs['input_text'])

    def test_unknown_mount_wrapper_is_rejected(self):
        backend = closure.ProductionBackend(runner=FixtureRunner(''))
        backend.reader = FixtureOcc({'mounts': []})
        with self.assertRaises(closure.PreflightError):
            backend.mounts('test-user')

    def test_mount_metadata_and_credentials_are_not_returned(self):
        backend = closure.ProductionBackend(runner=FixtureRunner(''))
        backend.reader = FixtureOcc([{'password': 'private', 'mount': 'private-name'}])
        result = backend.mounts('test-user')
        self.assertEqual(result, {
            'team_folders': 1, 'personal_external_mounts': 1, 'admin_external_mounts': 1,
        })
        self.assertNotIn('private', json.dumps(result))
        self.assertTrue(all('--show-password' not in args for args in backend.reader.calls))
        self.assertTrue(all('--all' not in args for args in backend.reader.calls))

    def test_duplicate_markers_are_rejected(self):
        with self.assertRaises(closure.PreflightError):
            closure.unique_marker('COVIN_JSON={}\nCOVIN_JSON={}\n', 'fixture')

    def test_readonly_adapter_refuses_mutations(self):
        backend = closure.ProductionBackend(runner=FixtureRunner(''))
        for method in (
            'set_nextcloud_enabled', 'delete_nextcloud_tokens', 'set_authentik_active',
            'delete_authentik_sessions', 'set_mailcow_access', 'delete_mailcow_app_passwords',
            'delete_mailcow_web_sessions', 'kick_mailbox',
        ):
            with self.subTest(method=method), self.assertRaises(closure.PreflightError):
                getattr(backend.reader, method)('test-user')
        with self.assertRaises(closure.PreflightError):
            backend.reader.mailcow_request('POST', '/not-used')
        with self.assertRaises(closure.PreflightError):
            backend.reader.mailcow_web_session_operation('test-user@example.test', delete=True)

    def test_backend_errors_do_not_expose_response_text(self):
        result = subprocess.CompletedProcess([], 1, 'private stdout', 'private stderr')
        with patch.object(closure.subprocess, 'run', return_value=result):
            with self.assertRaises(closure.PreflightError) as error:
                closure.SafeRunner().run(['fixture'])
        self.assertNotIn('private', str(error.exception))


if __name__ == '__main__':
    unittest.main()
