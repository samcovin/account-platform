<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Controller;

use OCA\CovinAccountAdmin\Db\AccountRequest;
use OCA\CovinAccountAdmin\Db\AccountRequestMapper;
use OCA\CovinAccountAdmin\Db\AuditEventMapper;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\IGroupManager;
use OCP\IRequest;
use OCP\IUserSession;

final class ApiController extends Controller {
    public function __construct(
        string $appName,
        IRequest $request,
        private IUserSession $userSession,
        private IGroupManager $groupManager,
        private AccountRequestMapper $requests,
        private AuditEventMapper $auditEvents,
    ) {
        parent::__construct($appName, $request);
    }

    public function create(
        string $displayName,
        string $username,
        string $contactEmail,
        int $invitationDays = 14,
    ): DataResponse {
        $actor = $this->requireAdmin();

        try {
            [$displayName, $username, $contactEmail] = $this->validateFields(
                $displayName,
                $username,
                $contactEmail
            );
            $invitationDays = $this->validateInvitationDays($invitationDays);

            if ($this->requests->hasOpenUsername($username)) {
                return new DataResponse(
                    ['error' => 'An active request already uses this username.'],
                    Http::STATUS_CONFLICT
                );
            }

            $now = time();
            $request = new AccountRequest();
            $request->setDisplayName($displayName);
            $request->setUsername($username);
            $request->setContactEmail($contactEmail);
            $request->setInvitationDays($invitationDays);
            $request->setJobType('provision');
            $request->setStatus('pending');
            $request->setRequestedAt($now);
            $request->setUpdatedAt($now);
            $request = $this->requests->insertGuarded($request);
            if ($request === null) {
                return new DataResponse(['error' => 'Username is unavailable.'], Http::STATUS_CONFLICT);
            }

            $this->auditEvents->record(
                $request->getId(),
                $actor,
                'created',
                'Request entered by an administrator with a ' . $invitationDays . '-day invitation.'
            );

            return new DataResponse($request, Http::STATUS_CREATED);
        } catch (\InvalidArgumentException $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    public function list(): DataResponse {
        $this->requireAdmin();
        return new DataResponse($this->requests->findRecent());
    }

    public function browse(string $view = 'active', string $search = '', int $page = 0): DataResponse {
        $this->requireAdmin();
        $search = trim($search);
        if (!in_array($view, ['active', 'rejected'], true) || $page < 0 || $page > 1000000 || mb_strlen($search) > 254) {
            return new DataResponse(['error' => 'Invalid search or page.'], Http::STATUS_BAD_REQUEST);
        }
        $items = $this->requests->browse($view, $search, $page);
        $hasMore = count($items) > 50;
        $rows = [];
        foreach (array_slice($items, 0, 50) as $item) {
            $row = $item->jsonSerialize();
            $row['closureState'] = $this->requests->closureState($item->getUsername());
            $row['hasRejectedMatches'] = $item->getStatus() === 'pending'
                && count($this->requests->rejectedMatches($item, 0, 1)) > 0;
            $rows[] = $row;
        }
        return new DataResponse(['items' => $rows, 'hasMore' => $hasMore, 'page' => $page]);
    }

    public function matches(int $id, int $page = 0): DataResponse {
        $this->requireAdmin();
        if ($page < 0 || $page > 1000000) {
            return new DataResponse(['error' => 'Invalid page.'], Http::STATUS_BAD_REQUEST);
        }
        try {
            $item = $this->requests->find($id);
            $matches = $this->requests->rejectedMatches($item, $page);
            return new DataResponse([
                'items' => array_slice($matches, 0, 50),
                'hasMore' => count($matches) > 50,
                'page' => $page,
            ]);
        } catch (\OCP\AppFramework\Db\DoesNotExistException $e) {
            return new DataResponse(['error' => 'Request not found.'], Http::STATUS_NOT_FOUND);
        }
    }

    public function audit(int $id, int $page = 0): DataResponse {
        $this->requireAdmin();
        if ($page < 0 || $page > 1000000) {
            return new DataResponse(['error' => 'Invalid page.'], Http::STATUS_BAD_REQUEST);
        }

        try {
            $this->requests->find($id);
            return new DataResponse($this->auditEvents->findForRequest($id, 100, $page * 100));
        } catch (\OCP\AppFramework\Db\DoesNotExistException $e) {
            return new DataResponse(['error' => 'Request not found.'], Http::STATUS_NOT_FOUND);
        }
    }

    public function approve(int $id, bool $reviewedRejections = false): DataResponse {
        $actor = $this->requireAdmin();
        try {
            $item = $this->requests->find($id);
        } catch (\OCP\AppFramework\Db\DoesNotExistException $e) {
            return new DataResponse(['error' => 'Request not found.'], Http::STATUS_NOT_FOUND);
        }
        $hasMatches = count($this->requests->rejectedMatches($item, 0, 1)) > 0;
        if ($hasMatches && !$reviewedRejections) {
            return new DataResponse(
                ['error' => 'This request matches an archived rejection. Refresh, review the matches, and confirm approval.'],
                Http::STATUS_CONFLICT
            );
        }
        $ok = $this->requests->queueForApproval($id, $actor);

        if ($ok) {
            $this->auditEvents->record($id, $actor, 'approved', 'Queued for the host approval worker.'
                . ($hasMatches ? ' Administrator acknowledged matching archived rejections.' : ''));
        }

        return new DataResponse(
            ['queued' => $ok],
            $ok ? Http::STATUS_OK : Http::STATUS_CONFLICT
        );
    }

    public function reject(int $id, string $reason = ''): DataResponse {
        $actor = $this->requireAdmin();
        $reason = trim($reason);

        if (mb_strlen($reason) > 4000) {
            return new DataResponse(['error' => 'The rejection note is too long.'], Http::STATUS_BAD_REQUEST);
        }

        $ok = $this->requests->reject($id, $actor, $reason);

        if ($ok) {
            $this->auditEvents->record($id, $actor, 'rejected', $reason);
        }

        return new DataResponse(
            ['rejected' => $ok],
            $ok ? Http::STATUS_OK : Http::STATUS_CONFLICT
        );
    }

    public function retry(int $id): DataResponse {
        $actor = $this->requireAdmin();
        $ok = $this->requests->retry($id, $actor);

        if ($ok) {
            $this->auditEvents->record($id, $actor, 'retried', 'Queued again after a worker failure.');
        }

        return new DataResponse(
            ['queued' => $ok],
            $ok ? Http::STATUS_OK : Http::STATUS_CONFLICT
        );
    }

    public function resend(int $id, int $invitationDays = 14): DataResponse {
        $actor = $this->requireAdmin();

        try {
            $invitationDays = $this->validateInvitationDays($invitationDays);
        } catch (\InvalidArgumentException $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }

        $ok = $this->requests->queueForResend($id, $actor, $invitationDays);

        if ($ok) {
            $this->auditEvents->record(
                $id,
                $actor,
                'resend_queued',
                'Queued a replacement ' . $invitationDays . '-day enrollment invitation.'
            );
        }

        return new DataResponse(
            ['queued' => $ok],
            $ok ? Http::STATUS_OK : Http::STATUS_CONFLICT
        );
    }

    private function requireAdmin(): string {
        $user = $this->userSession->getUser();

        if ($user === null || !$this->groupManager->isAdmin($user->getUID())) {
            throw new \OCP\AppFramework\Middleware\Security\Exceptions\NotAdminException();
        }

        return $user->getUID();
    }

    /** @return array{string, string, string} */
    private function validateFields(string $displayName, string $username, string $contactEmail): array {
        $displayName = trim($displayName);
        $username = mb_strtolower(trim($username));
        $contactEmail = trim($contactEmail);

        if ($displayName === '' || mb_strlen($displayName) > 100) {
            throw new \InvalidArgumentException('Display name must be between 1 and 100 characters.');
        }

        if (!preg_match('/^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])$/', $username)) {
            throw new \InvalidArgumentException(
                'Username must be 2–64 lowercase letters, numbers, dots, underscores, or hyphens.'
            );
        }

        if (strlen($contactEmail) > 254 || filter_var($contactEmail, FILTER_VALIDATE_EMAIL) === false) {
            throw new \InvalidArgumentException('Enter a valid contact email address.');
        }

        if (preg_match('/[\r\n]/', $displayName . $contactEmail)) {
            throw new \InvalidArgumentException('Invalid line break in request fields.');
        }

        return [$displayName, $username, $contactEmail];
    }

    private function validateInvitationDays(int $invitationDays): int {
        if (!in_array($invitationDays, [7, 14, 30], true)) {
            throw new \InvalidArgumentException('Invitation duration must be 7, 14, or 30 days.');
        }

        return $invitationDays;
    }
}
