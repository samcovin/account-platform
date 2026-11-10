<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Settings;

use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\Settings\IIconSection;

final class AdminSection implements IIconSection {
    public function __construct(
        private IL10N $l,
        private IURLGenerator $url,
    ) {
    }

    public function getID(): string {
        return 'covin_account_admin';
    }

    public function getName(): string {
        return $this->l->t('Account approvals');
    }

    public function getPriority(): int {
        return 65;
    }

    public function getIcon(): string {
        return $this->url->imagePath('covin_account_admin', 'app.svg');
    }
}
