<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

final class Version020000Date20260918000000 extends SimpleMigrationStep {
    public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
        /** @var ISchemaWrapper $schema */
        $schema = $schemaClosure();

        if (!$schema->hasTable('covin_account_requests')) {
            return $schema;
        }

        $table = $schema->getTable('covin_account_requests');

        if (!$table->hasColumn('invitation_days')) {
            $table->addColumn('invitation_days', 'integer', [
                'notnull' => true,
                'default' => 14,
            ]);
        }

        if (!$table->hasColumn('job_type')) {
            $table->addColumn('job_type', 'string', [
                'notnull' => true,
                'length' => 16,
                'default' => 'provision',
            ]);
        }

        return $schema;
    }
}
