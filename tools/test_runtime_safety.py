# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Source-run refusal checks; no real service/container commands are allowed."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    spec = importlib.util.spec_from_file_location('safety_' + Path(relative).stem.replace('-', '_'), ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeSafetyTests(unittest.TestCase):
    def test_shell_entrypoints_refuse_before_any_command_or_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            trace = base / 'unexpected-command'
            for name in ('docker', 'curl', 'sudo', 'flock', 'mktemp', 'jq', 'logger'):
                path = base / name
                path.write_text('#!/bin/sh\nprintf "called\\n" >> "$SAFETY_TRACE"\nexit 97\n')
                path.chmod(0o700)
            env = {**os.environ, 'PATH': str(base) + ':' + os.environ['PATH'], 'SAFETY_TRACE': str(trace)}
            env.pop('ACCOUNT_PLATFORM_RUNTIME_REVIEWED', None)
            for relative in ('host/worker/covin-account-worker', 'host/worker/covin-approve-account',
                             'host/account/check-closure-guards.sh'):
                with self.subTest(entrypoint=relative):
                    result = subprocess.run(['bash', str(ROOT / relative)], env=env,
                                            capture_output=True, text=True, timeout=5)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1', result.stderr)
                    self.assertFalse(trace.exists())

    def test_export_clis_refuse_before_root_runtime_files_or_services(self):
        cases = [
            ('host/export/covin-account-export.py', ['fixture-user']),
            ('host/export/covin-export-delivery.py', ['--export-dir', '/unused-fixture',
                '--request-id', 'fixture', '--display-name', 'Fixture', '--recipient', 'fixture@example.test']),
            ('host/export/covin-export-cleanup.py', ['--dry-run']),
        ]
        for relative, arguments in cases:
            with self.subTest(entrypoint=relative):
                module = load(relative)
                env = {k: v for k, v in os.environ.items() if k != 'ACCOUNT_PLATFORM_RUNTIME_REVIEWED'}
                with patch.dict(os.environ, env, clear=True), patch.object(sys, 'argv', [relative, *arguments]), \
                     patch.object(module.os, 'geteuid', side_effect=AssertionError('root check reached before opt-in')):
                    with self.assertRaisesRegex(RuntimeError, 'ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1'):
                        module.main()

    def test_access_cli_refuses_before_constructing_production_backend(self):
        module = load('host/account/covin-account-access.py')
        env = {k: v for k, v in os.environ.items() if k != 'ACCOUNT_PLATFORM_RUNTIME_REVIEWED'}
        with patch.dict(os.environ, env, clear=True), patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module, 'ProductionBackend') as backend:
            with self.assertRaisesRegex(module.AccessError, 'ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1'):
                module.main(['--suspend', '--username', 'fixture-user', '--operator', 'fixture-operator',
                             '--reason', 'offline safety fixture'])
            backend.assert_not_called()

    def test_readonly_preflight_refuses_before_constructing_production_backend(self):
        module = load('host/account/covin-account-closure-preflight.py')
        env = {k: v for k, v in os.environ.items() if k != 'ACCOUNT_PLATFORM_RUNTIME_REVIEWED'}
        with patch.dict(os.environ, env, clear=True), patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module, 'ProductionBackend') as backend:
            with self.assertRaisesRegex(module.PreflightError, 'ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1'):
                module.main(['--username', 'fixture-user'])
            backend.assert_not_called()

    def test_worker_does_not_echo_invalid_service_response(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = (ROOT / 'host/worker/covin-account-worker').read_text()
            source = source.replace("LOCK_FILE='/run/lock/covin-account-worker.lock'", f"LOCK_FILE='{base / 'worker.lock'}'")
            script = base / 'worker'
            script.write_text(source)
            docker = base / 'docker'
            docker.write_text('#!/bin/sh\nprintf "fixture-private-response\\n"\n')
            docker.chmod(0o700)
            env = {**os.environ, 'PATH': str(base) + ':' + os.environ['PATH'],
                   'ACCOUNT_PLATFORM_RUNTIME_REVIEWED': '1'}
            result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid JSON', result.stdout)
            self.assertNotIn('fixture-private-response', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
