<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\IDBConnection;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

final class Version050000Date20261012000000 extends SimpleMigrationStep {
    public function __construct(private IDBConnection $db) {
    }

    public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
        $schema = $schemaClosure();
        if (!$schema->hasTable('covin_closure_gate')) {
            $t = $schema->createTable('covin_closure_gate');
            $t->addColumn('id', 'integer', ['notnull' => true]);
            $t->addColumn('marker', 'string', ['notnull' => true, 'length' => 32]);
            $t->setPrimaryKey(['id']);
        }
        if (!$schema->hasTable('covin_account_closure')) {
            $t = $schema->createTable('covin_account_closure');
            $t->addColumn('username', 'string', ['notnull' => true, 'length' => 64]);
            $t->addColumn('state', 'string', ['notnull' => true, 'length' => 16]);
            $t->addColumn('execution_hash', 'string', ['notnull' => true, 'length' => 64, 'default' => '']);
            $t->addColumn('actor', 'string', ['notnull' => true, 'length' => 128, 'default' => '']);
            $t->addColumn('reason', 'string', ['notnull' => true, 'length' => 1000, 'default' => '']);
            $t->addColumn('updated_at', 'bigint', ['notnull' => true]);
            $t->setPrimaryKey(['username']);
        }
        if (!$schema->hasTable('covin_closure_audit')) {
            $t = $schema->createTable('covin_closure_audit');
            $t->addColumn('id', 'bigint', ['autoincrement' => true, 'notnull' => true, 'unsigned' => true]);
            foreach (['username' => 64, 'actor' => 128, 'action' => 32, 'reason' => 1000] as $key => $length) {
                $t->addColumn($key, 'string', ['notnull' => true, 'length' => $length]);
            }
            $t->addColumn('created_at', 'bigint', ['notnull' => true]);
            $t->setPrimaryKey(['id']);
            $t->addIndex(['username', 'id'], 'covin_closure_audit_user');
        }
        return $schema;
    }

    public function postSchemaChange(IOutput $output, Closure $schemaClosure, array $options): void {
        $q = $this->db->getQueryBuilder();
        $q->select('id')->from('covin_closure_gate')->where(
            $q->expr()->eq('id', $q->createNamedParameter(1))
        );
        $r = $q->executeQuery();
        $exists = $r->fetchOne() !== false;
        $r->closeCursor();
        if (!$exists) {
            $q = $this->db->getQueryBuilder();
            $q->insert('covin_closure_gate')
                ->setValue('id', $q->createNamedParameter(1))
                ->setValue('marker', $q->createNamedParameter(str_repeat('0', 32)))
                ->executeStatement();
        }
    }
}
