<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Db;

use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;
use OCA\CovinAccountAdmin\Service\ClosureRegistry;

final class AccountRequestMapper extends QBMapper {
    public function __construct(IDBConnection $db, private ClosureRegistry $closure) {
        parent::__construct($db, 'covin_account_requests', AccountRequest::class);
    }

    public function find(int $id): AccountRequest {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')->from($this->getTableName())
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)));
        return $this->findEntity($qb);
    }

    /** @return AccountRequest[] */
    public function findRecent(int $limit = 200): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')->from($this->getTableName())
            ->orderBy('id', 'DESC')
            ->setMaxResults($limit);
        return $this->findEntities($qb);
    }

    public function hasOpenUsername(string $username): bool {
        if ($this->closure->isBlocked($username)) {
            return true;
        }
        $qb = $this->db->getQueryBuilder();
        $qb->select('id')->from($this->getTableName())
            ->where($qb->expr()->eq('username', $qb->createNamedParameter($username)))
            ->andWhere($qb->expr()->in(
                'status',
                $qb->createNamedParameter(['pending', 'queued', 'running', 'completed'], IQueryBuilder::PARAM_STR_ARRAY)
            ))
            ->setMaxResults(1);
        return $qb->executeQuery()->fetchOne() !== false;
    }

    /** Atomic recheck closes the check/insert race for both request ingress paths. */
    public function insertGuarded(AccountRequest $request): ?AccountRequest {
        return $this->closure->serialized(function () use ($request) {
            if ($this->hasOpenUsername($request->getUsername())) {
                return null;
            }
            return $this->insert($request);
        });
    }

    public function closureState(string $username): string {
        return $this->closure->read($username)['state'] ?? 'open';
    }

    private function guardRequest(int $id, callable $operation): bool {
        return $this->closure->serialized(function () use ($id, $operation) {
            try {
                $request = $this->find($id);
            } catch (DoesNotExistException $error) {
                return false;
            }
            return $this->closure->isBlocked($request->getUsername()) ? false : $operation();
        });
    }

    /** Reservation only. No service changes, no account deletion, no reuse release. */
    public function freezeUsername(string $username, string $actor, string $reason): void {
        $this->closure->serialized(function () use ($username, $actor, $reason) {
            $q = $this->db->getQueryBuilder();
            $q->select('username', 'mailbox', 'status')->from($this->getTableName())
                ->where($q->expr()->orX(
                    $q->expr()->eq('username', $q->createNamedParameter($username)),
                    $q->expr()->eq('mailbox', $q->createNamedParameter($username . '@example.test'))
                ));
            $result = $q->executeQuery();
            $rows = $result->fetchAll();
            $result->closeCursor();
            $completed = 0;
            foreach ($rows as $row) {
                if ($row['username'] !== $username || ($row['mailbox'] !== ''
                    && $row['mailbox'] !== $username . '@example.test')) {
                    throw new \RuntimeException('Request identity conflict');
                }
                if ($row['status'] === 'running') {
                    throw new \RuntimeException('A claimed job is still running');
                }
                if ($row['status'] === 'completed') {
                    if ($row['mailbox'] !== $username . '@example.test') {
                        throw new \RuntimeException('Completed mailbox mapping required');
                    }
                    $completed++;
                }
            }
            if ($completed !== 1) {
                throw new \RuntimeException('Exactly one completed account request required');
            }
            $this->closure->freeze($username, $actor, $reason);
        });
    }

    /** Rejection is the archive state; no data is moved or deleted. */
    public function browse(string $view, string $search, int $page): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')->from($this->getTableName());
        $qb->where($view === 'rejected'
            ? $qb->expr()->eq('status', $qb->createNamedParameter('rejected'))
            : $qb->expr()->neq('status', $qb->createNamedParameter('rejected')));
        if ($search !== '') {
            $pattern = $qb->createNamedParameter('%' . $this->db->escapeLikeParameter($search) . '%');
            $qb->andWhere($qb->expr()->orX(
                $qb->expr()->iLike('username', $pattern),
                $qb->expr()->iLike('contact_email', $pattern),
                $qb->expr()->iLike('display_name', $pattern)
            ));
        }
        $qb->orderBy('id', 'DESC')->setFirstResult($page * 50)->setMaxResults(51);
        return $this->findEntities($qb);
    }

    /** Exact, case-insensitive matches. SQL wildcard characters are escaped. */
    public function rejectedMatches(AccountRequest $request, int $page = 0, int $limit = 51): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')->from($this->getTableName())
            ->where($qb->expr()->eq('status', $qb->createNamedParameter('rejected')))
            ->andWhere($qb->expr()->neq('id', $qb->createNamedParameter($request->getId(), IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->orX(
                $qb->expr()->iLike('username', $qb->createNamedParameter(
                    $this->db->escapeLikeParameter(trim($request->getUsername()))
                )),
                $qb->expr()->iLike('contact_email', $qb->createNamedParameter(
                    $this->db->escapeLikeParameter(trim($request->getContactEmail()))
                ))
            ))
            ->orderBy('id', 'DESC')->setFirstResult($page * 50)->setMaxResults($limit);
        return $this->findEntities($qb);
    }

    public function queueForApproval(int $id, string $actor): bool {
        return $this->guardRequest($id, fn() => $this->queueForApprovalOpen($id, $actor));
    }

    private function queueForApprovalOpen(int $id, string $actor): bool {
        $now = time();
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->getTableName())
            ->set('status', $qb->createNamedParameter('queued'))
            ->set('updated_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('reviewed_by', $qb->createNamedParameter($actor))
            ->set('reviewed_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('error_message', $qb->createNamedParameter(''))
            ->set('claim_token', $qb->createNamedParameter(''))
            ->set('claimed_at', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT))
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('pending')));
        return $qb->executeStatement() === 1;
    }

    public function reject(int $id, string $actor, string $reason): bool {
        $now = time();
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->getTableName())
            ->set('status', $qb->createNamedParameter('rejected'))
            ->set('updated_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('reviewed_by', $qb->createNamedParameter($actor))
            ->set('reviewed_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('error_message', $qb->createNamedParameter($reason))
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('pending')));
        return $qb->executeStatement() === 1;
    }

    public function retry(int $id, string $actor): bool {
        return $this->guardRequest($id, fn() => $this->retryOpen($id, $actor));
    }

    private function retryOpen(int $id, string $actor): bool {
        $now = time();
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->getTableName())
            ->set('status', $qb->createNamedParameter('queued'))
            ->set('updated_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('reviewed_by', $qb->createNamedParameter($actor))
            ->set('reviewed_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('error_message', $qb->createNamedParameter(''))
            ->set('claim_token', $qb->createNamedParameter(''))
            ->set('claimed_at', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT))
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('failed')));
        return $qb->executeStatement() === 1;
    }

    public function queueForResend(int $id, string $actor, int $invitationDays): bool {
        return $this->guardRequest($id, fn() => $this->queueForResendOpen($id, $actor, $invitationDays));
    }

    private function queueForResendOpen(int $id, string $actor, int $invitationDays): bool {
        $now = time();
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->getTableName())
            ->set('status', $qb->createNamedParameter('queued'))
            ->set('job_type', $qb->createNamedParameter('resend'))
            ->set('invitation_days', $qb->createNamedParameter($invitationDays, IQueryBuilder::PARAM_INT))
            ->set('updated_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('reviewed_by', $qb->createNamedParameter($actor))
            ->set('reviewed_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
            ->set('error_message', $qb->createNamedParameter(''))
            ->set('claim_token', $qb->createNamedParameter(''))
            ->set('claimed_at', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT))
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('completed')))
            ->andWhere($qb->expr()->neq('mailbox', $qb->createNamedParameter('')));
        return $qb->executeStatement() === 1;
    }

    public function claimNext(): ?AccountRequest {
        return $this->closure->serialized(fn() => $this->claimNextOpen());
    }

    private function claimNextOpen(): ?AccountRequest {
        for ($attempt = 0; $attempt < 3; $attempt++) {
            $candidate = $this->findNextQueued();
            if ($candidate === null) {
                return null;
            }

            $token = bin2hex(random_bytes(24));
            $now = time();
            $qb = $this->db->getQueryBuilder();
            $qb->update($this->getTableName())
                ->set('status', $qb->createNamedParameter('running'))
                ->set('claim_token', $qb->createNamedParameter($token))
                ->set('claimed_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
                ->set('updated_at', $qb->createNamedParameter($now, IQueryBuilder::PARAM_INT))
                ->where($qb->expr()->eq('id', $qb->createNamedParameter($candidate->getId(), IQueryBuilder::PARAM_INT)))
                ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('queued')));

            if ($qb->executeStatement() === 1) {
                return $this->find($candidate->getId());
            }
        }

        return null;
    }

    public function complete(int $id, string $claimToken, string $mailbox): bool {
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->getTableName())
            ->set('status', $qb->createNamedParameter('completed'))
            ->set('mailbox', $qb->createNamedParameter($mailbox))
            ->set('error_message', $qb->createNamedParameter(''))
            ->set('updated_at', $qb->createNamedParameter(time(), IQueryBuilder::PARAM_INT))
            ->set('claim_token', $qb->createNamedParameter(''))
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('running')))
            ->andWhere($qb->expr()->eq('claim_token', $qb->createNamedParameter($claimToken)));
        return $qb->executeStatement() === 1;
    }

    public function fail(
        int $id,
        string $claimToken,
        string $error,
        bool $preserveCompleted = false,
    ): bool {
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->getTableName())
            ->set('status', $qb->createNamedParameter($preserveCompleted ? 'completed' : 'failed'))
            ->set('error_message', $qb->createNamedParameter(mb_substr($error, 0, 4000)))
            ->set('updated_at', $qb->createNamedParameter(time(), IQueryBuilder::PARAM_INT))
            ->set('claim_token', $qb->createNamedParameter(''))
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('running')))
            ->andWhere($qb->expr()->eq('claim_token', $qb->createNamedParameter($claimToken)));
        return $qb->executeStatement() === 1;
    }

    private function findNextQueued(): ?AccountRequest {
        $qb = $this->db->getQueryBuilder();
        $qb->select('r.*')->from($this->getTableName(), 'r')
            ->leftJoin('r', 'covin_account_closure', 'c', $qb->expr()->eq('r.username', 'c.username'))
            ->where($qb->expr()->eq('r.status', $qb->createNamedParameter('queued')))
            ->andWhere($qb->expr()->orX(
                $qb->expr()->isNull('c.username'),
                $qb->expr()->eq('c.state', $qb->createNamedParameter('open'))
            ))
            ->orderBy('r.id', 'ASC')
            ->setMaxResults(1);

        try {
            return $this->findEntity($qb);
        } catch (DoesNotExistException $e) {
            return null;
        }
    }
}
