<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin
declare(strict_types=1);

// Arguments are captured before Nextcloud bootstrap can change environment state.
define('COVIN_EXPORT_ARGUMENTS', array_slice($argv, 1));
try {
    umask(0077);
    [$uid, $out, $includeShared] = COVIN_EXPORT_ARGUMENTS;
    if (!preg_match('/^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$/D', $uid)
        || !preg_match('#^/tmp/covin-export-[a-f0-9]{32}/payload$#D', $out)
        || !in_array($includeShared, ['yes', 'no'], true)) {
        throw new RuntimeException('Invalid export arguments');
    }
    define('OC_CONSOLE', true);
    require '/var/www/html/lib/base.php';
    $user = \OC::$server->get(\OCP\IUserManager::class)->get($uid);
    if ($user === null) throw new RuntimeException('Account not found');
    \OC::$server->get(\OCP\IUserSession::class)->setUser($user);
    \OC_Util::setupFS($uid);
    $home = \OC::$server->get(\OCP\Files\IRootFolder::class)->getUserFolder($uid);
    $storage = $home->getStorage()->getId();
    $report = ['user' => $uid, 'files' => [], 'directories' => [],
        'excluded_storage_paths' => [], 'addressbooks' => [], 'calendars' => []];
    foreach (['files', 'contacts', 'calendars'] as $dir) {
        if (!mkdir($out . '/' . $dir, 0700)) throw new RuntimeException('Output directory failure');
    }
    $walk = function ($folder, string $relative = '') use (&$walk, &$report, $storage, $out) {
        foreach ($folder->getDirectoryListing() as $node) {
            $name = $node->getName();
            if ($name === '' || in_array($name, ['.', '..'], true)
                || str_contains($name, '/') || str_contains($name, "\0")) {
                throw new RuntimeException('Unsafe path');
            }
            $path = $relative === '' ? $name : $relative . '/' . $name;
            if ($node->getStorage()->getId() !== $storage) {
                $report['excluded_storage_paths'][] = $path;
                continue;
            }
            $target = $out . '/files/' . $path;
            if ($node instanceof \OCP\Files\Folder) {
                if (!mkdir($target, 0700)) throw new RuntimeException('Output folder failure');
                $report['directories'][] = $path;
                $walk($node, $path);
            } elseif ($node instanceof \OCP\Files\File) {
                $etag = $node->getEtag();
                $size = $node->getSize();
                $input = $node->fopen('r');
                if (!is_resource($input)) throw new RuntimeException('Source read failure');
                $output = fopen($target, 'xb');
                if (!is_resource($output)) {
                    fclose($input);
                    throw new RuntimeException('Output file failure');
                }
                try { $copied = stream_copy_to_stream($input, $output); }
                finally { fclose($input); fclose($output); }
                if ($copied !== $size || $node->getEtag() !== $etag) {
                    throw new RuntimeException('Incomplete or changing source file');
                }
                $hash = hash_file('sha256', $target);
                if ($hash === false) throw new RuntimeException('Hash failure');
                $report['files'][] = ['path' => $path, 'bytes' => $copied, 'sha256' => $hash];
            } else throw new RuntimeException('Unsupported file node');
        }
    };
    $walk($home);

    $principal = 'principals/users/' . $uid;
    $backend = \OC::$server->get(\OCA\DAV\CardDAV\CardDavBackend::class);
    $db = \OC::$server->getDatabaseConnection();
    // Establish owned IDs independently of shared-book principal rewriting.
    $q = $db->getQueryBuilder();
    $q->select('id')->from('addressbooks')->where($q->expr()->eq(
        'principaluri', $q->createNamedParameter($principal)));
    $result = $q->executeQuery();
    $owned = array_map('strval', array_column($result->fetchAll(), 'id'));
    $result->closeCursor();
    $seen = [];
    foreach ($backend->getAddressBooksForUser($principal) as $book) {
        $id = (string)$book['id'];
        if (!ctype_digit($id)) throw new RuntimeException('Unexpected address book ID');
        if (isset($seen[$id])) continue;
        $seen[$id] = true;
        $isOwned = in_array($id, $owned, true);
        $entry = ['id' => $id, 'uri' => $book['uri'],
            'name' => $book['{DAV:}displayname'] ?? '', 'owned' => $isOwned];
        if (!$isOwned && $includeShared !== 'yes') {
            $entry['excluded'] = 'Shared address books not requested';
            $report['addressbooks'][] = $entry;
            continue;
        }
        $cards = $backend->getCards($id);
        $filename = 'contacts/addressbook-' . $id . '.vcf';
        $fh = fopen($out . '/' . $filename, 'xb');
        if (!is_resource($fh)) throw new RuntimeException('Contact output failure');
        try {
            foreach ($cards as $card) {
                $data = $card['carddata'];
                if (!is_string($data)) throw new RuntimeException('Invalid card data');
                $parsed = \Sabre\VObject\Reader::read($data);
                if ($parsed->name !== 'VCARD') throw new RuntimeException('Invalid vCard');
                $data = rtrim($data, "\r\n") . "\r\n";
                if (fwrite($fh, $data) !== strlen($data)) throw new RuntimeException('Short contact write');
            }
        } finally { fclose($fh); }
        $entry['file'] = $filename;
        $entry['contacts'] = count($cards);
        $report['addressbooks'][] = $entry;
    }
    // Owned local calendars only. Shared calendars/subscriptions are out of scope.
    $q = $db->getQueryBuilder();
    $q->select('id', 'uri')->from('calendars')->where($q->expr()->eq(
        'principaluri', $q->createNamedParameter($principal)));
    $result = $q->executeQuery();
    foreach ($result->fetchAll() as $calendar) {
        if (!ctype_digit((string)$calendar['id'])) throw new RuntimeException('Unexpected calendar ID');
        $report['calendars'][] = ['id' => (string)$calendar['id'], 'uri' => $calendar['uri']];
    }
    $result->closeCursor();
    $report['complete'] = true;
    $json = json_encode($report, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR);
    if (file_put_contents($out . '/nextcloud-report.json', $json) !== strlen($json)) {
        throw new RuntimeException('Report write failure');
    }
    echo "NEXTCLOUD_EXPORT_COMPLETE\n";
} catch (\Throwable $e) {
    // Do not print file names or contact content to terminal logs.
    fwrite(STDERR, 'Export failed: ' . get_class($e) . ' at line ' . $e->getLine() . "\n");
    exit(1);
}
