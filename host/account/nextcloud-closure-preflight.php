<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin
declare(strict_types=1);

// Capture before bootstrap; groups come from the normal occ user:info command.
define('COVIN_CLOSURE_UID', getenv('COVIN_CLOSURE_UID'));
define('COVIN_CLOSURE_GROUPS', getenv('COVIN_CLOSURE_GROUPS'));
define('OC_CONSOLE', true);

try {
    $uid = COVIN_CLOSURE_UID;
    if (!is_string($uid)
        || !preg_match('/^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$/D', $uid)) {
        throw new RuntimeException('Invalid target');
    }
    $groups = json_decode(
        COVIN_CLOSURE_GROUPS, true, 512, JSON_THROW_ON_ERROR
    );
    if (!is_array($groups) || !array_is_list($groups)) {
        throw new RuntimeException('Invalid group list');
    }
    foreach ($groups as $group) {
        if (!is_string($group) || $group === '') {
            throw new RuntimeException('Invalid group');
        }
    }
    if (count($groups) !== count(array_unique($groups))) {
        throw new RuntimeException('Duplicate groups');
    }

    require '/var/www/html/lib/base.php';
    // No user-session setup, filesystem initialization, export, or write query.
    $uid = COVIN_CLOSURE_UID;
    $groups = json_decode(COVIN_CLOSURE_GROUPS, true, 512, JSON_THROW_ON_ERROR);
    $principal = 'principals/users/' . $uid;
    $mailbox = $uid . '@example.test';
    $db = \OC::$server->getDatabaseConnection();
    $intType = \OCP\DB\QueryBuilder\IQueryBuilder::PARAM_INT;
    $stringArrayType = \OCP\DB\QueryBuilder\IQueryBuilder::PARAM_STR_ARRAY;
    $report = [
        'group_file_shares_received' => 0,
        'published_owned_calendars' => 0,
    ];

    $q = $db->getQueryBuilder();
    $q->select('id')->from('share')->where($q->expr()->orX(
        $q->expr()->eq('uid_owner', $q->createNamedParameter($uid)),
        $q->expr()->eq('uid_initiator', $q->createNamedParameter($uid))
    ));
    $result = $q->executeQuery();
    $report['file_shares_owned_or_initiated'] = count($result->fetchAll());
    $result->closeCursor();

    $q = $db->getQueryBuilder();
    $q->select('id')->from('share')
        ->where($q->expr()->eq('share_with', $q->createNamedParameter($uid)))
        ->andWhere($q->expr()->eq('share_type', $q->createNamedParameter(0, $intType)));
    $result = $q->executeQuery();
    $report['direct_user_file_shares_received'] = count($result->fetchAll());
    $result->closeCursor();

    if ($groups !== []) {
        $q = $db->getQueryBuilder();
        $q->select('id')->from('share')
            ->where($q->expr()->eq('share_type', $q->createNamedParameter(1, $intType)))
            ->andWhere($q->expr()->in(
                'share_with', $q->createNamedParameter($groups, $stringArrayType)
            ));
        $result = $q->executeQuery();
        $report['group_file_shares_received'] = count($result->fetchAll());
        $result->closeCursor();
    }

    $backends = [
        'calendars' => \OC::$server->get(\OCA\DAV\CalDAV\CalDavBackend::class),
        'addressbooks' => \OC::$server->get(\OCA\DAV\CardDAV\CardDavBackend::class),
    ];
    if (!defined(\OCA\DAV\CalDAV\CalDavBackend::class . '::ACCESS_PUBLIC')) {
        throw new RuntimeException('Calendar publication constant unavailable');
    }
    foreach ($backends as $table => $backend) {
        $q = $db->getQueryBuilder();
        $q->select('id')->from($table)->where($q->expr()->eq(
            'principaluri', $q->createNamedParameter($principal)
        ));
        $result = $q->executeQuery();
        $resources = $result->fetchAll();
        $result->closeCursor();
        $report['owned_' . $table] = count($resources);
        $shareKey = $table === 'calendars'
            ? 'calendar_recipient_shares' : 'addressbook_recipient_shares';
        $report[$shareKey] = 0;
        foreach ($resources as $resource) {
            $id = (int)$resource['id'];
            $report[$shareKey] += count($backend->getShares($id));
            if ($table !== 'calendars') {
                continue;
            }
            $q = $db->getQueryBuilder();
            $q->select('access')->from('dav_shares')
                ->where($q->expr()->eq('type', $q->createNamedParameter('calendar')))
                ->andWhere($q->expr()->eq('resourceid', $q->createNamedParameter($id, $intType)));
            $result = $q->executeQuery();
            foreach ($result->fetchAll() as $share) {
                if ((int)$share['access'] === \OCA\DAV\CalDAV\CalDavBackend::ACCESS_PUBLIC) {
                    $report['published_owned_calendars']++;
                    break;
                }
            }
            $result->closeCursor();
        }
    }

    $q = $db->getQueryBuilder();
    $q->select('id', 'username', 'mailbox', 'status', 'job_type')
        ->from('covin_account_requests')
        ->where($q->expr()->orX(
            $q->expr()->eq('username', $q->createNamedParameter($uid)),
            $q->expr()->eq('mailbox', $q->createNamedParameter($mailbox))
        ));
    $result = $q->executeQuery();
    $report['requests'] = [];
    foreach ($result->fetchAll() as $row) {
        $report['requests'][] = [
            'id' => (int)$row['id'],
            'status' => $row['status'],
            'job_type' => $row['job_type'],
            'username_matches' => $row['username'] === $uid,
            'mailbox_matches' => $row['mailbox'] === $mailbox,
        ];
    }
    $result->closeCursor();

    echo 'COVIN_JSON=' . json_encode($report, JSON_THROW_ON_ERROR) . PHP_EOL;
} catch (\Throwable $error) {
    fwrite(STDERR, 'STOP: read-only resource inventory failed: '
        . get_class($error) . PHP_EOL);
    exit(1);
}
