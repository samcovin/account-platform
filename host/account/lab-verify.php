<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);

define('OC_CONSOLE', true);
$labValidated = false;

try {
    $run = getenv('COVIN_GUARD_LAB_RUN');
    $host = getenv('COVIN_GUARD_LAB_DB_HOST');
    if (!is_string($run) || !preg_match('/^[a-f0-9]{24}$/D', $run)
        || $host !== 'covin-guard-db-' . $run
        || !is_file('/var/www/html/.covin-guard-lab')
        || trim(file_get_contents('/var/www/html/.covin-guard-lab')) !== $run) {
        throw new \RuntimeException('Lab identity mismatch');
    }
    // Refuse additional configuration includes before any Nextcloud bootstrap.
    foreach (glob('/var/www/html/config/*.php') as $path) {
        if (!in_array(basename($path), ['config.php', 'config.sample.php'], true)) {
            throw new \RuntimeException('Unexpected lab configuration include');
        }
    }
    require '/var/www/html/config/config.php';
    if (($CONFIG['dbhost'] ?? null) !== $host
        || ($CONFIG['dbname'] ?? null) !== 'covin_guard_lab'
        || ($CONFIG['dbuser'] ?? null) !== 'covin_guard_lab'
        || ($CONFIG['dbtype'] ?? null) !== 'mysql'
        || ($CONFIG['datadirectory'] ?? null) !== '/var/www/html/data'
        || ($CONFIG['installed'] ?? false) !== true) {
        throw new \RuntimeException('Generated database/storage configuration mismatch');
    }
    $labValidated = true;
    chdir('/var/www/html');
    require '/var/www/html/lib/base.php';
    $config = \OC::$server->get(\OCP\IConfig::class);
    if ($config->getSystemValue('dbhost') !== $host
        || $config->getSystemValue('dbname') !== 'covin_guard_lab'
        || $config->getAppValue('covin_account_admin', 'installed_version') !== '0.5.0') {
        throw new \RuntimeException('Effective lab configuration/app version mismatch');
    }
    $registry = \OC::$server->get(\OCA\CovinAccountAdmin\Service\ClosureRegistry::class);
    $mapper = \OC::$server->get(\OCA\CovinAccountAdmin\Db\AccountRequestMapper::class);
    $db = \OC::$server->get(\OCP\IDBConnection::class);
    $counts = [];
    foreach (['covin_account_requests', 'covin_account_audit', 'covin_account_closure',
        'covin_closure_audit', 'covin_closure_gate'] as $table) {
        $q = $db->getQueryBuilder();
        $q->select('*')->from($table);
        $r = $q->executeQuery();
        $counts[$table] = count($r->fetchAll());
        $r->closeCursor();
    }
    if ($counts !== [
        'covin_account_requests' => 0, 'covin_account_audit' => 0,
        'covin_account_closure' => 0, 'covin_closure_audit' => 0,
        'covin_closure_gate' => 1,
    ]) {
        fwrite(STDERR, 'LAB_TABLE_COUNTS=' . json_encode($counts, JSON_THROW_ON_ERROR) . PHP_EOL);
        throw new \RuntimeException('Lab is not empty or migration/gate initialization failed');
    }
    $registry->serialized(fn() => null);
    if ($mapper->claimNext() !== null || $mapper->hasOpenUsername('guard-lab-member')) {
        throw new \RuntimeException('Unexpected empty-queue result');
    }
    $prefix = $config->getSystemValue('dbtableprefix', 'oc_');
    if (!is_string($prefix) || !preg_match('/^[a-zA-Z0-9_]*$/D', $prefix)) {
        throw new \RuntimeException('Unexpected lab prefix');
    }
    $pdo = new \PDO('mysql:host=' . $host . ';dbname=covin_guard_lab',
        'covin_guard_lab', getenv('COVIN_GUARD_LAB_DB_PASSWORD'),
        [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
    $statement = $pdo->prepare('SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES'
        . ' WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (?, ?, ?, ?, ?)');
    $statement->execute(array_map(fn($table) => $prefix . $table, array_keys($counts)));
    $engines = $statement->fetchAll(\PDO::FETCH_ASSOC);
    if (count($engines) !== 5) {
        throw new \RuntimeException('Missing lab tables');
    }
    foreach ($engines as $engine) {
        if ($engine['ENGINE'] !== 'InnoDB') {
            throw new \RuntimeException('Nontransactional test table');
        }
    }
    echo json_encode([
        'status' => 'isolated-migration-smoke-passed',
        'app_version' => '0.5.0',
        'registry_and_mapper_dependency_injection' => 'passed',
        'empty_request_and_audit_tables' => true,
        'gate_row_count' => 1,
        'transactional_table_count' => 5,
        'empty_claim_query' => 'passed',
        'real_concurrency_tested' => false,
        'production_deployment' => false,
        'account_deletion' => false,
    ], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR), PHP_EOL;
} catch (\Throwable $error) {
    // Details stay in isolated private logs; never expose credentials/configuration.
    if ($labValidated) {
        $diagnostic = '/var/www/html/data/.guard-lab-verify-error.txt';
        if (@file_put_contents($diagnostic, (string)$error, LOCK_EX) !== false) {
            @chmod($diagnostic, 0600);
        }
    }
    fwrite(STDERR, 'STOP: isolated migration smoke failed (' . get_class($error) . ").\n");
    exit(1);
}
