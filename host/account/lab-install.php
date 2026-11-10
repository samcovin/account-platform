<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);

// Empty, isolated instance only. Passwords enter PHP memory, not process argv.
$run = getenv('COVIN_GUARD_LAB_RUN');
$host = getenv('COVIN_GUARD_LAB_DB_HOST');
if (!is_string($run) || !preg_match('/^[a-f0-9]{24}$/D', $run)
    || $host !== 'covin-guard-db-' . $run
    || !is_file('/var/www/html/.covin-guard-lab')
    || trim(file_get_contents('/var/www/html/.covin-guard-lab')) !== $run
    || is_file('/var/www/html/config/config.php')) {
    fwrite(STDERR, "STOP: empty lab identity check failed.\n");
    exit(1);
}
$dbPassword = getenv('COVIN_GUARD_LAB_DB_PASSWORD');
$adminPassword = getenv('COVIN_GUARD_LAB_ADMIN_PASSWORD');
if (!is_string($dbPassword) || !preg_match('/^[a-f0-9]{64}$/D', $dbPassword)
    || !is_string($adminPassword) || !preg_match('/^[a-f0-9]{64}$/D', $adminPassword)) {
    fwrite(STDERR, "STOP: disposable lab credentials unavailable.\n");
    exit(1);
}
chdir('/var/www/html');
$argv = [
    'occ', 'maintenance:install', '--no-interaction', '--no-ansi',
    '--database=mysql', '--database-host=' . $host,
    '--database-name=covin_guard_lab', '--database-user=covin_guard_lab',
    '--database-pass=' . $dbPassword,
    '--admin-user=guard-lab-admin', '--admin-pass=' . $adminPassword,
    '--data-dir=/var/www/html/data',
];
$_SERVER['argv'] = $argv;
$_SERVER['argc'] = count($argv);
require '/var/www/html/console.php';
