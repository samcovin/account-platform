# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Run a temporary approver copy with ALL external commands replaced by mocks."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MOCK = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
case = os.environ['GUARD_TEST_CASE']
trace = Path(os.environ['GUARD_TEST_TRACE'])
reserved = Path(os.environ['GUARD_TEST_RESERVED'])
def log(item):
    with trace.open('a') as f: f.write(item + '\n')
if name == 'logger':
    sys.exit(0)
if name == 'curl':
    sys.stdin.read()
    method = args[args.index('--request') + 1]
    output = Path(args[args.index('--output') + 1])
    log('mailcow-' + method)
    if method == 'GET':
        output.write_text(json.dumps([{'username': 'fixture-member@example.test'}] if 'resend' in case else []))
    else:
        if case == 'mailcow-fail': sys.exit(22)
        output.write_text('[{"type":"success"}]')
    sys.exit(0)
if name != 'docker': sys.exit(91)
if 'covin-account:closure-guard' in args:
    action = args[args.index('covin-account:closure-guard') + 1]
    log('guard-' + action)
    if case == 'missing-guard': sys.exit(1)
    if action == 'inspect':
        print(json.dumps({'status': 'guard-inspection', 'state': 'closing' if case == 'blocked' else 'open',
            'blocked': case == 'blocked', 'execution_reserved': case == 'already-reserved'}))
    elif action == 'begin-execution':
        if case == 'begin-refused': sys.exit(1)
        reserved.write_text('reserved')
        print('unexpected-output' if case == 'invalid-token' else 'b' * 48)
    elif action == 'end-execution':
        if case in ('release-fail', 'invalid-token'): sys.exit(1)
        if os.environ.get('COVIN_EXECUTION_TOKEN') != 'b' * 48: sys.exit(1)
        reserved.unlink()
        print('{"status":"execution-released"}')
    else: sys.exit(92)
elif 'ak' in args:
    script = args[-1]
    if 'Invitation.objects.create' in script:
        log('invitation-write')
        if case == 'invitation-fail': sys.exit(1)
        print('INVITE_URL=https://auth.example.test/if/flow/covin-account-enrollment/?itoken=offline-fixture')
    else:
        log('identity-read')
        print('AUTH_USER_EXISTS=False')
elif '/usr/sbin/sendmail' in args:
    sys.stdin.read()
    log('email-write')
    if case == 'email-fail': sys.exit(1)
else: sys.exit(93)
'''


class ApproverGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ('docker', 'curl', 'logger'):
            p = self.bin / name
            p.write_text(MOCK)
            p.chmod(0o700)
        mailcow = self.base / 'mailcow'
        mailcow.mkdir()
        (mailcow / 'mailcow.conf').write_text('API_KEY=offline-fixture\n')
        authentik = self.base / 'authentik'
        authentik.mkdir()
        source = (ROOT / 'host/worker/covin-approve-account').read_text()
        source = source.replace("MAILCOW_DIR='/opt/mailcow-dockerized'", f"MAILCOW_DIR='{mailcow}'")
        source = source.replace("AUTHENTIK_DIR='/opt/authentik'", f"AUTHENTIK_DIR='{authentik}'")
        source = source.replace('if [[ $EUID -ne 0 ]]; then', 'if false; then')
        source = source.replace('/tmp/covin-approval.', str(self.base / 'approval.'))
        self.script = self.base / 'approver'
        self.script.write_text(source)
        self.trace = self.base / 'trace'
        self.reserved = self.base / 'reserved'

    def run_approver(self, case, mode='--worker-commit'):
        env = os.environ.copy()
        env.update({
            'PATH': str(self.bin) + ':' + env['PATH'],
            'GUARD_TEST_CASE': case,
            'GUARD_TEST_TRACE': str(self.trace),
            'GUARD_TEST_RESERVED': str(self.reserved),
            'COVIN_APPROVE_USERNAME': 'fixture-member',
            'COVIN_APPROVE_DISPLAY_NAME': 'Offline Fixture',
            'COVIN_APPROVE_CONTACT_EMAIL': 'fixture@example.test',
            'COVIN_WORKER_CONFIRM': 'APPROVE',
            'ACCOUNT_PLATFORM_RUNTIME_REVIEWED': '1',
        })
        result = subprocess.run(['bash', str(self.script), mode], env=env,
            input='fixture-member\nOffline Fixture\nfixture@example.test\nAPPROVE\n',
            capture_output=True, text=True, timeout=20)
        events = self.trace.read_text().splitlines() if self.trace.exists() else []
        return result, events

    def assert_no_writes(self, events):
        self.assertNotIn('mailcow-POST', events)
        self.assertNotIn('invitation-write', events)
        self.assertNotIn('email-write', events)

    def test_closed_policy_and_missing_guard_stop_before_service_calls(self):
        for case in ('blocked', 'missing-guard', 'already-reserved'):
            with self.subTest(case=case):
                if self.trace.exists(): self.trace.unlink()
                result, events = self.run_approver(case)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events, ['guard-inspect'])
                self.assert_no_writes(events)

    def test_execution_refusal_after_preflight_has_no_writes(self):
        result, events = self.run_approver('begin-refused')
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes(events)
        self.assertFalse(self.reserved.exists())

    def test_invalid_token_stops_writes_and_retains_reservation(self):
        result, events = self.run_approver('invalid-token')
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes(events)
        self.assertTrue(self.reserved.exists())
        self.assertNotIn('guard-end-execution', events)

    def test_success_reserves_before_writes_and_releases_last(self):
        result, events = self.run_approver('success')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertLess(events.index('guard-begin-execution'), events.index('mailcow-POST'))
        self.assertEqual(events[-1], 'guard-end-execution')
        self.assertFalse(self.reserved.exists())
        self.assertNotIn('b' * 48, result.stdout + result.stderr)

    def test_manual_approver_also_uses_execution_reservation(self):
        result, events = self.run_approver('success', '--commit')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertLess(events.index('guard-begin-execution'), events.index('mailcow-POST'))
        self.assertEqual(events[-1], 'guard-end-execution')

    def test_failure_keeps_execution_reserved(self):
        for case in ('mailcow-fail', 'invitation-fail', 'email-fail'):
            with self.subTest(case=case):
                if self.trace.exists(): self.trace.unlink()
                result, events = self.run_approver(case)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(self.reserved.exists())
                self.assertNotIn('guard-end-execution', events)
                self.assertTrue(list(self.base.glob('approval.*')))

    def test_release_failure_is_nonzero_and_keeps_protected_diagnostics(self):
        result, events = self.run_approver('release-fail')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.reserved.exists())
        self.assertTrue(list(self.base.glob('approval.*')))

    def test_worker_dry_run_has_no_reservation_or_writes(self):
        result, events = self.run_approver('success', '--worker-dry-run')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn('guard-begin-execution', events)
        self.assertFalse(self.reserved.exists())
        self.assert_no_writes(events)

    def test_resend_also_reserves_before_invitation_or_email(self):
        result, events = self.run_approver('resend-success', '--worker-resend')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn('mailcow-POST', events)
        self.assertLess(events.index('guard-begin-execution'), events.index('invitation-write'))
        self.assertEqual(events[-1], 'guard-end-execution')


if __name__ == '__main__':
    unittest.main()
