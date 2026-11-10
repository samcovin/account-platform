<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);

const COVIN_INGRESS_ENDPOINT =
    'https://example.test/index.php/apps/covin_account_admin/public/requests';
const COVIN_INGRESS_SECRET_FILE = __DIR__ . '/.ingress-secret';

function page(int $status, string $title, string $message): never {
    http_response_code($status);
    header('Content-Type: text/html; charset=UTF-8');
    header('X-Robots-Tag: noindex, nofollow, noarchive, nosnippet');
    header('Cache-Control: no-store');
    $title = htmlspecialchars($title, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $message = htmlspecialchars($message, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

    echo '<!doctype html><html lang="en"><head>';
    echo '<meta charset="utf-8">';
    echo '<meta name="viewport" content="width=device-width,initial-scale=1">';
    echo '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">';
    echo "<title>{$title}</title>";
    echo '<style>
      :root{font-family:system-ui,sans-serif;color:#f7fbff;background:#071426}
      body{min-height:100vh;margin:0;padding:1rem;display:grid;place-items:center;
      background:linear-gradient(145deg,#071426,#0b2f4d 55%,#071a2c)}
      main{width:min(100%,38rem);padding:2rem;border:1px solid #ffffff2e;
      border-radius:1.4rem;background:#061626e8}
      p{color:#d3e5f2;line-height:1.6}
      a{display:inline-block;margin-top:1rem;padding:.75rem 1rem;
      border-radius:.7rem;color:#061522;background:#f5fbff;
      text-decoration:none;font-weight:700}
    </style></head><body><main>';
    echo "<h1>{$title}</h1><p>{$message}</p>";
    echo '<a href="/">Return to services</a>';
    echo '</main></body></html>';
    exit;
}

function field(string $name): ?string {
    if (!isset($_POST[$name]) || !is_string($_POST[$name])) {
        return null;
    }

    return trim($_POST[$name]);
}

function smtpReply($socket): string {
    $reply = '';

    while (($line = fgets($socket, 2048)) !== false) {
        $reply .= $line;

        if (strlen($line) < 4 || $line[3] !== '-') {
            break;
        }
    }

    return $reply;
}

function smtpCommand($socket, string $command, array $codes): void {
    fwrite($socket, $command . "\r\n");
    $reply = smtpReply($socket);
    $code = (int)substr($reply, 0, 3);

    if (!in_array($code, $codes, true)) {
        throw new RuntimeException("SMTP rejected command with code {$code}");
    }
}

function sendSmtpMessage(
    string $to,
    string $replyTo,
    string $subject,
    string $body,
    string $messagePrefix,
): void {
    $socket = @stream_socket_client(
        'tcp://postfix-mailcow:25',
        $errno,
        $error,
        10
    );

    if ($socket === false) {
        throw new RuntimeException("SMTP connection failed: {$errno}");
    }

    try {
        stream_set_timeout($socket, 10);

        $greeting = smtpReply($socket);
        if ((int)substr($greeting, 0, 3) !== 220) {
            throw new RuntimeException('Invalid SMTP greeting');
        }

        smtpCommand($socket, 'EHLO example.test', [250]);
        smtpCommand($socket, 'MAIL FROM:<requests@example.test>', [250]);
        smtpCommand($socket, "RCPT TO:<{$to}>", [250, 251]);
        smtpCommand($socket, 'DATA', [354]);

        $body = str_replace(["\r\n", "\r"], "\n", $body);
        $body = preg_replace('/^\./m', '..', $body) ?? $body;
        $body = str_replace("\n", "\r\n", $body);

        $message =
            "From: Account Services <requests@example.test>\r\n" .
            "To: {$to}\r\n" .
            "Reply-To: {$replyTo}\r\n" .
            "Subject: {$subject}\r\n" .
            'Date: ' . date(DATE_RFC2822) . "\r\n" .
            "Message-ID: <{$messagePrefix}-" . bin2hex(random_bytes(12)) .
                "@example.test>\r\n" .
            "Content-Type: text/plain; charset=UTF-8\r\n" .
            "\r\n" .
            $body .
            "\r\n.\r\n";

        fwrite($socket, $message);
        $accepted = smtpReply($socket);

        if ((int)substr($accepted, 0, 3) !== 250) {
            throw new RuntimeException('Message was not accepted');
        }

        smtpCommand($socket, 'QUIT', [221]);
    } finally {
        fclose($socket);
    }
}

function queuePublicRequest(
    string $displayName,
    string $username,
    string $contactEmail,
): bool {
    $secret = trim((string)@file_get_contents(COVIN_INGRESS_SECRET_FILE));

    if (!preg_match('/^[a-f0-9]{64}$/D', $secret)) {
        throw new RuntimeException('Public request signing secret is unavailable');
    }

    $payload = json_encode(
        [
            'displayName' => $displayName,
            'username' => $username,
            'contactEmail' => $contactEmail,
            'invitationDays' => 14,
        ],
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
    );
    $timestamp = (string)time();
    $nonce = bin2hex(random_bytes(16));
    $signature = hash_hmac(
        'sha256',
        $timestamp . "\n" . $nonce . "\n" . $payload,
        $secret
    );

    $headers = [
        'Content-Type: application/json',
        'Accept: application/json',
        'User-Agent: CovinPublicRequest/0.3.0',
        'X-Covin-Timestamp: ' . $timestamp,
        'X-Covin-Nonce: ' . $nonce,
        'X-Covin-Signature: ' . $signature,
    ];

    $context = stream_context_create([
        'http' => [
            'method' => 'POST',
            'header' => implode("\r\n", $headers),
            'content' => $payload,
            'ignore_errors' => true,
            'follow_location' => 0,
            'timeout' => 12,
        ],
        'ssl' => [
            'verify_peer' => true,
            'verify_peer_name' => true,
            'peer_name' => 'example.test',
            'SNI_enabled' => true,
        ],
    ]);

    $response = @file_get_contents(COVIN_INGRESS_ENDPOINT, false, $context);
    $responseHeaders = $http_response_header ?? [];
    $status = 0;

    foreach ($responseHeaders as $header) {
        if (preg_match('/^HTTP\/\S+\s+([0-9]{3})\b/', $header, $matches)) {
            $status = (int)$matches[1];
        }
    }

    if ($response === false || !in_array($status, [201, 202], true)) {
        throw new RuntimeException("Approval queue returned HTTP {$status}");
    }

    $decoded = json_decode($response, true, 8, JSON_THROW_ON_ERROR);

    if (!is_array($decoded) || ($decoded['accepted'] ?? false) !== true) {
        throw new RuntimeException('Approval queue returned an invalid response');
    }

    return ($decoded['created'] ?? false) === true;
}

// Server-controlled deployment opt-in; never read this from a request field.
if (getenv('ACCOUNT_PLATFORM_RUNTIME_REVIEWED') !== '1') {
    page(503, 'Service not configured', 'Account requests are not enabled on this installation.');
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    page(405, 'Method not allowed', 'Please use the account request form.');
}

$name = field('name');
$username = field('username');
$email = field('email');
$website = field('website');

if ($website !== null && $website !== '') {
    page(200, 'Request received', 'Thank you. Your request has been submitted.');
}

if (
    $name === null ||
    mb_strlen($name) < 2 ||
    mb_strlen($name) > 100 ||
    preg_match('/[\r\n]/', $name)
) {
    page(400, 'Check your name', 'Enter a name between 2 and 100 characters without line breaks.');
}

$username = mb_strtolower($username ?? '');

if (!preg_match('/^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])$/D', $username)) {
    page(
        400,
        'Check your username',
        'Use 3–64 letters, numbers, periods, underscores, or hyphens. Begin and end with a letter or number.'
    );
}

if (in_array($username, [
    'admin',
    'administrator',
    'abuse',
    'postmaster',
    'hostmaster',
    'webmaster',
    'security',
    'root',
    'mailer-daemon',
    'requests',
    'support',
    'billing',
    'noreply',
    'no-reply',
], true)) {
    page(400, 'Check your username', 'That username is reserved. Choose another username.');
}

if (
    $email === null ||
    strlen($email) > 254 ||
    preg_match('/[\r\n]/', $email) ||
    filter_var($email, FILTER_VALIDATE_EMAIL) === false
) {
    page(400, 'Check your email', 'Enter a valid current email address.');
}

try {
    $created = queuePublicRequest($name, $username, $email);
} catch (Throwable $exception) {
    error_log('Account request queue failed: ' . $exception->getMessage());
    page(
        503,
        'Request temporarily unavailable',
        'The account request service is temporarily unavailable. Please try again later.'
    );
}

$remote = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$submitted = gmdate('Y-m-d H:i:s') . ' UTC';

if ($created) {
    $adminBody =
        "New Account Services account request\n\n" .
        "Name: {$name}\n" .
        "Preferred username: {$username}\n" .
        "Current email: {$email}\n" .
        "Submitted: {$submitted}\n" .
        "Remote address: {$remote}\n\n" .
        "The request is pending in the Nextcloud Account approvals app.\n" .
        "No account has been created automatically.\n";

    try {
        sendSmtpMessage(
            'requests@example.test',
            $email,
            "Account request from {$name}",
            $adminBody,
            'request'
        );
    } catch (Throwable $exception) {
        error_log('Account request notification failed: ' . $exception->getMessage());
    }
}

$confirmationBody =
    "Hello {$name},\n\n" .
    "We received your request for the username {$username}.\n\n" .
    "The request will be reviewed manually. No account has been created yet, " .
    "and you do not need to send a password.\n\n" .
    "If the request is approved, setup instructions will be sent to this " .
    "email address.\n\n" .
    "If you did not submit this request, you may ignore this message.\n";

$confirmationSent = true;

try {
    sendSmtpMessage(
        $email,
        'requests@example.test',
        'We received your account request',
        $confirmationBody,
        'confirmation'
    );
} catch (Throwable $exception) {
    $confirmationSent = false;
    error_log('Account request confirmation failed: ' . $exception->getMessage());
}

if (!$confirmationSent) {
    page(
        200,
        'Request received',
        'Your request is awaiting manual review. The confirmation email could not be delivered, but the request is safely recorded. If approved, setup instructions will be sent to your current email address.'
    );
}

page(
    200,
    'Request received',
    'Your request is awaiting manual review and a confirmation email should arrive shortly. If you do not see it, check your spam or junk folder. If approved, setup instructions will be emailed to you.'
);
