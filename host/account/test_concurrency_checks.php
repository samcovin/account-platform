<?php
// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026 Sam Covin

declare(strict_types=1);
require __DIR__ . '/lab-concurrency-checks.php';

// Pure outcome checks only: no Nextcloud bootstrap, network or database.
$yes = ['outcome' => 'accepted']; $no = ['outcome' => 'refused'];
$claim = ['outcome' => 'claimed', 'id' => 1002]; $none = ['outcome' => 'none'];
$closing = ['state' => 'closing', 'execution_hash' => ''];
$open = ['state' => 'open', 'execution_hash' => ''];
$reserved = ['state' => 'open', 'execution_hash' => str_repeat('a', 64)];
$cases = [
    ['approval queues before freeze', true, 'approval', $yes, $yes, 'queued', $closing],
    ['approval refused after freeze', true, 'approval', $no, $yes, 'pending', $closing],
    ['retry queues before freeze', true, 'retry', $yes, $yes, 'queued', $closing],
    ['retry refused after freeze', true, 'retry', $no, $yes, 'failed', $closing],
    ['resend wins', true, 'resend', $yes, $no, 'queued', null],
    ['freeze wins over resend', true, 'resend', $no, $yes, 'completed', $closing],
    ['claim wins', true, 'claim', $claim, $no, 'running', null],
    ['freeze wins over claim', true, 'claim', $none, $yes, 'queued', $closing],
    ['execution wins', true, 'execution', $yes, $no, 'completed', $reserved],
    ['freeze wins over execution', true, 'execution', $no, $yes, 'completed', $closing],
    ['first claimant wins', true, 'double-claim', $claim, $none, 'running', null],
    ['second claimant wins', true, 'double-claim', $none, $claim, 'running', $open],
    ['queued approval without closure rejected', false, 'approval', $yes, $yes, 'queued', null],
    ['refused retry cannot mutate state', false, 'retry', $no, $yes, 'queued', $closing],
    ['resend and freeze both accepted rejected', false, 'resend', $yes, $yes, 'queued', $closing],
    ['claim and freeze both accepted rejected', false, 'claim', $claim, $yes, 'running', $closing],
    ['execution and freeze both accepted rejected', false, 'execution', $yes, $yes, 'completed', $reserved],
    ['two claimants rejected', false, 'double-claim', $claim, $claim, 'running', null],
    ['no successful claimant rejected', false, 'double-claim', $none, $none, 'queued', null],
    ['wrong claimed row rejected', false, 'claim', ['outcome' => 'claimed', 'id' => 9999], $no, 'running', null],
    ['error is not a business refusal', false, 'resend', ['outcome' => 'error'], $yes, 'completed', $closing],
    ['unknown scenario rejected', false, 'unknown', $yes, $no, 'queued', null],
    ['malformed registry rejected', false, 'execution', $yes, $no, 'completed', []],
    ['invalid execution reservation rejected', false, 'execution', $yes, $no, 'completed', ['state' => 'open', 'execution_hash' => 'invalid']],
    ['closed is not a new freeze result', false, 'resend', $no, $yes, 'completed', ['state' => 'closed', 'execution_hash' => '']],
    ['unexpected result fields rejected', false, 'approval', ['outcome' => 'accepted', 'extra' => true], $yes, 'queued', $closing],
];
$failures = 0;
foreach ($cases as [$name, $expected, $scenario, $a, $b, $status, $registry]) {
    $passed = true;
    try { covinCheckRace($scenario, $a, $b, $status, $registry, 1002); }
    catch (\RuntimeException $error) { $passed = false; }
    if ($passed !== $expected) { $failures++; }
    echo $passed === $expected ? 'PASS: ' : 'FAIL: ', $name, PHP_EOL;
}
echo 'Concurrency outcome tests: ', count($cases), '; failures: ', $failures, PHP_EOL;
exit($failures === 0 ? 0 : 1);
