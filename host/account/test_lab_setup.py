# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline orchestration mocks; never launches Docker or installs Nextcloud."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MOCK = r'''#!/usr/bin/env python3
import io, json, os, sys, tarfile
from pathlib import Path
args = sys.argv[1:]
case = os.environ['LAB_TEST_CASE']
base = Path(os.environ['LAB_TEST_STATE'])
name = Path(sys.argv[0]).name
with (base / 'trace').open('a') as f:
    f.write(json.dumps([name] + args) + '\n')
if name == 'git':
    if 'rev-parse' in args:
        print('a' * 40)
        sys.exit(0)
    if 'diff' in args: sys.exit(1 if case == 'source-drift' else 0)
    if 'archive' in args:
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as t:
            root = Path(os.environ['LAB_TEST_SOURCE'])
            for source in (root / 'apps/covin_account_admin').rglob('*'):
                arc = str(source.relative_to(root))
                t.add(source, arcname=arc, recursive=False)
    sys.exit(0)
if name == 'chown': sys.exit(0)
if name != 'docker': sys.exit(91)
def path(resource): return base / (resource + '.json')
def read(resource): return json.loads(path(resource).read_text())
def label_value(item): return next(iter(item.values()))
if args[:2] == ['image', 'inspect']:
    image = args[2]
    volume = '/var/www/html' if image == os.environ['LAB_TEST_APP_IMAGE'] else '/var/lib/mysql'
    if case == 'image-volume': volume = '/unexpected-volume'
    print(json.dumps([{'Id': image, 'Config': {'Volumes': {volume: {}}}}]))
elif args[:2] == ['network', 'create']:
    resource = args[-1]
    key, value = args[args.index('--label') + 1].split('=', 1)
    path(resource).write_text(json.dumps({'Internal': True, 'Labels': {key: value}}))
    print('mock-network')
elif args[:2] == ['network', 'inspect']:
    resource = args[2]
    if not path(resource).exists(): sys.exit(1)
    item = read(resource)
    if '--format' in args:
        print('true' if args[-1] == '{{.Internal}}' else label_value(item['Labels']))
    else: print(json.dumps([item]))
elif args[:2] == ['network', 'rm']:
    path(args[-1]).unlink()
    print('mock-network-removed')
elif args[0] == 'run':
    resource = args[args.index('--name') + 1]
    key, value = args[args.index('--label') + 1].split('=', 1)
    network = args[args.index('--network') + 1]
    mounts = []
    for i, arg in enumerate(args):
        if arg == '--mount':
            fields = dict(pair.split('=', 1) for pair in args[i + 1].split(',') if '=' in pair)
            mounts.append({'Type': fields['type'], 'Source': fields['src'], 'Destination': fields['dst'],
                'RW': 'readonly' not in args[i + 1].split(',')})
    item = {'Name': '/' + resource, 'Config': {'Labels': {key: value}}, 'Mounts': mounts,
        'HostConfig': {'PortBindings': {}}, 'NetworkSettings': {'Networks': {network: {}}}}
    if case == 'published-port': item['HostConfig']['PortBindings'] = {'80/tcp': [{'HostPort': '9999'}]}
    if case == 'wrong-mount': item['Mounts'][0]['Source'] = '/not-a-lab-mount'
    if case == 'wrong-destination': item['Mounts'][0]['Destination'] = '/not-a-lab-destination'
    if case == 'writable-tools' and resource.startswith('covin-guard-app-'): item['Mounts'][-1]['RW'] = True
    if case == 'wrong-label': item['Config']['Labels'][key] = 'not-this-run'
    path(resource).write_text(json.dumps(item))
    if case == 'lost-run-response' and resource.startswith('covin-guard-app-'): sys.exit(1)
    print('mock-container')
elif args[0] == 'inspect':
    if '--format' in args:
        resource = args[1]
        if not path(resource).exists(): sys.exit(1)
        print(label_value(read(resource)['Config']['Labels']))
    else:
        if any(not path(resource).exists() for resource in args[1:]): sys.exit(1)
        print(json.dumps([read(resource) for resource in args[1:]]))
elif args[0] == 'exec':
    if '/lab/upgrade.php' in args and 'seed' in args and case == 'seed-fail': sys.exit(1)
    if 'occ' in args and 'upgrade' in args and case == 'upgrade-fail': sys.exit(1)
    if '/lab/upgrade.php' in args and 'verify' in args:
        report = {'status': 'isolated-populated-upgrade-passed', 'from_version': '0.4.0',
            'app_version': '0.5.0', 'preserved_request_rows': 7, 'preserved_audit_rows': 7,
            'all_existing_row_fields_preserved': True, 'gate_row_count': 1,
            'transactional_table_count': 5, 'registry_and_mapper_dependency_injection': 'passed',
            'real_concurrency_tested': False, 'production_deployment': False, 'account_deletion': False}
        if case == 'bad-upgrade-report': report['all_existing_row_fields_preserved'] = False
        print(json.dumps(report))
    if '/lab/concurrency.php' in args:
        if case == 'concurrency-fail':
            print('PRIVATE MOCK CONCURRENCY DETAILS', file=sys.stderr)
            sys.exit(1)
        report = {'status': 'isolated-concurrency-passed',
            'scenarios': ['approval', 'retry', 'resend', 'claim', 'execution', 'double-claim'],
            'contended_rounds': 12, 'observed_gate_waiters': 24,
            'unrelated_request_and_audit_preserved': True, 'separate_worker_connections': True,
            'production_deployment': False, 'account_deletion': False}
        if case == 'bad-concurrency-report': report['observed_gate_waiters'] = 23
        if case == 'wrong-report-type': report['contended_rounds'] = 12.0
        print(json.dumps(report))
    if '/lab/install.php' in args and case == 'install-timeout': sys.exit(124)
    if '/lab/install.php' in args and case == 'install-fail':
        print('PRIVATE MOCK INSTALL DETAILS', file=sys.stderr)
        sys.exit(1)
    if '/lab/verify.php' in args:
        if case == 'fresh-verification-fail': sys.exit(1)
        print(json.dumps({'status': 'isolated-migration-smoke-passed', 'app_version': '0.5.0',
            'registry_and_mapper_dependency_injection': 'passed', 'empty_request_and_audit_tables': True,
            'gate_row_count': 1, 'transactional_table_count': 5, 'empty_claim_query': 'passed',
            'real_concurrency_tested': False, 'production_deployment': False, 'account_deletion': False}))
elif args[0] == 'logs': print('PRIVATE MOCK CONTAINER LOG')
elif args[0] == 'stop':
    path(args[-1]).unlink()
    print('mock-stopped')
else: sys.exit(92)
'''


class LabSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.account = self.repo / 'host/account'
        self.account.mkdir(parents=True)
        for name in ('lab-install.php', 'lab-verify.php', 'lab-upgrade.php',
                     'lab-concurrency.php', 'lab-concurrency-checks.php'):
            (self.account / name).write_text((ROOT / 'host/account' / name).read_text())
        # Synthetic baseline for orchestration only; this is not the preserved
        # historical 0.4.0 implementation. The separate baseline checker tests
        # verify byte/mode/version provenance and copy boundaries independently.
        self.baseline = self.base / 'baseline'
        pinned = {}
        for path in (ROOT / 'apps/covin_account_admin').rglob('*'):
            if not path.is_file(): continue
            relative = path.relative_to(ROOT)
            dest = self.baseline / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            if path.name == 'info.xml': data = data.replace(b'<version>0.5.0</version>', b'<version>0.4.0</version>')
            dest.write_bytes(data)
            dest.chmod(path.stat().st_mode & 0o777)
            pinned[relative.as_posix()] = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': path.stat().st_mode & 0o777}
        (self.account / 'upgrade-baseline-0.4.0.json').write_text(json.dumps({
            'schema': 1, 'app_id': 'covin_account_admin', 'version': '0.4.0',
            'source_snapshot': 'b' * 40, 'files': pinned,
        }))
        tools = self.repo / 'tools'
        tools.mkdir()
        (tools / 'check-lab-baseline.py').write_text((ROOT / 'tools/check-lab-baseline.py').read_text())
        source = (ROOT / 'host/account/prepare-closure-lab.sh').read_text()
        # Only this throwaway fixture bypasses sudo and relocates temporary state.
        source = source.replace('$EUID -ne 0', '0 -ne 0')
        source = source.replace('/var/tmp/covin-closure-lab.', str(self.base / 'lab.'))
        self.script = self.account / 'prepare-closure-lab.sh'
        self.script.write_text(source)
        self.state = self.base / 'mock-state'
        self.state.mkdir()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ('docker', 'git', 'chown'):
            p = self.bin / name
            p.write_text(MOCK)
            p.chmod(0o700)

    def run_setup(self, case='success', args=('--create-lab', 'ISOLATED'), *, baseline_configured=True, images_configured=True):
        env = os.environ.copy()
        env.update({
            'PATH': str(self.bin) + ':' + env['PATH'], 'LAB_TEST_CASE': case,
            'LAB_TEST_STATE': str(self.state), 'LAB_TEST_SOURCE': str(ROOT),
            'LAB_TEST_APP_IMAGE': 'sha256:' + 'a' * 64,
            'COVIN_LAB_APP_IMAGE': 'sha256:' + 'a' * 64,
            'COVIN_LAB_DB_IMAGE': 'sha256:' + 'b' * 64,
            'COVIN_LAB_BASELINE_DIR': str(self.baseline),
        })
        if not baseline_configured: env.pop('COVIN_LAB_BASELINE_DIR', None)
        if not images_configured:
            env.pop('COVIN_LAB_APP_IMAGE', None)
            env.pop('COVIN_LAB_DB_IMAGE', None)
        if case == 'wrong-baseline-version':
            path = self.baseline / 'apps/covin_account_admin/appinfo/info.xml'
            path.write_bytes(path.read_bytes().replace(b'<version>0.4.0</version>', b'<version>0.5.0</version>'))
        result = subprocess.run(['bash', str(self.script), *args], env=env,
            capture_output=True, text=True, timeout=25)
        trace = self.state / 'trace'
        calls = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        return result, calls

    def assert_cleanup(self):
        self.assertEqual(list(self.state.glob('covin-guard-*.json')), [])

    def test_concurrency_mode_checks_fresh_schema_then_runs_workers(self):
        result, calls = self.run_setup(args=('--create-concurrency-lab', 'ISOLATED'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ISOLATED_CLOSURE_CONCURRENCY_PASSED', result.stdout)
        self.assertNotIn('ISOLATED_CLOSURE_MIGRATION_SMOKE_PASSED', result.stdout)
        checks = [i for i, c in enumerate(calls) if '/lab/verify.php' in c]
        races = [i for i, c in enumerate(calls) if '/lab/concurrency.php' in c]
        self.assertEqual(len(checks), 1)
        self.assertEqual(len(races), 1)
        self.assertLess(checks[0], races[0])
        call = calls[races[0]]
        self.assertEqual(call[-2:], ['/lab/concurrency.php', 'run'])
        self.assertEqual(call[call.index('-u') + 1], 'www-data')
        self.assertFalse(any('/lab/upgrade.php' in c for c in calls))
        stage = next(self.base.glob('lab.*'))
        self.assertIn('COVIN_GUARD_LAB_TEST=concurrency', (stage / 'app.env').read_text())
        for name in ('concurrency.php', 'concurrency-checks.php'):
            self.assertTrue((stage / 'tools' / name).is_file())
        self.assertEqual(json.loads((stage / 'fresh-result.json').read_text())['gate_row_count'], 1)
        self.assert_cleanup()

    def test_fresh_verification_failure_prevents_concurrency(self):
        result, calls = self.run_setup('fresh-verification-fail', args=('--create-concurrency-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('/lab/concurrency.php' in c for c in calls))
        self.assert_cleanup()

    def test_concurrency_failure_is_private_and_cleans_test_resources(self):
        result, calls = self.run_setup('concurrency-fail', args=('--create-concurrency-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('PRIVATE MOCK', result.stdout + result.stderr)
        self.assertNotIn('ISOLATED_CLOSURE_CONCURRENCY_PASSED', result.stdout)
        self.assert_cleanup()

    def test_incomplete_concurrency_evidence_cannot_pass(self):
        for case in ('bad-concurrency-report', 'wrong-report-type'):
            with self.subTest(case=case):
                result, calls = self.run_setup(case, args=('--create-concurrency-lab', 'ISOLATED'))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('ISOLATED_CLOSURE_CONCURRENCY_PASSED', result.stdout)
                self.assert_cleanup()

    def test_ordinary_fresh_mode_does_not_run_concurrency(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any('/lab/concurrency.php' in c for c in calls))
        stage = next(self.base.glob('lab.*'))
        self.assertIn('COVIN_GUARD_LAB_TEST=fresh', (stage / 'app.env').read_text())
        self.assert_cleanup()

    def test_populated_upgrade_orders_baseline_seed_upgrade_and_verification(self):
        result, calls = self.run_setup(args=('--create-upgrade-lab', 'ISOLATED'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ISOLATED_CLOSURE_POPULATED_UPGRADE_PASSED', result.stdout)
        archives = [c[c.index('archive') + 1] for c in calls if c[0] == 'git' and 'archive' in c]
        self.assertEqual(archives, ['a' * 40])
        self.assertFalse(any('main^{commit}' in c for c in calls))
        stages = []
        for i, call in enumerate(calls):
            if call[:2] != ['docker', 'exec']: continue
            if ('app:enable' in call or '/lab/upgrade.php' in call
                    or ('occ' in call and 'upgrade' in call)):
                self.assertEqual(call[call.index('-u') + 1], 'www-data')
                stages.append((i, call))
        self.assertEqual(len(stages), 4)
        self.assertIn('app:enable', stages[0][1])
        self.assertEqual(stages[1][1][-2:], ['/lab/upgrade.php', 'seed'])
        self.assertIn('upgrade', stages[2][1])
        self.assertEqual(stages[3][1][-2:], ['/lab/upgrade.php', 'verify'])
        stage = next(self.base.glob('lab.*'))
        self.assertIn('<version>0.4.0</version>', (stage / 'old-app/appinfo/info.xml').read_text())
        self.assertIn('<version>0.5.0</version>', (stage / 'html/custom_apps/covin_account_admin/appinfo/info.xml').read_text())
        self.assertEqual((stage / 'baseline-commit.txt').read_text().strip(), 'b' * 40)
        self.assert_cleanup()

    def test_wrong_upgrade_baseline_refused_before_containers(self):
        result, calls = self.run_setup('wrong-baseline-version', args=('--create-upgrade-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == 'docker' for c in calls))
        self.assert_cleanup()

    def test_upgrade_requires_explicit_baseline_before_any_docker_command(self):
        result, calls = self.run_setup(args=('--create-upgrade-lab', 'ISOLATED'), baseline_configured=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('COVIN_LAB_BASELINE_DIR', result.stderr)
        self.assertFalse(any(c[0] == 'docker' for c in calls))

    def test_cached_images_require_explicit_review_before_any_external_command(self):
        result, calls = self.run_setup(images_configured=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('COVIN_LAB_APP_IMAGE', result.stderr)
        self.assertEqual(calls, [])

    def test_altered_external_baseline_stops_before_any_docker_command(self):
        (self.baseline / 'apps/covin_account_admin/LICENSE').write_text('changed synthetic fixture')
        result, calls = self.run_setup(args=('--create-upgrade-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == 'docker' for c in calls))

    def test_seed_failure_prevents_upgrade_and_cleans_resources(self):
        result, calls = self.run_setup('seed-fail', args=('--create-upgrade-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('occ' in c and 'upgrade' in c for c in calls))
        self.assert_cleanup()

    def test_upgrade_failure_prevents_verification_and_cleans_resources(self):
        result, calls = self.run_setup('upgrade-fail', args=('--create-upgrade-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('/lab/upgrade.php' in c and 'verify' in c for c in calls))
        self.assert_cleanup()

    def test_changed_fixture_report_cannot_pass(self):
        result, calls = self.run_setup('bad-upgrade-report', args=('--create-upgrade-lab', 'ISOLATED'))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('ISOLATED_CLOSURE_POPULATED_UPGRADE_PASSED', result.stdout)
        self.assert_cleanup()

    def test_candidate_archive_uses_resolved_commit_and_records_it(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archives = [c for c in calls if c[0] == 'git' and 'archive' in c]
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0][archives[0].index('archive') + 1], 'a' * 40)
        stage = next(self.base.glob('lab.*'))
        self.assertEqual((stage / 'source-commit.txt').read_text().strip(), 'a' * 40)
        self.assertIn('exit_status=0', (stage / 'install-result.txt').read_text())

    def test_requires_explicit_isolated_opt_in(self):
        result, calls = self.run_setup(args=())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_wrong_image_volume_stops_before_creating_lab(self):
        result, calls = self.run_setup('image-volume')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.base.glob('lab.*')), [])
        self.assertFalse(any(call[1:2] == ['run'] for call in calls))

    def test_source_drift_stops_before_docker_changes(self):
        result, calls = self.run_setup('source-drift')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(call[0] == 'docker' for call in calls))

    def test_fully_mocked_setup_uses_only_new_labeled_resources_and_fresh_mounts(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        runs = [call for call in calls if call[0:2] == ['docker', 'run']]
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertIn('--rm', run)
            self.assertIn('--pull=never', run)
            self.assertNotIn('-p', run)
            self.assertNotIn('--publish', run)
            self.assertNotIn('--privileged', run)
            self.assertNotIn('--volumes-from', run)
            self.assertTrue(run[run.index('--name') + 1].startswith('covin-guard-'))
        self.assertNotIn('PRIVATE MOCK', result.stdout + result.stderr)
        self.assertNotIn('nextcloud-app', json.dumps(calls))
        self.assertNotIn('nextcloud-db', json.dumps(calls))
        stage = next(self.base.glob('lab.*'))
        self.assertEqual(stage.stat().st_mode & 0o777, 0o700)
        for name in ('app.env', 'db.env'):
            self.assertEqual((stage / name).stat().st_mode & 0o777, 0o600)
            self.assertNotIn((stage / name).read_text(), result.stdout + result.stderr)
        self.assert_cleanup()

    def test_bad_mount_or_published_ports_stop_and_cleanup_only_test_resources(self):
        for case in ('wrong-mount', 'wrong-destination', 'writable-tools', 'published-port'):
            with self.subTest(case=case):
                result, calls = self.run_setup(case)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any('/lab/install.php' in call for call in calls))
                self.assert_cleanup()

    def test_source_copy_creates_www_data_owned_files_without_recursive_chown(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        app_run = next(c for c in calls if c[:2] == ['docker', 'run']
                       and '--entrypoint' in c)
        self.assertIn('--user', app_run)
        self.assertEqual(app_run[app_run.index('--user') + 1], '33:33')
        self.assertIn('cp -a --no-preserve=ownership', app_run[-1])
        self.assertNotIn('chown -R', app_run[-1])
        stage = next(self.base.glob('lab.*'))
        ownership = [c for c in calls if c[0] == 'chown']
        self.assertEqual(ownership, [['chown', '33:33', str(stage / 'html')]])
        self.assertLess(calls.index(ownership[0]), calls.index(app_run))
        candidate_chown = [c for c in calls if c[:2] == ['docker', 'exec'] and 'chown' in c]
        self.assertEqual(len(candidate_chown), 1)
        self.assertEqual(candidate_chown[0][candidate_chown[0].index('-u') + 1], '0:0')
        self.assertEqual(candidate_chown[0][-1], '/var/www/html/custom_apps/covin_account_admin')
        application_calls = [c for c in calls if c[:2] == ['docker', 'exec']
                             and ('occ' in c or '/lab/install.php' in c
                                  or '/lab/verify.php' in c)]
        self.assertGreaterEqual(len(application_calls), 5)
        for call in application_calls:
            self.assertEqual(call[call.index('-u') + 1], 'www-data')
        self.assert_cleanup()

    def test_app_discovery_paths_are_configured_before_enabling_candidate(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        paths = [i for i, c in enumerate(calls) if 'config:system:set' in c and 'apps_paths' in c]
        enable = [i for i, c in enumerate(calls) if 'app:enable' in c]
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(enable), 1)
        self.assertLess(paths[0], enable[0])
        self.assertIn('--type=json', calls[paths[0]])

    def test_install_failure_keeps_logs_private_and_removes_test_resources(self):
        result, calls = self.run_setup('install-fail')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('PRIVATE MOCK', result.stdout + result.stderr)
        self.assert_cleanup()

    def test_install_timeout_records_status_and_prevents_app_setup(self):
        result, calls = self.run_setup('install-timeout')
        self.assertEqual(result.returncode, 124)
        self.assertIn('installation exited with status 124', result.stderr)
        self.assertFalse(any('config:system:set' in c or 'app:enable' in c for c in calls))
        stage = next(self.base.glob('lab.*'))
        evidence = dict(line.split('=', 1) for line in (stage / 'install-result.txt').read_text().splitlines())
        self.assertEqual(evidence['exit_status'], '124')
        self.assertGreaterEqual(int(evidence['elapsed_seconds']), 0)
        self.assert_cleanup()

    def test_lost_run_response_still_cleans_up_matching_test_container(self):
        result, calls = self.run_setup('lost-run-response')
        self.assertNotEqual(result.returncode, 0)
        self.assert_cleanup()

    def test_mismatched_container_labels_are_never_stopped(self):
        result, calls = self.run_setup('wrong-label')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(call[:2] == ['docker', 'stop'] for call in calls))
        self.assertFalse(any('/lab/install.php' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
