<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

final class Version010000Date20260917000000 extends SimpleMigrationStep {
    public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
        /** @var ISchemaWrapper $schema */
        $schema = $schemaClosure();

        if (!$schema->hasTable('covin_account_requests')) {
            $table = $schema->createTable('covin_account_requests');
            $table->addColumn('id', 'bigint', ['autoincrement' => true, 'notnull' => true, 'unsigned' => true]);
            $table->addColumn('display_name', 'string', ['notnull' => true, 'length' => 100]);
            $table->addColumn('username', 'string', ['notnull' => true, 'length' => 64]);
            $table->addColumn('contact_email', 'string', ['notnull' => true, 'length' => 254]);
            $table->addColumn('status', 'string', ['notnull' => true, 'length' => 32, 'default' => 'pending']);
            $table->addColumn('requested_at', 'bigint', ['notnull' => true, 'default' => 0]);
            $table->addColumn('updated_at', 'bigint', ['notnull' => true, 'default' => 0]);
            $table->addColumn('reviewed_by', 'string', ['notnull' => true, 'length' => 128, 'default' => '']);
            $table->addColumn('reviewed_at', 'bigint', ['notnull' => true, 'default' => 0]);
            $table->addColumn('claim_token', 'string', ['notnull' => true, 'length' => 64, 'default' => '']);
            $table->addColumn('claimed_at', 'bigint', ['notnull' => true, 'default' => 0]);
            $table->addColumn('mailbox', 'string', ['notnull' => true, 'length' => 320, 'default' => '']);
            $table->addColumn('error_message', 'string', ['notnull' => true, 'length' => 4000, 'default' => '']);
            $table->setPrimaryKey(['id']);
            $table->addIndex(['status', 'id'], 'covin_account_status');
            $table->addIndex(['username', 'id'], 'covin_account_username');
            $table->addIndex(['contact_email', 'id'], 'covin_account_contact');
        }

        if (!$schema->hasTable('covin_account_audit')) {
            $table = $schema->createTable('covin_account_audit');
            $table->addColumn('id', 'bigint', ['autoincrement' => true, 'notnull' => true, 'unsigned' => true]);
            $table->addColumn('request_id', 'bigint', ['notnull' => true, 'unsigned' => true]);
            $table->addColumn('actor', 'string', ['notnull' => true, 'length' => 128]);
            $table->addColumn('action', 'string', ['notnull' => true, 'length' => 64]);
            $table->addColumn('details', 'string', ['notnull' => true, 'length' => 4000, 'default' => '']);
            $table->addColumn('created_at', 'bigint', ['notnull' => true, 'default' => 0]);
            $table->setPrimaryKey(['id']);
            $table->addIndex(['request_id', 'id'], 'covin_account_audit_request');
            $table->addIndex(['created_at'], 'covin_account_audit_created');
        }

        return $schema;
    }
}
