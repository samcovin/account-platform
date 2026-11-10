<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Db;

use OCP\AppFramework\Db\Entity;

/**
 * @method int getId()
 * @method int getRequestId()
 * @method void setRequestId(int $value)
 * @method string getActor()
 * @method void setActor(string $value)
 * @method string getAction()
 * @method void setAction(string $value)
 * @method string getDetails()
 * @method void setDetails(string $value)
 * @method int getCreatedAt()
 * @method void setCreatedAt(int $value)
 */
final class AuditEvent extends Entity implements \JsonSerializable {
    protected $requestId = 0;
    protected $actor = '';
    protected $action = '';
    protected $details = '';
    protected $createdAt = 0;

    public function __construct() {
        $this->addType('id', 'integer');
        $this->addType('requestId', 'integer');
        $this->addType('createdAt', 'integer');
    }

    public function jsonSerialize(): array {
        return [
            'id' => $this->getId(),
            'requestId' => $this->getRequestId(),
            'actor' => $this->getActor(),
            'action' => $this->getAction(),
            'details' => $this->getDetails(),
            'createdAt' => $this->getCreatedAt(),
        ];
    }
}
