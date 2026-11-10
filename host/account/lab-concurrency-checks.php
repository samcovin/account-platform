<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);

/** Pure assertions shared by the isolated harness and standalone unit tests. */
function covinCheckRace(string $scenario, array $a, array $b, string $status, ?array $registry, int $id): void {
    $closing = $registry !== null && ($registry['state'] ?? null) === 'closing' && ($registry['execution_hash'] ?? null) === '';
    $open = $registry === null || (($registry['state'] ?? null) === 'open' && ($registry['execution_hash'] ?? null) === '');
    $accepted = fn(array $r): bool => $r === ['outcome' => 'accepted'];
    $refused = fn(array $r): bool => $r === ['outcome' => 'refused'];
    $pass = false;
    if (in_array($scenario, ['approval', 'retry'], true)) {
        $original = $scenario === 'approval' ? 'pending' : 'failed';
        $pass = $accepted($b) && $closing
            && (($accepted($a) && $status === 'queued') || ($refused($a) && $status === $original));
    } elseif ($scenario === 'resend') {
        $pass = ($accepted($a) && $refused($b) && $open && $status === 'queued')
            || ($refused($a) && $accepted($b) && $closing && $status === 'completed');
    } elseif ($scenario === 'claim') {
        $pass = ($a === ['outcome' => 'claimed', 'id' => $id] && $refused($b) && $open && $status === 'running')
            || ($a === ['outcome' => 'none'] && $accepted($b) && $closing && $status === 'queued');
    } elseif ($scenario === 'execution') {
        $reserved = $registry !== null && ($registry['state'] ?? null) === 'open'
            && is_string(($registry['execution_hash'] ?? null)) && preg_match('/^[a-f0-9]{64}$/D', ($registry['execution_hash'] ?? null));
        $pass = $status === 'completed' && (($accepted($a) && $refused($b) && $reserved)
            || ($refused($a) && $accepted($b) && $closing));
    } elseif ($scenario === 'double-claim') {
        $claimed = ['outcome' => 'claimed', 'id' => $id]; $none = ['outcome' => 'none'];
        $pass = $open && $status === 'running' && (($a === $claimed && $b === $none) || ($b === $claimed && $a === $none));
    }
    if (!$pass) { throw new \RuntimeException('Concurrency outcome invariant failed: ' . $scenario); }
}
