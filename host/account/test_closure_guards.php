<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);

// Standalone mocks only. Do not bootstrap Nextcloud or contact any live service.
namespace OCP {
    interface IDBConnection {}
    interface IUserManager {}
    interface IGroupManager {}
}
namespace OCP\Migration {
    interface IOutput {}
    interface IRepairStep {
        public function getName(): string;
        public function run(IOutput $output): void;
    }
}
namespace Symfony\Component\Console\Command {
    class Command {
        public const SUCCESS = 0;
        public const FAILURE = 1;
        public function __construct() {}
    }
}
namespace Symfony\Component\Console\Input {
    interface InputInterface {}
    class InputArgument { public const REQUIRED = 1; }
    class InputOption { public const VALUE_REQUIRED = 1; public const VALUE_NONE = 2; }
}
namespace Symfony\Component\Console\Output {
    interface OutputInterface {}
}
namespace OCP\DB\QueryBuilder {
    interface IQueryBuilder { const PARAM_INT = 1; const PARAM_STR_ARRAY = 2; }
}
namespace OCP\AppFramework\Db {
    class DoesNotExistException extends \RuntimeException {}
    class Entity {
        protected $id = 0;
        public function addType($name, $type): void {}
        public function __call($name, $args): mixed {
            $property = lcfirst(substr($name, 3));
            if (str_starts_with($name, 'get')) { return $this->$property; }
            if (str_starts_with($name, 'set')) { $this->$property = $args[0]; return null; }
            throw new \RuntimeException('Unknown entity method');
        }
    }
    class QBMapper {
        public function __construct(protected \OCP\IDBConnection $db, private string $table, private string $entity) {}
        public function getTableName(): string { return $this->table; }
        protected function hydrate(array $row): Entity {
            $e = new $this->entity();
            foreach ($row as $key => $value) {
                $method = 'set' . str_replace(' ', '', ucwords(str_replace('_', ' ', $key)));
                $e->$method($value);
            }
            return $e;
        }
        public function findEntity($q): Entity {
            $rows = $q->executeQuery()->fetchAll();
            if (count($rows) !== 1) { throw new DoesNotExistException(); }
            return $this->hydrate($rows[0]);
        }
        public function findEntities($q): array {
            return array_map(fn($row) => $this->hydrate($row), $q->executeQuery()->fetchAll());
        }
        public function insert(Entity $entity): Entity {
            $row = $entity->jsonSerialize();
            $snake = [];
            foreach ($row as $key => $value) {
                $snake[strtolower(preg_replace('/[A-Z]/', '_$0', $key))] = $value;
            }
            $snake['id'] = count($this->db->tables[$this->table]) + 100;
            $snake['claim_token'] = '';
            $snake['claimed_at'] = 0;
            $this->db->tables[$this->table][] = $snake;
            $entity->setId($snake['id']);
            return $entity;
        }
    }
}
namespace {
    final class Param { public function __construct(public mixed $value) {} }
    final class Result {
        private int $offset = 0;
        public function __construct(private array $rows) {}
        public function fetch(): array|false { return $this->rows[$this->offset++] ?? false; }
        public function fetchAll(): array { return $this->rows; }
        public function fetchOne(): mixed { return $this->rows === [] ? false : reset($this->rows[0]); }
        public function closeCursor(): void {}
    }
    final class Expr {
        public static function value($item, array $row): mixed {
            return $item instanceof Param ? $item->value : ($row[$item] ?? null);
        }
        public function eq($a, $b): callable { return fn($r) => self::value($a, $r) === self::value($b, $r); }
        public function neq($a, $b): callable { return fn($r) => self::value($a, $r) !== self::value($b, $r); }
        public function in($a, $b): callable { return fn($r) => in_array(self::value($a, $r), self::value($b, $r), true); }
        public function isNull($a): callable { return fn($r) => self::value($a, $r) === null; }
        public function orX(...$clauses): callable { return fn($r) => count(array_filter($clauses, fn($c) => $c($r))) > 0; }
    }
    final class FakeDB implements \OCP\IDBConnection {
        public array $tables = [
            'covin_closure_gate' => [['id' => 1, 'marker' => 'initial']],
            'covin_account_closure' => [], 'covin_closure_audit' => [],
            'covin_account_requests' => [], 'covin_account_audit' => [],
        ];
        public array $trace = [];
        private ?array $snapshot = null;
        public function beginTransaction(): void {
            if ($this->snapshot !== null) { throw new \RuntimeException('Unexpected nested transaction'); }
            $this->snapshot = $this->tables;
            $this->trace[] = 'begin';
        }
        public function commit(): void { $this->trace[] = 'commit'; $this->snapshot = null; }
        public function rollBack(): void {
            $this->tables = $this->snapshot;
            $this->snapshot = null;
            $this->trace[] = 'rollback';
        }
        public function getQueryBuilder(): Query { return new Query($this); }
    }
    final class Query {
        private string $action = 'select';
        private string $table = '';
        private string $alias = '';
        private array $columns = ['*'];
        private array $clauses = [];
        private array $values = [];
        private ?array $join = null;
        private int $limit = PHP_INT_MAX;
        private int $offset = 0;
        private ?array $sort = null;
        public function __construct(private FakeDB $db) {}
        public function expr(): Expr { return new Expr(); }
        public function createNamedParameter($value, $type = null): Param { return new Param($value); }
        public function select(...$columns): self { $this->columns = $columns; return $this; }
        public function from($table, $alias = ''): self { $this->table = $table; $this->alias = $alias; return $this; }
        public function update($table): self { $this->action = 'update'; $this->table = $table; return $this; }
        public function insert($table): self { $this->action = 'insert'; $this->table = $table; return $this; }
        public function set($key, $value): self { $this->values[$key] = $value->value; return $this; }
        public function setValue($key, $value): self { return $this->set($key, $value); }
        public function where($clause): self { $this->clauses = [$clause]; return $this; }
        public function andWhere($clause): self { $this->clauses[] = $clause; return $this; }
        public function leftJoin($from, $table, $alias, $condition): self { $this->join = [$table, $alias, $condition]; return $this; }
        public function orderBy($column, $direction): self { $this->sort = [$column, $direction]; return $this; }
        public function setMaxResults($limit): self { $this->limit = $limit; return $this; }
        public function setFirstResult($offset): self { $this->offset = $offset; return $this; }
        private function tableRows(): array {
            if (!array_key_exists($this->table, $this->db->tables)) { throw new \RuntimeException('Missing table'); }
            return $this->db->tables[$this->table];
        }
        private function matches(array $row): bool {
            foreach ($this->clauses as $clause) { if (!$clause($row)) { return false; } }
            return true;
        }
        private function qualify(array $row, string $alias): array {
            $result = $row;
            foreach ($row as $key => $value) { $result[$alias . '.' . $key] = $value; }
            return $result;
        }
        public function executeStatement(): int {
            $rows = $this->tableRows();
            $this->db->trace[] = $this->action . ':' . $this->table;
            if ($this->action === 'insert') {
                if ($this->table === 'covin_account_closure') {
                    foreach ($rows as $r) { if ($r['username'] === $this->values['username']) { throw new \RuntimeException('Duplicate'); } }
                }
                $this->db->tables[$this->table][] = $this->values;
                return 1;
            }
            $count = 0;
            foreach ($rows as &$row) {
                if ($this->matches($row)) { $row = array_merge($row, $this->values); $count++; }
            }
            unset($row);
            $this->db->tables[$this->table] = $rows;
            return $count;
        }
        public function executeQuery(): Result {
            $this->db->trace[] = 'select:' . $this->table;
            $selected = [];
            foreach ($this->tableRows() as $original) {
                $row = $this->alias === '' ? $original : $this->qualify($original, $this->alias);
                if ($this->join !== null) {
                    [$table, $alias, $condition] = $this->join;
                    foreach ($this->db->tables[$table] as $joined) {
                        $candidate = array_merge($row, $this->qualify($joined, $alias));
                        // Keep base unqualified fields to model selecting r.*.
                        $candidate = array_merge($candidate, $original);
                        if ($condition($candidate)) { $row = $candidate; break; }
                    }
                }
                if ($this->matches($row)) { $selected[] = $row; }
            }
            if ($this->sort !== null) {
                [$column, $direction] = $this->sort;
                usort($selected, fn($a, $b) => ($direction === 'DESC' ? -1 : 1) * ($a[$column] <=> $b[$column]));
            }
            $selected = array_slice($selected, $this->offset, $this->limit);
            $projected = [];
            foreach ($selected as $row) {
                if ($this->columns === ['r.*']) {
                    $projected[] = array_intersect_key($row, array_flip(array_keys($this->tableRows()[0])));
                } elseif ($this->columns === ['*']) {
                    $projected[] = array_filter($row, fn($key) => !str_contains($key, '.'), ARRAY_FILTER_USE_KEY);
                } else {
                    $projected[] = array_intersect_key($row, array_flip($this->columns));
                }
            }
            return new Result($projected);
        }
    }

    // Resolve from an explicitly supplied source root when piped into a container.
    $root = getenv('COVIN_GUARD_SOURCE_ROOT') ?: dirname(__DIR__, 2);
    require $root . '/apps/covin_account_admin/lib/Db/AccountRequest.php';
    require $root . '/apps/covin_account_admin/lib/Service/ClosureRegistry.php';
    require $root . '/apps/covin_account_admin/lib/Db/AccountRequestMapper.php';
    require $root . '/apps/covin_account_admin/lib/Command/ClosureGuardCommand.php';

    require $root . '/apps/covin_account_admin/lib/Repair/InitializeClosureGate.php';

    final class FakeInput implements \Symfony\Component\Console\Input\InputInterface {
        public function __construct(private string $action, private string $username, private array $options) {}
        public function getArgument($key): string { return $key === 'action' ? $this->action : $this->username; }
        public function getOption($key): mixed { return $this->options[$key] ?? null; }
    }
    final class FakeOutput implements \Symfony\Component\Console\Output\OutputInterface {
        public array $lines = [];
        public function writeln($line): void { $this->lines[] = $line; }
    }
    final class FakeUsers implements \OCP\IUserManager {
        public function __construct(private bool $exists, private bool $enabled) {}
        public function get($username): ?object {
            if (!$this->exists) { return null; }
            return new class($this->enabled) {
                public function __construct(private bool $enabled) {}
                public function isEnabled(): bool { return $this->enabled; }
            };
        }
    }
    final class FakeGroups implements \OCP\IGroupManager {
        public function __construct(private bool $admin) {}
        public function isAdmin($username): bool { return $this->admin; }
    }
    function runCommand($registry, $mapper, string $action, string $username, array $options = [], bool $enabled = false, bool $admin = false, bool $exists = true): array {
        $command = new \OCA\CovinAccountAdmin\Command\ClosureGuardCommand(
            $registry, $mapper, new FakeUsers($exists, $enabled), new FakeGroups($admin)
        );
        $output = new FakeOutput();
        $method = new \ReflectionMethod($command, 'execute');
        $status = $method->invoke($command, new FakeInput($action, $username, $options), $output);
        return [$status, implode("\n", $output->lines)];
    }

    function expect(bool $condition, string $message): void {
        if (!$condition) { throw new \RuntimeException($message); }
    }
    function refused(callable $operation): void {
        try { $operation(); } catch (\Throwable $error) { return; }
        throw new \RuntimeException('Expected refusal');
    }
    function requestRow(int $id, string $user, string $status): array {
        return ['id' => $id, 'username' => $user, 'mailbox' => $user . '@example.test',
            'status' => $status, 'claim_token' => '', 'claimed_at' => 0,
            'job_type' => 'provision', 'invitation_days' => 14];
    }
    function fixture(): array {
        $db = new FakeDB();
        $registry = new \OCA\CovinAccountAdmin\Service\ClosureRegistry($db);
        $mapper = new \OCA\CovinAccountAdmin\Db\AccountRequestMapper($db, $registry);
        return [$db, $registry, $mapper];
    }
    function reserve(FakeDB $db, string $user, string $state): void {
        $db->tables['covin_account_closure'][] = ['username' => $user, 'state' => $state,
            'execution_hash' => '', 'actor' => 'test-operator', 'reason' => 'offline test', 'updated_at' => 1];
    }

    $tests = [];
    $tests['freeze retains completed request and separate audit'] = function () {
        [$db, $r, $m] = fixture();
        $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'completed')];
        $before = $db->tables['covin_account_requests'];
        $m->freezeUsername('test-member', 'test-operator', 'offline test');
        expect($r->isBlocked('test-member'), 'Not frozen');
        expect($db->tables['covin_account_requests'] === $before, 'Request changed');
        expect(count($db->tables['covin_closure_audit']) === 1, 'Missing audit');
        $m->freezeUsername('test-member', 'other-operator', 'retry');
        expect(count($db->tables['covin_closure_audit']) === 1, 'Duplicate freeze audit');
    };
    foreach (['closing', 'closed'] as $state) {
        foreach (['pending', 'failed', 'completed'] as $status) {
            $tests[$state . ' blocks ' . $status . ' queue mutation'] = function () use ($state, $status) {
                [$db, $r, $m] = fixture();
                reserve($db, 'test-member', $state);
                $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', $status)];
                $before = $db->tables['covin_account_requests'];
                $ok = match ($status) {
                    'pending' => $m->queueForApproval(1, 'test-operator'),
                    'failed' => $m->retry(1, 'test-operator'),
                    'completed' => $m->queueForResend(1, 'test-operator', 14),
                };
                expect($ok === false && $before === $db->tables['covin_account_requests'], 'Queue changed');
            };
        }
        $tests[$state . ' reserves username even without request rows'] = function () use ($state) {
            [$db, $r, $m] = fixture(); reserve($db, 'test-member', $state);
            $request = new \OCA\CovinAccountAdmin\Db\AccountRequest();
            $request->setUsername('test-member');
            expect($m->hasOpenUsername('test-member'), 'Username was reusable');
            expect($m->insertGuarded($request) === null, 'Ingress inserted');
            refused(fn() => $r->beginExecution('test-member'));
        };
    }
    $tests['worker skips frozen queued job and serves unrelated member'] = function () {
        [$db, $r, $m] = fixture(); reserve($db, 'test-member', 'closing');
        $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'queued'), requestRow(2, 'other-member', 'queued')];
        expect($m->claimNext()?->getUsername() === 'other-member', 'Wrong claim');
        expect($db->tables['covin_account_requests'][0]['status'] === 'queued', 'Frozen history changed');
    };
    $tests['unrelated ingress approval retry resend remain available'] = function () {
        [$db, $r, $m] = fixture(); reserve($db, 'test-member', 'closed');
        $db->tables['covin_account_requests'] = [requestRow(1, 'pending-member', 'pending'),
            requestRow(2, 'failed-member', 'failed'), requestRow(3, 'completed-member', 'completed')];
        expect($m->queueForApproval(1, 'operator'), 'Approval blocked');
        expect($m->retry(2, 'operator'), 'Retry blocked');
        expect($m->queueForResend(3, 'operator', 14), 'Resend blocked');
        $request = new \OCA\CovinAccountAdmin\Db\AccountRequest(); $request->setUsername('new-member');
        expect($m->insertGuarded($request) !== null, 'New member blocked');
        expect($m->insertGuarded($request) === null, 'Duplicate ingress accepted');
    };
    $tests['claimed running job blocks freeze without mutation'] = function () {
        [$db, $r, $m] = fixture();
        $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'completed'), requestRow(2, 'test-member', 'running')];
        $before = $db->tables; refused(fn() => $m->freezeUsername('test-member', 'operator', 'test'));
        expect($db->tables === $before, 'Failed freeze changed data');
    };
    $tests['manual execution blocks freeze and stores no raw token'] = function () {
        [$db, $r, $m] = fixture(); $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'completed')];
        $token = $r->beginExecution('test-member');
        expect(!str_contains(json_encode($db->tables), $token), 'Raw token persisted');
        refused(fn() => $m->freezeUsername('test-member', 'operator', 'test'));
        refused(fn() => $r->beginExecution('test-member'));
        refused(fn() => $r->endExecution('test-member', str_repeat('a', 48)));
        expect($r->read('test-member')['execution_hash'] !== '', 'Wrong token released');
        $r->endExecution('test-member', $token);
        $m->freezeUsername('test-member', 'operator', 'test');
        expect($r->isBlocked('test-member'), 'Freeze after release failed');
    };
    $tests['old execution reservation never expires automatically'] = function () {
        [$db, $r, $m] = fixture(); $r->beginExecution('test-member');
        $db->tables['covin_account_closure'][0]['updated_at'] = 1;
        refused(fn() => $r->beginExecution('test-member'));
        expect($r->read('test-member')['execution_hash'] !== '', 'Expired automatically');
    };
    $tests['identity conflict and ambiguous completed history block freeze'] = function () {
        foreach (['conflict', 'ambiguous', 'absent'] as $variant) {
            [$db, $r, $m] = fixture();
            if ($variant !== 'absent') { $db->tables['covin_account_requests'][] = requestRow(1, 'test-member', 'completed'); }
            if ($variant === 'conflict') { $db->tables['covin_account_requests'][0]['mailbox'] = 'other-member@example.test'; }
            if ($variant === 'ambiguous') { $db->tables['covin_account_requests'][] = requestRow(2, 'test-member', 'completed'); }
            refused(fn() => $m->freezeUsername('test-member', 'operator', 'test'));
            expect($db->tables['covin_account_closure'] === [], 'Reservation written despite conflict');
        }
    };
    $tests['missing gate and missing registry fail closed'] = function () {
        [$db, $r, $m] = fixture(); $db->tables['covin_closure_gate'] = [];
        refused(fn() => $r->beginExecution('test-member'));
        expect($db->tables['covin_account_closure'] === [], 'Missing gate allowed reservation');
        unset($db->tables['covin_account_closure']);
        refused(fn() => $m->hasOpenUsername('test-member'));
    };
    $tests['unknown state rejected rather than treated open'] = function () {
        [$db, $r, $m] = fixture(); reserve($db, 'test-member', 'unknown');
        refused(fn() => $m->hasOpenUsername('test-member'));
        refused(fn() => $r->beginExecution('test-member'));
    };
    $tests['lock acquired before request mutation'] = function () {
        [$db, $r, $m] = fixture(); $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'pending')];
        $m->queueForApproval(1, 'operator');
        expect($db->trace[0] === 'begin' && $db->trace[1] === 'update:covin_closure_gate', 'Lock order wrong');
        expect(end($db->trace) === 'commit', 'Transaction not committed');
    };
    $tests['closed state never changed to closing by freeze retry'] = function () {
        [$db, $r, $m] = fixture(); reserve($db, 'test-member', 'closed');
        $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'completed')];
        $m->freezeUsername('test-member', 'operator', 'test');
        expect($r->read('test-member')['state'] === 'closed', 'Closed state regressed');
    };
    $tests['invalid canonical username rejected'] = function () {
        [$db, $r, $m] = fixture();
        foreach (['Test-Member', 'member@example.test', '*', '../member'] as $name) { refused(fn() => $r->beginExecution($name)); }
    };
    $tests['CLI inspect and freeze dry run have no writes or clearance'] = function () {
        [$db, $r, $m] = fixture(); $before = $db->tables;
        foreach (['inspect', 'freeze', 'begin-execution', 'end-execution'] as $action) {
            [$status, $text] = runCommand($r, $m, $action, 'test-member');
            $report = json_decode($text, true, 512, JSON_THROW_ON_ERROR);
            expect($status === 0 && $report['freeze_clearance'] === false && $report['data_deletion'] === false, 'Unsafe dry run');
            expect($db->tables === $before, 'Dry run changed data');
        }
    };
    $tests['CLI freeze requires exact confirmation and disabled member'] = function () {
        foreach (['confirmation', 'enabled', 'admin', 'missing', 'protected'] as $variant) {
            [$db, $r, $m] = fixture();
            $name = $variant === 'protected' ? 'covin-export-delivery' : 'test-member';
            $db->tables['covin_account_requests'] = [requestRow(1, $name, 'completed')];
            $before = $db->tables;
            [$status, $text] = runCommand($r, $m, 'freeze', $name, [
                'commit' => true, 'confirm' => $variant === 'confirmation' ? 'YES' : 'FREEZE',
                'operator' => 'test-operator', 'reason' => 'test',
            ], $variant === 'enabled', $variant === 'admin', $variant !== 'missing');
            expect($status === 1 && $db->tables === $before, 'Unsafe CLI freeze');
        }
    };
    $tests['CLI confirmed freeze reserves only and cannot mark closed or reuse'] = function () {
        [$db, $r, $m] = fixture(); $db->tables['covin_account_requests'] = [requestRow(1, 'test-member', 'completed')];
        [$status, $text] = runCommand($r, $m, 'freeze', 'test-member', [
            'commit' => true, 'confirm' => 'FREEZE', 'operator' => 'test-operator', 'reason' => 'test',
        ]);
        expect($status === 0 && $r->read('test-member')['state'] === 'closing', 'Confirmed freeze failed');
        foreach (['mark-closed', 'unfreeze', 'reuse', 'delete'] as $action) {
            [$status, $text] = runCommand($r, $m, $action, 'test-member', ['commit' => true]);
            expect($status === 1 && $r->isBlocked('test-member'), 'Unsupported transition allowed');
        }
    };
    $tests['transaction exception rolls back reservation and audit'] = function () {
        [$db, $r, $m] = fixture(); $before = $db->tables;
        refused(fn() => $r->serialized(function () use ($r) {
            $r->freeze('test-member', 'operator', 'test');
            throw new \RuntimeException('Injected failure');
        }));
        expect($db->tables === $before, 'Rollback lost state');
    };
    $tests['fresh install repair seeds exactly one gate and is idempotent'] = function () {
        $db = new FakeDB();
        $db->tables['covin_closure_gate'] = [];
        $repair = new \OCA\CovinAccountAdmin\Repair\InitializeClosureGate($db);
        $out = new class implements \OCP\Migration\IOutput {};
        $repair->run($out);
        expect($db->tables['covin_closure_gate'] === [['id' => 1, 'marker' => str_repeat('0', 32)]], 'Incorrect seed');
        $before = $db->tables;
        $repair->run($out);
        expect($db->tables === $before, 'Repeated install changed state');
    };
    $tests['install repair preserves populated state with an existing valid gate'] = function () {
        $db = new FakeDB();
        $db->tables['covin_closure_gate'] = [['id' => '1', 'marker' => str_repeat('a', 32)]];
        $db->tables['covin_account_closure'] = [['username' => 'reserved-member', 'state' => 'closed']];
        $db->tables['covin_closure_audit'] = [['id' => 1]];
        $before = $db->tables;
        (new \OCA\CovinAccountAdmin\Repair\InitializeClosureGate($db))->run(new class implements \OCP\Migration\IOutput {});
        expect($db->tables === $before, 'Existing gate/reservation/audit changed');
    };
    $tests['install repair refuses missing gate over any retained account state'] = function () {
        foreach (['covin_account_requests', 'covin_account_audit', 'covin_account_closure', 'covin_closure_audit'] as $table) {
            $db = new FakeDB();
            $db->tables['covin_closure_gate'] = [];
            $db->tables[$table] = [['id' => 1]];
            $before = $db->tables;
            refused(fn() => (new \OCA\CovinAccountAdmin\Repair\InitializeClosureGate($db))->run(new class implements \OCP\Migration\IOutput {}));
            expect($db->tables === $before, 'Missing gate reseeded over existing state');
            expect(in_array('rollback', $db->trace, true), 'Failure did not roll back');
        }
    };
    $tests['install repair refuses malformed or duplicate gate rows'] = function () {
        foreach ([
            [['id' => 2, 'marker' => str_repeat('0', 32)]],
            [['id' => 1, 'marker' => 'invalid']],
            [['id' => 1, 'marker' => str_repeat('0', 32)], ['id' => 2, 'marker' => str_repeat('0', 32)]],
        ] as $rows) {
            $db = new FakeDB(); $db->tables['covin_closure_gate'] = $rows;
            $before = $db->tables;
            refused(fn() => (new \OCA\CovinAccountAdmin\Repair\InitializeClosureGate($db))->run(new class implements \OCP\Migration\IOutput {}));
            expect($db->tables === $before, 'Malformed gate was repaired implicitly');
        }
    };
    $tests['install repair refuses missing prerequisite tables'] = function () {
        $db = new FakeDB(); $db->tables['covin_closure_gate'] = [];
        unset($db->tables['covin_closure_audit']);
        $before = $db->tables;
        refused(fn() => (new \OCA\CovinAccountAdmin\Repair\InitializeClosureGate($db))->run(new class implements \OCP\Migration\IOutput {}));
        expect($db->tables === $before, 'Incomplete schema was initialized');
    };
    $failed = 0;
    foreach ($tests as $name => $test) {
        try { $test(); echo 'PASS: ' . $name . PHP_EOL; }
        catch (\Throwable $error) { $failed++; echo 'FAIL: ' . $name . ' — ' . $error->getMessage() . PHP_EOL; }
    }
    printf("Closure guard mock tests: %d; failures: %d\n", count($tests), $failed);
    exit($failed === 0 ? 0 : 1);
}
