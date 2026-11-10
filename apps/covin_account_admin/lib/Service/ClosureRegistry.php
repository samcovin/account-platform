<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Service;

use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

/** Persistent username reservation, independent of request/audit status. */
final class ClosureRegistry {
    public function __construct(private IDBConnection $db) {
    }

    /**
     * A singleton row update serializes short registry/queue transactions.
     * Missing schema/gate fails closed. Never hold this across network calls.
     */
    public function serialized(callable $operation): mixed {
        $this->db->beginTransaction();
        try {
            $q = $this->db->getQueryBuilder();
            $q->update('covin_closure_gate')
                ->set('marker', $q->createNamedParameter(bin2hex(random_bytes(16))))
                ->where($q->expr()->eq('id', $q->createNamedParameter(1, IQueryBuilder::PARAM_INT)));
            if ($q->executeStatement() !== 1) {
                throw new \RuntimeException('Closure gate unavailable');
            }
            $value = $operation();
            $this->db->commit();
            return $value;
        } catch (\Throwable $error) {
            $this->db->rollBack();
            throw $error;
        }
    }

    public function read(string $username): ?array {
        self::validateUsername($username);
        $q = $this->db->getQueryBuilder();
        $q->select('*')->from('covin_account_closure')->where(
            $q->expr()->eq('username', $q->createNamedParameter($username))
        );
        $result = $q->executeQuery();
        $row = $result->fetch();
        $result->closeCursor();
        if ($row === false) {
            return null;
        }
        if (!in_array($row['state'], ['open', 'closing', 'closed'], true)
            || !preg_match('/^(?:[a-f0-9]{64})?$/D', $row['execution_hash'])) {
            throw new \RuntimeException('Invalid closure registry state');
        }
        return $row;
    }

    public function isBlocked(string $username): bool {
        $row = $this->read($username);
        return $row !== null && $row['state'] !== 'open';
    }

    /** Must be called within serialized(). No release/reuse/closed transition here. */
    public function freeze(string $username, string $actor, string $reason): void {
        self::validateUsername($username);
        if ($actor === '' || strlen($actor) > 128 || $reason === '' || strlen($reason) > 1000
            || preg_match('/[\r\n\x00]/', $actor . $reason)) {
            throw new \InvalidArgumentException('Operator and short reason required');
        }
        $row = $this->read($username);
        if ($row !== null && $row['execution_hash'] !== '') {
            throw new \RuntimeException('An approver execution is still reserved');
        }
        if ($row !== null && $row['state'] !== 'open') {
            return; // Idempotent: never turn closed back into closing.
        }
        $this->write($username, 'closing', '', $actor, $reason, $row !== null);
        $this->event($username, $actor, 'freeze', $reason);
    }

    public function beginExecution(string $username): string {
        return $this->serialized(function () use ($username) {
            $row = $this->read($username);
            if (($row !== null && $row['state'] !== 'open')
                || ($row !== null && $row['execution_hash'] !== '')) {
                throw new \RuntimeException('Approval is blocked or already reserved');
            }
            $token = bin2hex(random_bytes(24));
            $this->write($username, 'open', hash('sha256', $token), '', '', $row !== null);
            $this->event($username, 'host-approver', 'execution-begin', '');
            return $token;
        });
    }

    public function endExecution(string $username, string $token): void {
        if (!preg_match('/^[a-f0-9]{48}$/D', $token)) {
            throw new \InvalidArgumentException('Invalid execution token');
        }
        $this->serialized(function () use ($username, $token) {
            $row = $this->read($username);
            if ($row === null || $row['execution_hash'] === ''
                || !hash_equals($row['execution_hash'], hash('sha256', $token))) {
                throw new \RuntimeException('Execution reservation mismatch');
            }
            $this->write($username, $row['state'], '', $row['actor'], $row['reason'], true);
            $this->event($username, 'host-approver', 'execution-end', '');
        });
    }

    private function write(string $username, string $state, string $hash, string $actor, string $reason, bool $exists): void {
        $q = $this->db->getQueryBuilder();
        $values = [
            'state' => $state, 'execution_hash' => $hash,
            'actor' => $actor, 'reason' => $reason, 'updated_at' => time(),
        ];
        if ($exists) {
            $q->update('covin_account_closure')->where(
                $q->expr()->eq('username', $q->createNamedParameter($username))
            );
            foreach ($values as $key => $value) {
                $q->set($key, $q->createNamedParameter($value));
            }
        } else {
            $q->insert('covin_account_closure');
            $values['username'] = $username;
            foreach ($values as $key => $value) {
                $q->setValue($key, $q->createNamedParameter($value));
            }
        }
        if ($q->executeStatement() !== 1) {
            throw new \RuntimeException('Registry write failed');
        }
    }

    private function event(string $username, string $actor, string $action, string $reason): void {
        $q = $this->db->getQueryBuilder();
        $q->insert('covin_closure_audit');
        foreach (['username' => $username, 'actor' => $actor, 'action' => $action,
            'reason' => $reason, 'created_at' => time()] as $key => $value) {
            $q->setValue($key, $q->createNamedParameter($value));
        }
        $q->executeStatement();
    }

    public static function validateUsername(string $username): void {
        if (!preg_match('/^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])$/D', $username)) {
            throw new \InvalidArgumentException('Invalid exact username');
        }
    }
}
