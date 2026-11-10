<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Repair;

use OCP\IDBConnection;
use OCP\Migration\IOutput;
use OCP\Migration\IRepairStep;

/** Install-time initialization only; never invoked by request/worker paths. */
final class InitializeClosureGate implements IRepairStep {
    public function __construct(private IDBConnection $db) {
    }

    public function getName(): string {
        return 'Initialize closure gate for an empty installation';
    }

    public function run(IOutput $output): void {
        $this->db->beginTransaction();
        try {
            $rows = $this->rows('covin_closure_gate', 2);
            if ($rows !== []) {
                if (count($rows) !== 1 || (string)($rows[0]['id'] ?? '') !== '1'
                    || !is_string($rows[0]['marker'] ?? null)
                    || !preg_match('/^[a-f0-9]{32}$/D', $rows[0]['marker'])) {
                    throw new \RuntimeException('Invalid existing closure gate; operator review required');
                }
                // Preserve the current marker and every existing reservation/audit row.
                $this->db->commit();
                return;
            }
            foreach (['covin_account_requests', 'covin_account_audit',
                'covin_account_closure', 'covin_closure_audit'] as $table) {
                if ($this->rows($table, 1) !== []) {
                    throw new \RuntimeException('Missing closure gate with existing state; operator review required');
                }
            }
            $q = $this->db->getQueryBuilder();
            $q->insert('covin_closure_gate')
                ->setValue('id', $q->createNamedParameter(1))
                ->setValue('marker', $q->createNamedParameter(str_repeat('0', 32)))
                ->executeStatement();
            $this->db->commit();
        } catch (\Throwable $error) {
            $this->db->rollBack();
            throw $error;
        }
    }

    private function rows(string $table, int $limit): array {
        $q = $this->db->getQueryBuilder();
        $q->select('*')->from($table)->setMaxResults($limit);
        $result = $q->executeQuery();
        try {
            return $result->fetchAll();
        } finally {
            $result->closeCursor();
        }
    }
}
