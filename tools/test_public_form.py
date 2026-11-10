# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Real PHP/HTTP tests using only disposable, owned loopback HTTP/SMTP fixtures.

The throwaway handler copy changes only its ingress URL and SMTP target. This
does not start Nextcloud/Mailcow, send real mail, or test production TLS/FPM.
"""
import hashlib
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]


class LocalIngress(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.calls.append({'method': 'GET', 'path': self.path})
        self.send_response(500)
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        stamp = self.headers.get('X-Covin-Timestamp', '')
        nonce = self.headers.get('X-Covin-Nonce', '')
        expected = hmac.new(self.server.secret.encode(), stamp.encode() + b'\n' + nonce.encode() + b'\n' + body,
                            hashlib.sha256).hexdigest()
        signature_valid = hmac.compare_digest(expected, self.headers.get('X-Covin-Signature', ''))
        self.server.calls.append({'method': 'POST', 'path': self.path, 'signature_valid': signature_valid,
                                  'payload': json.loads(body)})
        mode = self.server.mode
        status = 403 if mode == 'reject' else 302 if mode == 'redirect' else 201
        response = (b'fixture-private-response' if mode in ('reject', 'malformed')
                    else json.dumps({'accepted': True, 'created': mode != 'existing'}).encode())
        self.send_response(status)
        if mode == 'redirect':
            self.send_header('Location', f'http://127.0.0.1:{self.server.server_port}/must-not-follow')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class LocalSMTP(socketserver.StreamRequestHandler):
    def handle(self):
        self.server.connections.append(True)
        self.request.settimeout(3)
        self.wfile.write(b'220 fixture SMTP\r\n')
        while True:
            line = self.rfile.readline(8192)
            if not line:
                break
            command = line.split(b' ', 1)[0].strip().upper()
            if command == b'EHLO':
                self.wfile.write(b'250-fixture\r\n250 OK\r\n')
            elif command in (b'MAIL', b'RCPT'):
                self.wfile.write(b'550 fixture refused\r\n' if self.server.fail else b'250 OK\r\n')
            elif command == b'DATA':
                self.wfile.write(b'354 data\r\n')
                data = []
                while True:
                    item = self.rfile.readline(65536)
                    if not item or item == b'.\r\n':
                        break
                    data.append(item)
                self.server.messages.append(b''.join(data))
                self.wfile.write(b'250 stored in fixture memory only\r\n')
            elif command == b'QUIT':
                self.wfile.write(b'221 bye\r\n')
                break
            else:
                self.wfile.write(b'500 fixture unsupported\r\n')


class SMTPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True


class PublicFormHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.php = os.environ.get('ACCOUNT_PLATFORM_TEST_PHP') or shutil.which('php')
        if not cls.php:
            raise unittest.SkipTest('PHP CLI unavailable; set ACCOUNT_PLATFORM_TEST_PHP to run real local form tests')
        result = subprocess.run([cls.php, '-n', '-r', 'exit(extension_loaded("mbstring") ? 0 : 1);'],
                                capture_output=True, timeout=5)
        if result.returncode:
            raise unittest.SkipTest('The isolated PHP CLI needs mbstring available with -n')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='account-platform-form-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.secret = 'a' * 64  # Synthetic fixture only; never a deployment key.
        self.ingress = ThreadingHTTPServer(('127.0.0.1', 0), LocalIngress)
        self.ingress.daemon_threads = True
        self.ingress.secret = self.secret
        self.ingress.mode = 'created'
        self.ingress.calls = []
        self.smtp = SMTPServer(('127.0.0.1', 0), LocalSMTP)
        self.smtp.messages = []
        self.smtp.connections = []
        self.smtp.fail = False
        for server in (self.ingress, self.smtp):
            threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        source = (ROOT / 'public/data/web/example.test/request-account/submit.php').read_text()
        old_url = 'https://example.test/index.php/apps/covin_account_admin/public/requests'
        old_smtp = 'tcp://postfix-mailcow:25'
        self.assertEqual(source.count(old_url), 1)
        self.assertEqual(source.count(old_smtp), 1)
        source = source.replace(old_url, f'http://127.0.0.1:{self.ingress.server_port}/ingress')
        source = source.replace(old_smtp, f'tcp://127.0.0.1:{self.smtp.server_address[1]}')
        (self.base / 'submit.php').write_text(source)
        (self.base / '.ingress-secret').write_text(self.secret)
        (self.base / '.ingress-secret').chmod(0o600)
        # Expose only the handler, never fixture secrets or logs as static files.
        (self.base / 'router.php').write_text("<?php\n"
            "if (parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) !== '/submit.php') { http_response_code(404); exit; }\n"
            "require __DIR__ . '/submit.php';\n")
        self.process = None
        self.addCleanup(self.stop_php)
        self.start_php('1')

    def stop_php(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.process = None
        if hasattr(self, 'log_handle'):
            self.log_handle.close()

    def start_php(self, reviewed):
        self.stop_php()
        env = {**os.environ}
        env.pop('ACCOUNT_PLATFORM_RUNTIME_REVIEWED', None)
        env.pop('PHP_CLI_SERVER_WORKERS', None)
        if reviewed is not None:
            env['ACCOUNT_PLATFORM_RUNTIME_REVIEWED'] = reviewed
        log = self.base / 'server-output.txt'
        self.log_handle = log.open('w')
        # Port 0 is assigned atomically by PHP/the kernel; no free-port race or
        # connection to a pre-existing localhost service is involved.
        self.process = subprocess.Popen([self.php, '-n', '-d', 'allow_url_fopen=1',
            '-S', '127.0.0.1:0', '-t', str(self.base), str(self.base / 'router.php')],
            env=env, stdout=self.log_handle, stderr=self.log_handle)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail('Isolated PHP fixture failed to start; check loopback/runtime permissions')
            match = re.search(r'http://127\.0\.0\.1:([1-9][0-9]*)', log.read_text())
            if match:
                self.port = int(match[1])
                return
            time.sleep(0.02)
        self.fail('Isolated PHP fixture startup timed out')

    def request(self, fields=None, method='POST'):
        if fields is None:
            fields = {'name': 'Fixture Member', 'username': 'fixture-member',
                      'email': 'fixture@example.test', 'website': ''}
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request(method, '/submit.php', urlencode(fields),
                               {'Content-Type': 'application/x-www-form-urlencoded'})
            response = connection.getresponse()
            body = response.read().decode()
            headers = dict(response.getheaders())
            self.assertEqual(headers.get('Cache-Control'), 'no-store')
            self.assertIn('noindex', headers.get('X-Robots-Tag', ''))
            return response.status, headers, body
        finally:
            connection.close()

    def assert_no_service_calls(self):
        self.assertEqual(self.ingress.calls, [])
        self.assertEqual(self.smtp.messages, [])
        self.assertEqual(self.smtp.connections, [])

    def test_unset_runtime_opt_in_refuses_valid_post_without_service_calls(self):
        self.start_php(None)
        status, _, body = self.request()
        self.assertEqual(status, 503)
        self.assertIn('Service not configured', body)
        self.assert_no_service_calls()

    def test_zero_runtime_opt_in_refuses(self):
        self.start_php('0')
        self.assertEqual(self.request()[0], 503)
        self.assert_no_service_calls()

    def test_non_exact_runtime_opt_in_refuses(self):
        self.start_php('true')
        self.assertEqual(self.request()[0], 503)
        self.assert_no_service_calls()

    def test_request_field_cannot_enable_server_opt_in(self):
        self.start_php(None)
        status, _, _ = self.request({'ACCOUNT_PLATFORM_RUNTIME_REVIEWED': '1'})
        self.assertEqual(status, 503)
        self.assert_no_service_calls()

    def test_enabled_get_is_rejected_before_services(self):
        status, headers, _ = self.request(method='GET')
        self.assertEqual(status, 405)
        self.assertEqual(headers.get('Allow'), 'POST')
        self.assert_no_service_calls()

    def test_invalid_name_is_rejected_before_services(self):
        status, _, _ = self.request({'name': 'X', 'username': 'fixture-member', 'email': 'fixture@example.test'})
        self.assertEqual(status, 400)
        self.assert_no_service_calls()

    def test_reserved_username_is_rejected_before_services(self):
        status, _, _ = self.request({'name': 'Fixture Member', 'username': 'admin', 'email': 'fixture@example.test'})
        self.assertEqual(status, 400)
        self.assert_no_service_calls()

    def test_email_header_injection_is_rejected_before_services(self):
        status, _, _ = self.request({'name': 'Fixture Member', 'username': 'fixture-member',
                                    'email': 'fixture@example.test\r\nBcc: other@example.test'})
        self.assertEqual(status, 400)
        self.assert_no_service_calls()

    def test_array_email_is_rejected_before_services(self):
        status, _, _ = self.request({'name': 'Fixture Member', 'username': 'fixture-member', 'email[]': 'fixture@example.test'})
        self.assertEqual(status, 400)
        self.assert_no_service_calls()

    def test_honeypot_is_accepted_without_services(self):
        self.assertEqual(self.request({'website': 'fixture-bot'})[0], 200)
        self.assert_no_service_calls()

    def test_enabled_valid_post_signs_ingress_and_sends_only_fixture_messages(self):
        status, _, body = self.request()
        self.assertEqual(status, 200)
        self.assertIn('awaiting manual review', body)
        self.assertEqual(len(self.ingress.calls), 1)
        self.assertTrue(self.ingress.calls[0]['signature_valid'])
        self.assertEqual(self.ingress.calls[0]['payload']['username'], 'fixture-member')
        self.assertEqual(len(self.smtp.messages), 2)
        self.assertNotIn(self.secret, body)

    def test_existing_request_does_not_send_duplicate_admin_notification(self):
        self.ingress.mode = 'existing'
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(len(self.smtp.messages), 1)

    def test_missing_signing_fixture_fails_closed(self):
        (self.base / '.ingress-secret').unlink()
        self.assertEqual(self.request()[0], 503)
        self.assert_no_service_calls()

    def test_rejected_ingress_is_generic_and_sends_no_mail(self):
        self.ingress.mode = 'reject'
        status, _, body = self.request()
        self.assertEqual(status, 503)
        self.assertNotIn('fixture-private-response', body)
        self.assertEqual(self.smtp.messages, [])

    def test_malformed_ingress_is_generic_and_sends_no_mail(self):
        self.ingress.mode = 'malformed'
        status, _, body = self.request()
        self.assertEqual(status, 503)
        self.assertNotIn('fixture-private-response', body)
        self.assertEqual(self.smtp.messages, [])

    def test_ingress_redirect_is_not_followed(self):
        self.ingress.mode = 'redirect'
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(len(self.ingress.calls), 1)
        self.assertEqual(self.smtp.messages, [])

    def test_smtp_failure_does_not_lose_queued_request_or_disclose_backend_error(self):
        self.smtp.fail = True
        status, _, body = self.request()
        self.assertEqual(status, 200)
        self.assertIn('request is safely recorded', body)
        self.assertEqual(len(self.ingress.calls), 1)
        self.assertNotIn('fixture refused', body)
        self.assertEqual(self.smtp.messages, [])


if __name__ == '__main__':
    unittest.main()
