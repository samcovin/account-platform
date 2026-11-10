<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Controller;

use OCA\CovinAccountAdmin\Db\AccountRequest;
use OCA\CovinAccountAdmin\Db\AccountRequestMapper;
use OCA\CovinAccountAdmin\Db\AuditEventMapper;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\PublicPage;
use OCP\AppFramework\Http\DataResponse;
use OCP\IConfig;
use OCP\IRequest;

final class PublicRequestController extends Controller {
    private const APP_ID = 'covin_account_admin';
    private const SECRET_KEY = 'public_ingress_secret';
    private const MAX_CLOCK_SKEW_SECONDS = 300;

    public function __construct(
        string $appName,
        IRequest $request,
        private IConfig $config,
        private AccountRequestMapper $requests,
        private AuditEventMapper $auditEvents,
    ) {
        parent::__construct($appName, $request);
    }

    #[PublicPage]
    #[NoCSRFRequired]
    public function submit(
        string $displayName = '',
        string $username = '',
        string $contactEmail = '',
        int $invitationDays = 14,
    ): DataResponse {
        if (!$this->hasValidSignature(
            $displayName,
            $username,
            $contactEmail,
            $invitationDays
        )) {
            return new DataResponse(
                ['error' => 'Request authorization failed.'],
                Http::STATUS_FORBIDDEN
            );
        }

        try {
            [$displayName, $username, $contactEmail] = $this->validateFields(
                $displayName,
                $username,
                $contactEmail
            );

            if ($invitationDays !== 14) {
                throw new \InvalidArgumentException(
                    'Public requests must use the 14-day invitation default.'
                );
            }

            if ($this->requests->hasOpenUsername($username)) {
                return new DataResponse(
                    ['accepted' => true, 'created' => false],
                    Http::STATUS_ACCEPTED
                );
            }

            $now = time();
            $accountRequest = new AccountRequest();
            $accountRequest->setDisplayName($displayName);
            $accountRequest->setUsername($username);
            $accountRequest->setContactEmail($contactEmail);
            $accountRequest->setInvitationDays(14);
            $accountRequest->setJobType('provision');
            $accountRequest->setStatus('pending');
            $accountRequest->setRequestedAt($now);
            $accountRequest->setUpdatedAt($now);
            $accountRequest = $this->requests->insertGuarded($accountRequest);
            if ($accountRequest === null) {
                // Same response as an existing request: do not disclose closure history.
                return new DataResponse(['accepted' => true, 'created' => false], Http::STATUS_ACCEPTED);
            }

            $this->auditEvents->record(
                $accountRequest->getId(),
                'public-form',
                'submitted',
                'Request submitted through the public account form with a 14-day invitation.'
            );

            return new DataResponse(
                ['accepted' => true, 'created' => true],
                Http::STATUS_CREATED
            );
        } catch (\InvalidArgumentException $e) {
            return new DataResponse(
                ['error' => $e->getMessage()],
                Http::STATUS_BAD_REQUEST
            );
        }
    }

    private function hasValidSignature(
        string $displayName,
        string $username,
        string $contactEmail,
        int $invitationDays,
    ): bool {
        $secret = trim($this->config->getAppValue(
            self::APP_ID,
            self::SECRET_KEY,
            ''
        ));
        $timestamp = trim($this->request->getHeader('X-Covin-Timestamp'));
        $nonce = strtolower(trim($this->request->getHeader('X-Covin-Nonce')));
        $signature = strtolower(trim($this->request->getHeader('X-Covin-Signature')));

        if (
            !preg_match('/^[a-f0-9]{64}$/D', $secret) ||
            !preg_match('/^[0-9]{10,12}$/D', $timestamp) ||
            !preg_match('/^[a-f0-9]{32}$/D', $nonce) ||
            !preg_match('/^[a-f0-9]{64}$/D', $signature)
        ) {
            return false;
        }

        if (abs(time() - (int)$timestamp) > self::MAX_CLOCK_SKEW_SECONDS) {
            return false;
        }

        $payload = json_encode(
            [
                'displayName' => $displayName,
                'username' => $username,
                'contactEmail' => $contactEmail,
                'invitationDays' => $invitationDays,
            ],
            JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
        );

        $expected = hash_hmac(
            'sha256',
            $timestamp . "\n" . $nonce . "\n" . $payload,
            $secret
        );

        return hash_equals($expected, $signature);
    }

    /** @return array{string, string, string} */
    private function validateFields(
        string $displayName,
        string $username,
        string $contactEmail,
    ): array {
        $displayName = trim($displayName);
        $username = mb_strtolower(trim($username));
        $contactEmail = trim($contactEmail);

        if (
            mb_strlen($displayName) < 2 ||
            mb_strlen($displayName) > 100 ||
            preg_match('/[\r\n]/', $displayName)
        ) {
            throw new \InvalidArgumentException(
                'Display name must be between 2 and 100 characters without line breaks.'
            );
        }

        if (!preg_match('/^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])$/D', $username)) {
            throw new \InvalidArgumentException(
                'Username must be 3–64 lowercase letters, numbers, dots, underscores, or hyphens and must begin and end with a letter or number.'
            );
        }

        if (in_array($username, [
            'admin',
            'administrator',
            'abuse',
            'postmaster',
            'hostmaster',
            'webmaster',
            'security',
            'root',
            'mailer-daemon',
            'requests',
            'support',
            'billing',
            'noreply',
            'no-reply',
        ], true)) {
            throw new \InvalidArgumentException('That username is reserved.');
        }

        if (
            strlen($contactEmail) > 254 ||
            preg_match('/[\r\n]/', $contactEmail) ||
            filter_var($contactEmail, FILTER_VALIDATE_EMAIL) === false
        ) {
            throw new \InvalidArgumentException(
                'Enter a valid contact email address.'
            );
        }

        return [$displayName, $username, $contactEmail];
    }
}
