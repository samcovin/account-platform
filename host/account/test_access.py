# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline account access tests; never contact production services."""

import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


TOOL = Path(__file__).with_name('covin-account-access.py')
spec = importlib.util.spec_from_file_location('account_access', TOOL)
access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(access)


class FakeBackend:
    def __init__(self):
        self.nextcloud_enabled = True
        self.nextcloud_token_ids = ['11', '12']
        self.authentik_active = True
        self.authentik_sessions = 2
        self.mailcow_active = True
        self.mailcow_access = {
            field: True for field in access.MAILCOW_ACCESS_FIELDS
        }
        self.mailcow_password_ids = [31, 32]
        self.mailcow_session_count = 1
        self.calls = []
        self.failure = None

    def fail(self, name):
        if self.failure == name:
            raise access.AccessError(f'simulated {name} failure')

    def nextcloud_info(self, username):
        self.fail('nextcloud-info')
        return {'enabled': self.nextcloud_enabled}

    def nextcloud_tokens(self, username):
        return list(self.nextcloud_token_ids)

    def set_nextcloud_enabled(self, username, enabled):
        self.fail('nextcloud-state')
        self.calls.append(('nextcloud-state', enabled))
        self.nextcloud_enabled = enabled

    def delete_nextcloud_tokens(self, username, token_ids):
        self.fail('nextcloud-tokens')
        self.calls.append(('nextcloud-tokens', tuple(token_ids)))
        self.nextcloud_token_ids = [item for item in self.nextcloud_token_ids
                                    if item not in token_ids]

    def authentik_info(self, username):
        return {
            'count': 1,
            'active': self.authentik_active,
            'sessions': self.authentik_sessions,
        }

    def set_authentik_active(self, username, active):
        self.fail('authentik-state')
        self.calls.append(('authentik-state', active))
        self.authentik_active = active

    def delete_authentik_sessions(self, username):
        self.fail('authentik-sessions')
        self.calls.append(('authentik-sessions', self.authentik_sessions))
        count = self.authentik_sessions
        self.authentik_sessions = 0
        return count

    def mailcow_info(self, mailbox):
        return {
            'active': self.mailcow_active,
            'access': dict(self.mailcow_access),
        }

    def set_mailcow_access(self, mailbox, state):
        self.fail('mailcow-access')
        state = access.validate_mailcow_access(state)
        self.calls.append(('mailcow-access', tuple(sorted(state.items()))))
        self.mailcow_access = dict(state)

    def mailcow_app_passwords(self, mailbox):
        return list(self.mailcow_password_ids)

    def delete_mailcow_app_passwords(self, mailbox, password_ids):
        self.fail('mailcow-passwords')
        self.calls.append(('mailcow-passwords', tuple(password_ids)))
        self.mailcow_password_ids = [item for item in self.mailcow_password_ids
                                     if item not in password_ids]

    def mailcow_web_sessions(self, mailbox):
        return self.mailcow_session_count

    def delete_mailcow_web_sessions(self, mailbox):
        self.fail('mailcow-web-sessions')
        self.calls.append(('mailcow-web-sessions', self.mailcow_session_count))
        count = self.mailcow_session_count
        self.mailcow_session_count = 0
        return count

    def kick_mailbox(self, mailbox):
        self.fail('dovecot-kick')
        self.calls.append(('dovecot-kick', mailbox))


class OutputRunner:
    def __init__(self, output):
        self.output = output

    def run(self, arguments, **kwargs):
        return self.output


class CompletedRunner:
    def __init__(self, returncode, stdout='', stderr=''):
        self.result = SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def completed(self, arguments, **kwargs):
        return self.result


class RecordingMailcowBackend(access.ProductionBackend):
    def __init__(self):
        self.current_access = {
            field: True for field in access.MAILCOW_ACCESS_FIELDS
        }
        self.requests = []

    def mailcow_request(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        if method == 'POST':
            attributes = payload['attr']
            protocols = set(attributes['protocol_access'])
            self.current_access = {
                'sogo_access': attributes['sogo_access'] == '1',
                'imap_access': 'imap' in protocols,
                'pop3_access': 'pop3' in protocols,
                'smtp_access': 'smtp' in protocols,
                'sieve_access': 'sieve' in protocols,
            }
            return [{'type': 'success'}]
        return [{
            'username': 'fixture-member@example.test',
            'active': '1',
            'attributes': {
                field: '1' if enabled else '0'
                for field, enabled in self.current_access.items()
            },
        }]


class AccessTests(unittest.TestCase):
    def simulated_root_ownership(self, root):
        real_lstat = Path.lstat

        def simulated_lstat(path, *args, **kwargs):
            result = real_lstat(path, *args, **kwargs)
            candidate = Path(path)
            if candidate == root or root in candidate.parents:
                fields = list(result)
                fields[4] = 0
                return os.stat_result(fields)
            return result

        return patch.object(Path, 'lstat', simulated_lstat)

    def run_main(self, backend, receipt_root, *arguments):
        output = io.StringIO()
        argv = [
            *arguments,
            '--username', 'fixture-member',
            '--operator', 'fixture-operator',
            '--reason', 'Offline test',
        ]
        with patch.object(access.os, 'geteuid', return_value=0), \
                patch.object(access, 'RECEIPT_ROOT', receipt_root), \
                patch.object(access, 'operation_lock',
                             return_value=nullcontext()), \
                self.simulated_root_ownership(receipt_root), \
                redirect_stdout(output):
            result = access.main(argv, backend=backend)
        self.assertEqual(result, 0)
        return json.loads(output.getvalue())

    def test_dry_run_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            root = Path(temporary) / 'receipts'
            result = self.run_main(backend, root, '--suspend')
            self.assertEqual(result['status'], 'dry-run-valid')
            self.assertTrue(result['current']['nextcloud_enabled'])
            self.assertEqual(result['current']['nextcloud_tokens'], 2)
            self.assertEqual(result['current']['mailcow_web_sessions'], 1)
            self.assertEqual(backend.calls, [])
            self.assertFalse(root.exists())

    def test_suspend_revokes_access_but_preserves_mailbox(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            root = Path(temporary) / 'receipts'
            result = self.run_main(
                backend, root, '--suspend', '--commit', '--confirm', 'SUSPEND')
            self.assertEqual(result['status'], 'suspend-complete')
            self.assertFalse(backend.nextcloud_enabled)
            self.assertFalse(backend.authentik_active)
            self.assertEqual(backend.nextcloud_token_ids, [])
            self.assertEqual(backend.authentik_sessions, 0)
            self.assertEqual(backend.mailcow_password_ids, [])
            self.assertEqual(backend.mailcow_session_count, 0)
            self.assertTrue(backend.mailcow_active)
            self.assertEqual(
                backend.mailcow_access,
                {field: False for field in access.MAILCOW_ACCESS_FIELDS})
            receipt = json.loads(
                (root / 'fixture-member.json').read_text())
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual(
                (root / 'fixture-member.json').stat().st_mode & 0o777,
                0o600)
            self.assertEqual(receipt['state'], 'suspended')
            self.assertEqual(receipt['attempts'][-1]['status'], 'complete')
            self.assertIn(
                'mailcow-web-sessions-revoked',
                receipt['attempts'][-1]['steps'])
            self.assertEqual(
                receipt['attempts'][-1]['revoked_counts'],
                {'mailcow_web_sessions': 1})
            self.assertEqual(
                receipt['mailcow_restore'],
                {field: True for field in access.MAILCOW_ACCESS_FIELDS})
            serialized = json.dumps(receipt)
            self.assertNotIn('nextcloud_token_ids', serialized)
            self.assertNotIn('mailcow_app_password_ids', serialized)
            self.assertNotIn('PHPREDIS_SESSION', serialized)
            self.assertNotIn('api_key', serialized.lower())

    def test_resume_does_not_recreate_revoked_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            backend.nextcloud_enabled = False
            backend.authentik_active = False
            backend.nextcloud_token_ids = []
            backend.authentik_sessions = 0
            backend.mailcow_password_ids = []
            backend.mailcow_session_count = 0
            backend.mailcow_access = {
                field: False for field in access.MAILCOW_ACCESS_FIELDS
            }
            restore = {
                'sogo_access': True,
                'imap_access': True,
                'pop3_access': False,
                'smtp_access': True,
                'sieve_access': False,
            }
            root = Path(temporary) / 'receipts'
            root.mkdir(mode=0o700)
            (root / 'fixture-member.json').write_text(json.dumps({
                'version': 1,
                'username': 'fixture-member',
                'mailbox': 'fixture-member@example.test',
                'state': 'suspended',
                'updated_at': None,
                'mailcow_restore': restore,
                'attempts': [],
            }) + '\n')
            (root / 'fixture-member.json').chmod(0o600)
            result = self.run_main(
                backend, root, '--resume', '--commit', '--confirm', 'RESUME')
            self.assertEqual(result['status'], 'resume-complete')
            self.assertTrue(backend.nextcloud_enabled)
            self.assertTrue(backend.authentik_active)
            self.assertEqual(backend.nextcloud_token_ids, [])
            self.assertEqual(backend.mailcow_password_ids, [])
            self.assertEqual(backend.mailcow_access, restore)

    def test_resume_without_suspension_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            backend.nextcloud_enabled = False
            backend.authentik_active = False
            backend.nextcloud_token_ids = []
            backend.authentik_sessions = 0
            backend.mailcow_password_ids = []
            backend.mailcow_access = {
                field: False for field in access.MAILCOW_ACCESS_FIELDS
            }
            root = Path(temporary) / 'receipts'
            with self.assertRaises(access.AccessError):
                self.run_main(
                    backend, root, '--resume', '--commit', '--confirm', 'RESUME')
            self.assertFalse(root.exists())

    def test_resume_without_mailcow_restore_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            root = Path(temporary) / 'receipts'
            root.mkdir(mode=0o700)
            receipt_path = root / 'fixture-member.json'
            receipt_path.write_text(json.dumps({
                'version': 1,
                'username': 'fixture-member',
                'mailbox': 'fixture-member@example.test',
                'state': 'suspend-pending',
                'updated_at': None,
                'attempts': [],
            }) + '\n')
            receipt_path.chmod(0o600)
            with self.assertRaises(access.AccessError):
                self.run_main(
                    backend, root, '--resume', '--commit', '--confirm', 'RESUME')
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt['state'], 'suspend-pending')
            self.assertEqual(receipt['attempts'], [])

    def test_failure_is_recorded_and_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            backend.failure = 'nextcloud-tokens'
            root = Path(temporary) / 'receipts'
            with self.assertRaises(access.AccessError):
                self.run_main(
                    backend, root, '--suspend', '--commit',
                    '--confirm', 'SUSPEND')
            receipt_path = root / 'fixture-member.json'
            failed = json.loads(receipt_path.read_text())
            self.assertEqual(failed['state'], 'suspend-pending')
            self.assertEqual(failed['attempts'][-1]['status'], 'failed')

            backend.failure = None
            result = self.run_main(
                backend, root, '--suspend', '--commit', '--confirm', 'SUSPEND')
            self.assertEqual(result['status'], 'suspend-complete')
            retried = json.loads(receipt_path.read_text())
            self.assertEqual(retried['state'], 'suspended')
            self.assertEqual(len(retried['attempts']), 2)

    def test_retry_preserves_original_mailcow_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            backend.failure = 'nextcloud-tokens'
            root = Path(temporary) / 'receipts'
            with self.assertRaises(access.AccessError):
                self.run_main(
                    backend, root, '--suspend', '--commit',
                    '--confirm', 'SUSPEND')
            self.assertFalse(any(backend.mailcow_access.values()))

            backend.failure = None
            self.run_main(
                backend, root, '--suspend', '--commit', '--confirm', 'SUSPEND')
            receipt = json.loads(
                (root / 'fixture-member.json').read_text())
            self.assertEqual(
                receipt['mailcow_restore'],
                {field: True for field in access.MAILCOW_ACCESS_FIELDS})

    def test_dovecot_no_users_kicked_is_successful_noop(self):
        backend = access.ProductionBackend(
            CompletedRunner(68, stderr='no users kicked\n'))
        backend.kick_mailbox('fixture-member@example.test')

    def test_dovecot_other_status_68_error_is_rejected(self):
        backend = access.ProductionBackend(
            CompletedRunner(68, stderr='unexpected failure\n'))
        with self.assertRaises(access.AccessError):
            backend.kick_mailbox('fixture-member@example.test')

    def test_mailcow_web_session_inspection_is_read_only(self):
        backend = access.ProductionBackend(OutputRunner(
            'COVIN_JSON={"before":2,"deleted":0,"remaining":2}\n'))
        self.assertEqual(
            backend.mailcow_web_sessions('fixture-member@example.test'),
            2)

    def test_mailcow_web_session_revocation_requires_zero_remaining(self):
        backend = access.ProductionBackend(OutputRunner(
            'COVIN_JSON={"before":2,"deleted":1,"remaining":1}\n'))
        with self.assertRaises(access.AccessError):
            backend.delete_mailcow_web_sessions(
                'fixture-member@example.test')

    def test_mailcow_web_session_failure_is_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            backend.failure = 'mailcow-web-sessions'
            root = Path(temporary) / 'receipts'
            with self.assertRaises(access.AccessError):
                self.run_main(
                    backend, root, '--suspend', '--commit',
                    '--confirm', 'SUSPEND')
            receipt_path = root / 'fixture-member.json'
            failed = json.loads(receipt_path.read_text())
            self.assertEqual(failed['state'], 'suspend-pending')
            self.assertEqual(failed['attempts'][-1]['status'], 'failed')
            self.assertNotIn(
                'mailcow-web-sessions-revoked',
                failed['attempts'][-1]['steps'])

            backend.failure = None
            result = self.run_main(
                backend, root, '--suspend', '--commit', '--confirm', 'SUSPEND')
            self.assertEqual(result['status'], 'suspend-complete')
            self.assertEqual(backend.mailcow_session_count, 0)

    def test_mailcow_access_update_preserves_delivery(self):
        backend = RecordingMailcowBackend()
        requested = {
            'sogo_access': False,
            'imap_access': True,
            'pop3_access': False,
            'smtp_access': True,
            'sieve_access': False,
        }
        backend.set_mailcow_access(
            'fixture-member@example.test', requested)
        method, path, payload = backend.requests[0]
        self.assertEqual((method, path), ('POST', '/api/v1/edit/mailbox'))
        self.assertEqual(payload['items'], ['fixture-member@example.test'])
        self.assertEqual(payload['attr']['active'], '1')
        self.assertEqual(payload['attr']['sogo_access'], '0')
        self.assertEqual(
            payload['attr']['protocol_access'], ['0', 'imap', 'smtp'])
        self.assertEqual(backend.current_access, requested)

    def test_inactive_mailbox_stops_before_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            backend.mailcow_active = False
            root = Path(temporary) / 'receipts'
            with self.assertRaises(access.AccessError):
                self.run_main(backend, root, '--suspend')
            self.assertEqual(backend.calls, [])
            self.assertFalse(root.exists())

    def test_commit_requires_exact_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = FakeBackend()
            with self.assertRaises(access.AccessError):
                self.run_main(
                    backend, Path(temporary), '--suspend', '--commit')
            self.assertEqual(backend.calls, [])

    def test_protected_service_account_is_rejected(self):
        backend = FakeBackend()
        with patch.object(access.os, 'geteuid', return_value=0):
            with self.assertRaises(access.AccessError):
                access.main([
                    '--suspend',
                    '--username', 'covin-export-delivery',
                    '--operator', 'fixture-operator',
                    '--reason', 'Offline test',
                ], backend=backend)
        self.assertEqual(backend.calls, [])

    def test_unexpected_nextcloud_token_object_is_rejected(self):
        backend = access.ProductionBackend(OutputRunner('{"unexpected":[]}\n'))
        with self.assertRaises(access.AccessError):
            backend.nextcloud_tokens('fixture-member')

    def test_receipt_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / 'receipts'
            root.mkdir(mode=0o700)
            target = parent / 'target.json'
            target.write_text('{}\n')
            target.chmod(0o600)
            (root / 'fixture-member.json').symlink_to(target)
            backend = FakeBackend()
            with self.assertRaises(access.AccessError):
                access.commit_action(
                    backend,
                    'suspend',
                    'fixture-member',
                    'fixture-member@example.test',
                    'fixture-operator',
                    'Offline test',
                    root,
                )
            self.assertEqual(backend.calls, [])


if __name__ == '__main__':
    unittest.main()
