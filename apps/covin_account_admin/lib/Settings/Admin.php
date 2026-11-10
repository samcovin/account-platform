<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Settings;

use OCP\AppFramework\Http\TemplateResponse;
use OCP\Settings\ISettings;

final class Admin implements ISettings {
    public function getForm(): TemplateResponse {
        return new TemplateResponse('covin_account_admin', 'admin');
    }

    public function getSection(): string {
        return 'covin_account_admin';
    }

    public function getPriority(): int {
        return 10;
    }
}
