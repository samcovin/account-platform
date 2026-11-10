<?php

declare(strict_types=1);

return [
    'routes' => [
        ['name' => 'api#browse', 'url' => '/request-browser', 'verb' => 'GET'],
        ['name' => 'api#matches', 'url' => '/requests/{id}/matches', 'verb' => 'GET'],
        ['name' => 'api#create', 'url' => '/requests', 'verb' => 'POST'],
        ['name' => 'api#list', 'url' => '/requests', 'verb' => 'GET'],
        ['name' => 'api#audit', 'url' => '/requests/{id}/audit', 'verb' => 'GET'],
        ['name' => 'api#approve', 'url' => '/requests/{id}/approve', 'verb' => 'POST'],
        ['name' => 'api#reject', 'url' => '/requests/{id}/reject', 'verb' => 'POST'],
        ['name' => 'api#retry', 'url' => '/requests/{id}/retry', 'verb' => 'POST'],
        ['name' => 'api#resend', 'url' => '/requests/{id}/resend', 'verb' => 'POST'],
        ['name' => 'public_request#submit', 'url' => '/public/requests', 'verb' => 'POST'],
    ],
];
