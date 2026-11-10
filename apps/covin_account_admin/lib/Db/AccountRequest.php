<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Db;

use OCP\AppFramework\Db\Entity;

/**
 * @method int getId()
 * @method string getDisplayName()
 * @method void setDisplayName(string $value)
 * @method string getUsername()
 * @method void setUsername(string $value)
 * @method string getContactEmail()
 * @method void setContactEmail(string $value)
 * @method int getInvitationDays()
 * @method void setInvitationDays(int $value)
 * @method string getJobType()
 * @method void setJobType(string $value)
 * @method string getStatus()
 * @method void setStatus(string $value)
 * @method int getRequestedAt()
 * @method void setRequestedAt(int $value)
 * @method int getUpdatedAt()
 * @method void setUpdatedAt(int $value)
 * @method string getReviewedBy()
 * @method void setReviewedBy(string $value)
 * @method int getReviewedAt()
 * @method void setReviewedAt(int $value)
 * @method string getClaimToken()
 * @method void setClaimToken(string $value)
 * @method int getClaimedAt()
 * @method void setClaimedAt(int $value)
 * @method string getMailbox()
 * @method void setMailbox(string $value)
 * @method string getErrorMessage()
 * @method void setErrorMessage(string $value)
 */
final class AccountRequest extends Entity implements \JsonSerializable {
    protected $displayName = '';
    protected $username = '';
    protected $contactEmail = '';
    protected $invitationDays = 14;
    protected $jobType = 'provision';
    protected $status = 'pending';
    protected $requestedAt = 0;
    protected $updatedAt = 0;
    protected $reviewedBy = '';
    protected $reviewedAt = 0;
    protected $claimToken = '';
    protected $claimedAt = 0;
    protected $mailbox = '';
    protected $errorMessage = '';

    public function __construct() {
        $this->addType('id', 'integer');
        $this->addType('invitationDays', 'integer');
        $this->addType('requestedAt', 'integer');
        $this->addType('updatedAt', 'integer');
        $this->addType('reviewedAt', 'integer');
        $this->addType('claimedAt', 'integer');
    }

    public function jsonSerialize(): array {
        return [
            'id' => $this->getId(),
            'displayName' => $this->getDisplayName(),
            'username' => $this->getUsername(),
            'contactEmail' => $this->getContactEmail(),
            'invitationDays' => $this->getInvitationDays(),
            'jobType' => $this->getJobType(),
            'status' => $this->getStatus(),
            'requestedAt' => $this->getRequestedAt(),
            'updatedAt' => $this->getUpdatedAt(),
            'reviewedBy' => $this->getReviewedBy(),
            'reviewedAt' => $this->getReviewedAt(),
            'claimedAt' => $this->getClaimedAt(),
            'mailbox' => $this->getMailbox(),
            'errorMessage' => $this->getErrorMessage(),
        ];
    }

    public function toWorkerArray(): array {
        return [
            'id' => $this->getId(),
            'displayName' => $this->getDisplayName(),
            'username' => $this->getUsername(),
            'contactEmail' => $this->getContactEmail(),
            'invitationDays' => $this->getInvitationDays(),
            'jobType' => $this->getJobType(),
            'mailbox' => $this->getMailbox(),
            'claimToken' => $this->getClaimToken(),
        ];
    }
}
