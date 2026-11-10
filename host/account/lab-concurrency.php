<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);
define('OC_CONSOLE', true);
require __DIR__ . '/concurrency-checks.php';
$labValidated = false;
$children = [];
$pdo = null;

function covinLabJson(string $path, array $value): void {
    $text = json_encode($value, JSON_THROW_ON_ERROR);
    if (file_put_contents($path . '.tmp', $text, LOCK_EX) !== strlen($text)
        || !chmod($path . '.tmp', 0600) || !rename($path . '.tmp', $path)) {
        throw new \RuntimeException('Cannot write isolated process evidence');
    }
}
function covinLabRead(string $path): array {
    return json_decode(file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
}
function covinLabWait(callable $check): void {
    $deadline = microtime(true) + 25;
    do {
        if ($check()) { return; }
        usleep(100000);
    } while (microtime(true) < $deadline);
    throw new \RuntimeException('Isolated process synchronization timed out');
}
function covinLabRows(\PDO $pdo, string $table, string $where = '', array $parameters = []): array {
    $q = $pdo->prepare('SELECT * FROM `' . $table . '` ' . $where);
    $q->execute($parameters);
    return $q->fetchAll(\PDO::FETCH_ASSOC);
}

try {
    umask(0077);
    $mode = $argv[1] ?? '';
    if (!in_array($mode, ['run', 'worker'], true)) { throw new \RuntimeException('Invalid concurrency mode'); }
    $run = getenv('COVIN_GUARD_LAB_RUN'); $host = getenv('COVIN_GUARD_LAB_DB_HOST');
    if (!is_string($run) || !preg_match('/^[a-f0-9]{24}$/D', $run)
        || getenv('COVIN_GUARD_LAB_TEST') !== 'concurrency'
        || $host !== 'covin-guard-db-' . $run
        || !is_file('/var/www/html/.covin-guard-lab')
        || trim(file_get_contents('/var/www/html/.covin-guard-lab')) !== $run) {
        throw new \RuntimeException('Isolated concurrency identity mismatch');
    }
    foreach (glob('/var/www/html/config/*.php') as $path) {
        if (!in_array(basename($path), ['config.php', 'config.sample.php'], true)) {
            throw new \RuntimeException('Unexpected lab configuration include');
        }
    }
    require '/var/www/html/config/config.php';
    if (($CONFIG['dbhost'] ?? '') !== $host || ($CONFIG['dbname'] ?? '') !== 'covin_guard_lab'
        || ($CONFIG['dbuser'] ?? '') !== 'covin_guard_lab' || ($CONFIG['dbtype'] ?? '') !== 'mysql'
        || ($CONFIG['datadirectory'] ?? '') !== '/var/www/html/data' || ($CONFIG['installed'] ?? false) !== true) {
        throw new \RuntimeException('Isolated configuration mismatch');
    }
    $labValidated = true;
    chdir('/var/www/html'); require '/var/www/html/lib/base.php';
    $config = \OC::$server->get(\OCP\IConfig::class);
    if ($config->getSystemValue('dbhost') !== $host || $config->getSystemValue('dbname') !== 'covin_guard_lab'
        || $config->getAppValue('covin_account_admin', 'installed_version') !== '0.5.0') {
        throw new \RuntimeException('Effective isolated configuration/version mismatch');
    }
    $prefix = $config->getSystemValue('dbtableprefix', 'oc_');
    if (!is_string($prefix) || !preg_match('/^[a-zA-Z0-9_]*$/D', $prefix)) { throw new \RuntimeException('Invalid table prefix'); }
    $dir = '/var/www/html/data/.guard-concurrency-' . $run;
    $db = \OC::$server->get(\OCP\IDBConnection::class);
    $registry = \OC::$server->get(\OCA\CovinAccountAdmin\Service\ClosureRegistry::class);
    $mapper = \OC::$server->get(\OCA\CovinAccountAdmin\Db\AccountRequestMapper::class);
    if ($mode === 'worker') {
        $ticket = $argv[2] ?? '';
        if (count($argv) !== 3 || !preg_match('/^[0-9]{1,2}-[ab]$/D', $ticket) || !is_dir($dir)) {
            throw new \RuntimeException('Invalid worker identity');
        }
        $job = covinLabRead($dir . '/' . $ticket . '.job.json');
        if ($job['run'] !== $run || !preg_match('/^guard-race-[0-9]{1,2}$/D', $job['username'])
            || !is_int($job['id']) || $job['id'] < 1000 || $job['id'] > 2000) {
            throw new \RuntimeException('Invalid synthetic worker manifest');
        }
        $db->executeStatement('SET SESSION innodb_lock_wait_timeout = 60');
        $connection = (int)$db->executeQuery('SELECT CONNECTION_ID()')->fetchOne();
        covinLabJson($dir . '/' . $ticket . '.ready.json', ['connection_id' => $connection]);
        try {
            switch ($job['operation']) {
                case 'approval': $ok = $mapper->queueForApproval($job['id'], 'synthetic-operator'); break;
                case 'retry': $ok = $mapper->retry($job['id'], 'synthetic-operator'); break;
                case 'resend': $ok = $mapper->queueForResend($job['id'], 'synthetic-operator', 14); break;
                case 'freeze': $mapper->freezeUsername($job['username'], 'synthetic-operator', 'Isolated race'); $ok = true; break;
                case 'execution': $registry->beginExecution($job['username']); $ok = true; break;
                case 'claim':
                    $claimed = $mapper->claimNext();
                    $result = $claimed === null ? ['outcome' => 'none'] : ['outcome' => 'claimed', 'id' => (int)$claimed->getId()];
                    break;
                default: throw new \RuntimeException('Unknown synthetic operation');
            }
            if (!isset($result)) { $result = ['outcome' => $ok ? 'accepted' : 'refused']; }
        } catch (\RuntimeException $error) {
            $allowed = match ($job['operation']) {
                'freeze' => ['A claimed job is still running', 'Exactly one completed account request required', 'An approver execution is still reserved'],
                'execution' => ['Approval is blocked or already reserved'],
                default => [],
            };
            if (!in_array($error->getMessage(), $allowed, true)) { throw $error; }
            $result = ['outcome' => 'refused'];
        }
        covinLabJson($dir . '/' . $ticket . '.result.json', $result);
        exit(0);
    }
    if (count($argv) !== 2 || !function_exists('proc_open') || file_exists($dir) || !mkdir($dir, 0700)) {
        throw new \RuntimeException('Cannot start a new isolated concurrency run');
    }
    $pdo = new \PDO('mysql:host=' . $host . ';dbname=covin_guard_lab', 'covin_guard_lab',
        getenv('COVIN_GUARD_LAB_DB_PASSWORD'), [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED');
    $requestTable = $prefix . 'covin_account_requests'; $auditTable = $prefix . 'covin_account_audit';
    $closureTable = $prefix . 'covin_account_closure'; $closureAudit = $prefix . 'covin_closure_audit';
    $gate = $prefix . 'covin_closure_gate';
    foreach ([$requestTable, $auditTable, $closureTable, $closureAudit] as $table) {
        if (covinLabRows($pdo, $table) !== []) { throw new \RuntimeException('Concurrency fixture requires an empty app'); }
    }
    $gateRows = covinLabRows($pdo, $gate);
    if (count($gateRows) !== 1 || (int)$gateRows[0]['id'] !== 1) { throw new \RuntimeException('Missing singleton gate'); }
    $insertRequest = function (int $id, string $username, string $status) use ($pdo, $requestTable): void {
        $q = $pdo->prepare('INSERT INTO `' . $requestTable . '` (id, display_name, username, contact_email, status, mailbox) VALUES (?, ?, ?, ?, ?, ?)');
        $q->execute([$id, 'Synthetic race fixture', $username, $username . '@example.invalid', $status, $username . '@example.test']);
    };
    $insertRequest(900, 'guard-race-unrelated', 'pending');
    $pdo->exec('INSERT INTO `' . $auditTable . '` (id,request_id,actor,action,details,created_at) VALUES (900,900,\'synthetic\',\'fixture\',\'Unrelated history must remain\',1700000000)');
    $sentinel = covinLabRows($pdo, $requestTable, 'WHERE id = 900');
    $sentinelAudit = covinLabRows($pdo, $auditTable);
    $scenarios = ['approval', 'retry', 'resend', 'claim', 'execution', 'double-claim'];
    $rounds = 0; $waits = 0;
    foreach ($scenarios as $scenario) {
        foreach ([false, true] as $reverse) {
            $round = ++$rounds; $username = 'guard-race-' . $round; $id = 1000 + $round * 2;
            $initial = match ($scenario) { 'approval' => 'pending', 'retry' => 'failed', 'claim', 'double-claim' => 'queued', default => 'completed' };
            $insertRequest($id, $username, $initial);
            if (in_array($scenario, ['approval', 'retry', 'claim'], true)) { $insertRequest($id + 1, $username, 'completed'); }
            $operations = ['a' => $scenario === 'double-claim' ? 'claim' : $scenario,
                'b' => $scenario === 'double-claim' ? 'claim' : 'freeze'];
            $pdo->beginTransaction();
            $pdo->exec('UPDATE `' . $gate . '` SET marker = \'' . bin2hex(random_bytes(16)) . '\' WHERE id = 1');
            try {
                foreach ($reverse ? ['b', 'a'] : ['a', 'b'] as $side) {
                    $ticket = $round . '-' . $side;
                    covinLabJson($dir . '/' . $ticket . '.job.json', ['run' => $run, 'username' => $username, 'id' => $id, 'operation' => $operations[$side]]);
                    $proc = proc_open([PHP_BINARY, __FILE__, 'worker', $ticket],
                        [0 => ['file', '/dev/null', 'r'], 1 => ['file', $dir . '/' . $ticket . '.stdout', 'w'],
                        2 => ['file', $dir . '/' . $ticket . '.stderr', 'w']], $pipes);
                    if (!is_resource($proc)) { throw new \RuntimeException('Cannot start isolated worker'); }
                    $children[$ticket] = $proc;
                    covinLabWait(fn() => is_file($dir . '/' . $ticket . '.ready.json'));
                }
                $ids = [];
                foreach (['a', 'b'] as $side) { $ids[] = covinLabRead($dir . '/' . $round . '-' . $side . '.ready.json')['connection_id']; }
                if (count(array_unique($ids)) !== 2) { throw new \RuntimeException('Workers share a database connection'); }
                covinLabWait(function () use ($pdo, $ids, $gate, $dir, $round): bool {
                    foreach (['a', 'b'] as $side) {
                        if (is_file($dir . '/' . $round . '-' . $side . '.result.json')) { throw new \RuntimeException('Operation bypassed held gate'); }
                    }
                    $seen = [];
                    foreach ($pdo->query('SHOW FULL PROCESSLIST')->fetchAll(\PDO::FETCH_ASSOC) as $thread) {
                        if (in_array((int)$thread['Id'], $ids, true)
                            && preg_match('/^\s*UPDATE\s+`?' . preg_quote($gate, '/') . '`?\s+/i', (string)$thread['Info'])) {
                            $seen[] = (int)$thread['Id'];
                        }
                    }
                    return count(array_unique($seen)) === 2;
                });
                $waits += 2;
                $pdo->commit();
                $results = [];
                foreach (['a', 'b'] as $side) {
                    $ticket = $round . '-' . $side;
                    covinLabWait(fn() => is_file($dir . '/' . $ticket . '.result.json'));
                    $results[$side] = covinLabRead($dir . '/' . $ticket . '.result.json');
                    $exit = proc_close($children[$ticket]); unset($children[$ticket]);
                    if ($exit !== 0) { throw new \RuntimeException('Worker failed after result'); }
                }
                $row = covinLabRows($pdo, $requestTable, 'WHERE id = ?', [$id])[0];
                $registryRows = covinLabRows($pdo, $closureTable, 'WHERE username = ?', [$username]);
                if (count($registryRows) > 1) { throw new \RuntimeException('Duplicate closure state'); }
                covinCheckRace($scenario, $results['a'], $results['b'], $row['status'], $registryRows[0] ?? null, $id);
                if (covinLabRows($pdo, $requestTable, 'WHERE id = 900') !== $sentinel
                    || covinLabRows($pdo, $auditTable) !== $sentinelAudit) { throw new \RuntimeException('Unrelated history changed'); }
                covinLabJson($dir . '/round-' . $round . '.json', ['scenario' => $scenario, 'reverse_launch' => $reverse, 'gate_waiters' => 2, 'passed' => true]);
            } finally {
                if ($pdo->inTransaction()) { $pdo->rollBack(); }
                foreach ($children as $ticket => $proc) { proc_terminate($proc, 9); proc_close($proc); unset($children[$ticket]); }
            }
            // Only this round's synthetic rows; never user/account deletion interfaces.
            foreach ([$requestTable, $closureTable, $closureAudit] as $table) {
                $q = $pdo->prepare('DELETE FROM `' . $table . '` WHERE username = ?'); $q->execute([$username]);
            }
        }
    }
    echo json_encode(['status' => 'isolated-concurrency-passed', 'scenarios' => $scenarios,
        'contended_rounds' => $rounds, 'observed_gate_waiters' => $waits,
        'unrelated_request_and_audit_preserved' => true, 'separate_worker_connections' => true,
        'production_deployment' => false, 'account_deletion' => false], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR), PHP_EOL;
} catch (\Throwable $error) {
    if ($pdo instanceof \PDO && $pdo->inTransaction()) { $pdo->rollBack(); }
    foreach ($children as $proc) { proc_terminate($proc, 9); proc_close($proc); }
    if ($labValidated) {
        $path = '/var/www/html/data/.guard-concurrency-error-' . getmypid() . '.txt';
        if (@file_put_contents($path, (string)$error, LOCK_EX) !== false) { @chmod($path, 0600); }
    }
    fwrite(STDERR, 'STOP: isolated concurrency failed (' . get_class($error) . ").\n");
    exit(1);
}
