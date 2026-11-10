<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Db;

use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

final class AuditEventMapper extends QBMapper {
    public function __construct(IDBConnection $db) {
        parent::__construct($db, 'covin_account_audit', AuditEvent::class);
    }

    public function record(int $requestId, string $actor, string $action, string $details = ''): AuditEvent {
        $event = new AuditEvent();
        $event->setRequestId($requestId);
        $event->setActor(mb_substr($actor, 0, 128));
        $event->setAction(mb_substr($action, 0, 64));
        $event->setDetails(mb_substr($details, 0, 4000));
        $event->setCreatedAt(time());
        return $this->insert($event);
    }

    /** @return AuditEvent[] */
    public function findForRequest(int $requestId, int $limit = 100, int $offset = 0): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')->from($this->getTableName())
            ->where($qb->expr()->eq('request_id', $qb->createNamedParameter($requestId, IQueryBuilder::PARAM_INT)))
            ->orderBy('id', 'DESC')
            ->setFirstResult($offset)
            ->setMaxResults($limit);
        return $this->findEntities($qb);
    }
}
