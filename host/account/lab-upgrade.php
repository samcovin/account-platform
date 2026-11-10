<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);

// Opt-in synthetic fixtures only, after validating the isolated instance identity.
define('OC_CONSOLE', true);
$labValidated = false;

function covinUpgradeNormalizedRows(array $rows): array {
    foreach ($rows as &$row) {
        ksort($row);
        foreach ($row as &$value) {
            if ($value !== null) { $value = (string)$value; }
        }
        unset($value);
    }
    unset($row);
    usort($rows, fn($a, $b) => (int)$a['id'] <=> (int)$b['id']);
    return $rows;
}

function covinUpgradeFixtureRows(): array {
    $requests = []; $audit = [];
    foreach (['pending', 'queued', 'running', 'completed', 'failed', 'rejected', 'completed'] as $i => $status) {
        $username = 'guard-upgrade-' . ($i === 6 ? 'resend' : $status);
        $id = 1001 + $i;
        $requests[] = [
            'id' => $id, 'display_name' => 'Synthetic upgrade fixture ' . $i,
            'username' => $username, 'contact_email' => $username . '@example.invalid',
            'status' => $status, 'requested_at' => 1700000000 + $i,
            'updated_at' => 1700000100 + $i, 'reviewed_by' => 'synthetic-operator',
            'reviewed_at' => 1700000050 + $i,
            'claim_token' => $status === 'running' ? str_repeat('1', 64) : '',
            'claimed_at' => $status === 'running' ? 1700000090 : 0,
            'mailbox' => $username . '@example.invalid',
            'error_message' => $status === 'failed' ? 'Synthetic failure' : '',
            'invitation_days' => 14, 'job_type' => $i === 6 ? 'resend' : 'provision',
        ];
        $audit[] = ['id' => 2001 + $i, 'request_id' => $id,
            'actor' => 'synthetic-operator', 'action' => 'synthetic-fixture',
            'details' => 'Synthetic preserved history ' . $i, 'created_at' => 1700000200 + $i];
    }
    return ['covin_account_requests' => covinUpgradeNormalizedRows($requests),
        'covin_account_audit' => covinUpgradeNormalizedRows($audit)];
}

function covinUpgradeReadRows(\OCP\IDBConnection $db, string $table): array {
    $q = $db->getQueryBuilder();
    $q->select('*')->from($table)->orderBy('id', 'ASC');
    $r = $q->executeQuery();
    try { return covinUpgradeNormalizedRows($r->fetchAll()); }
    finally { $r->closeCursor(); }
}

try {
    $mode = $argv[1] ?? '';
    if (!in_array($mode, ['seed', 'verify'], true) || count($argv) !== 2) {
        throw new \RuntimeException('Invalid isolated upgrade mode');
    }
    $run = getenv('COVIN_GUARD_LAB_RUN');
    $host = getenv('COVIN_GUARD_LAB_DB_HOST');
    if (!is_string($run) || !preg_match('/^[a-f0-9]{24}$/D', $run)
        || $host !== 'covin-guard-db-' . $run
        || !is_file('/var/www/html/.covin-guard-lab')
        || trim(file_get_contents('/var/www/html/.covin-guard-lab')) !== $run) {
        throw new \RuntimeException('Lab identity mismatch');
    }
    foreach (glob('/var/www/html/config/*.php') as $path) {
        if (!in_array(basename($path), ['config.php', 'config.sample.php'], true)) {
            throw new \RuntimeException('Unexpected lab configuration include');
        }
    }
    require '/var/www/html/config/config.php';
    if (($CONFIG['dbhost'] ?? null) !== $host || ($CONFIG['dbname'] ?? null) !== 'covin_guard_lab'
        || ($CONFIG['dbuser'] ?? null) !== 'covin_guard_lab' || ($CONFIG['dbtype'] ?? null) !== 'mysql'
        || ($CONFIG['datadirectory'] ?? null) !== '/var/www/html/data' || ($CONFIG['installed'] ?? false) !== true) {
        throw new \RuntimeException('Generated lab configuration mismatch');
    }
    $labValidated = true;
    chdir('/var/www/html');
    require '/var/www/html/lib/base.php';
    $config = \OC::$server->get(\OCP\IConfig::class);
    $version = $config->getAppValue('covin_account_admin', 'installed_version');
    if ($config->getSystemValue('dbhost') !== $host
        || $config->getSystemValue('dbname') !== 'covin_guard_lab'
        || $version !== ($mode === 'seed' ? '0.4.0' : '0.5.0')) {
        throw new \RuntimeException('Effective lab identity/version mismatch');
    }
    $db = \OC::$server->get(\OCP\IDBConnection::class);
    $fixtures = covinUpgradeFixtureRows();
    $snapshot = '/var/www/html/data/.guard-upgrade-before.json';
    $prefix = $config->getSystemValue('dbtableprefix', 'oc_');
    if (!is_string($prefix) || !preg_match('/^[a-zA-Z0-9_]*$/D', $prefix)) {
        throw new \RuntimeException('Invalid lab table prefix');
    }
    $pdo = new \PDO('mysql:host=' . $host . ';dbname=covin_guard_lab',
        'covin_guard_lab', getenv('COVIN_GUARD_LAB_DB_PASSWORD'),
        [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
    $tableNames = array_merge(array_keys($fixtures), ['covin_account_closure', 'covin_closure_audit', 'covin_closure_gate']);
    $statement = $pdo->prepare('SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES'
        . ' WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (?, ?, ?, ?, ?)');
    $statement->execute(array_map(fn($table) => $prefix . $table, $tableNames));
    $engines = $statement->fetchAll(\PDO::FETCH_ASSOC);
    if (count($engines) !== ($mode === 'seed' ? 2 : 5)) {
        throw new \RuntimeException('Unexpected baseline/upgraded schema');
    }
    foreach ($engines as $engine) {
        if ($engine['ENGINE'] !== 'InnoDB') { throw new \RuntimeException('Nontransactional lab table'); }
    }
    if ($mode === 'seed') {
        if (file_exists($snapshot)) { throw new \RuntimeException('Fixture snapshot already exists'); }
        $db->beginTransaction();
        try {
            foreach ($fixtures as $table => $rows) {
                if (covinUpgradeReadRows($db, $table) !== []) { throw new \RuntimeException('Baseline is not empty'); }
                foreach ($rows as $row) {
                    $q = $db->getQueryBuilder(); $q->insert($table);
                    foreach ($row as $key => $value) { $q->setValue($key, $q->createNamedParameter($value)); }
                    $q->executeStatement();
                }
                if (covinUpgradeReadRows($db, $table) !== $rows) { throw new \RuntimeException('Fixture roundtrip mismatch'); }
            }
            $db->commit();
        } catch (\Throwable $error) { $db->rollBack(); throw $error; }
        $contents = json_encode(['run' => $run, 'version' => $version, 'tables' => $fixtures], JSON_THROW_ON_ERROR);
        $handle = fopen($snapshot, 'x');
        if ($handle === false) { throw new \RuntimeException('Cannot create fixture snapshot'); }
        try {
            if (!chmod($snapshot, 0600) || fwrite($handle, $contents) !== strlen($contents)) {
                throw new \RuntimeException('Cannot persist fixture snapshot');
            }
        } finally { fclose($handle); }
        echo "SYNTHETIC_UPGRADE_FIXTURES_READY\n";
        exit(0);
    }
    $before = json_decode(file_get_contents($snapshot), true, 512, JSON_THROW_ON_ERROR);
    if ($before !== ['run' => $run, 'version' => '0.4.0', 'tables' => $fixtures]) {
        throw new \RuntimeException('Fixture baseline identity/content mismatch');
    }
    foreach ($fixtures as $table => $rows) {
        if (covinUpgradeReadRows($db, $table) !== $rows) { throw new \RuntimeException('Pre-existing rows changed during upgrade'); }
    }
    foreach (['covin_account_closure', 'covin_closure_audit'] as $table) {
        $q = $db->getQueryBuilder(); $q->select('*')->from($table);
        $res = $q->executeQuery();
        try { if ($res->fetchAll() !== []) { throw new \RuntimeException('Unexpected closure records'); } }
        finally { $res->closeCursor(); }
    }
    if (covinUpgradeReadRows($db, 'covin_closure_gate') !== [['id' => '1', 'marker' => str_repeat('0', 32)]]) {
        throw new \RuntimeException('Upgrade gate initialization mismatch');
    }
    $registry = \OC::$server->get(\OCA\CovinAccountAdmin\Service\ClosureRegistry::class);
    $mapper = \OC::$server->get(\OCA\CovinAccountAdmin\Db\AccountRequestMapper::class);
    $registry->serialized(fn() => null);
    if (!$mapper->hasOpenUsername('guard-upgrade-pending')) {
        throw new \RuntimeException('Existing pending request not recognized');
    }
    foreach ($fixtures as $table => $rows) {
        if (covinUpgradeReadRows($db, $table) !== $rows) { throw new \RuntimeException('Verification changed fixture history'); }
    }
    echo json_encode(['status' => 'isolated-populated-upgrade-passed',
        'from_version' => '0.4.0', 'app_version' => '0.5.0',
        'preserved_request_rows' => 7, 'preserved_audit_rows' => 7,
        'all_existing_row_fields_preserved' => true, 'gate_row_count' => 1,
        'transactional_table_count' => 5, 'registry_and_mapper_dependency_injection' => 'passed',
        'real_concurrency_tested' => false, 'production_deployment' => false,
        'account_deletion' => false], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR), PHP_EOL;
} catch (\Throwable $error) {
    if ($labValidated) {
        $diagnostic = '/var/www/html/data/.guard-upgrade-error.txt';
        if (@file_put_contents($diagnostic, (string)$error, LOCK_EX) !== false) { @chmod($diagnostic, 0600); }
    }
    fwrite(STDERR, 'STOP: isolated upgrade check failed (' . get_class($error) . ").\n");
    exit(1);
}
