# Prior local validation checkpoint — 2026-11-10 01:22 UTC

This is the earlier local runtime/source evidence checkpoint. Subsequent release
decisions are in [remaining decisions](remaining-release-decisions.md), and current
source-preparation checks in [release validation](experimental-release-validation.json).

All **166 Python tests** passed without skips, errors or failures: 55 offline
checks under tools, 73 account/guard/lab mocks, 21 export/delivery/retention mocks
and 17 real PHP/form HTTP tests. The first three suites blocked service commands
in PATH. The form suite started only owned disposable loopback PHP, HTTP ingress
and fake SMTP fixtures; fake messages remained in memory. A throwaway handler
copy changed only the ingress URL and SMTP target. No existing service, real
recipient or production system was contacted.

PHP **8.3.36** was extracted temporarily from a signature-verified distro package,
with host INI loading disabled (`-n`). It was not installed system-wide or bundled
in Git/source archives. All **30 PHP files** passed lint. The PHP closure-guard
suite passed **29** mock cases and the concurrency-outcome suite passed **26**.
These 55 PHP cases are additional to the 166 Python cases. Synthetic outcome
checks are not actual database concurrency, migration or restore evidence.

Source hygiene and all **35 syntax checks** passed (30 PHP and 5 Bash/JavaScript).
All **21 Python files** compiled in memory; 2 XML/SVG files parsed. Local document
links were checked. Four systemd service/timer files passed offline verification
against a disposable filesystem root with fake prerequisite targets/executables;
no service manager, Docker, timer or service was started. Exact classifications,
commands and counts are in [validation-results.json](validation-results.json).

The public checker now rejects missing, empty, duplicate or malformed gate lists,
requires a resolution and existing-file evidence for resolved gates, and checks
Git's index/stored objects as well as disk files. The previous empty-list bypass
was reproduced without modifying the input. Regression tests also cover a secret
left only in the index. The checker and both development/initial-import hygiene
modes passed. At this checkpoint, `--release` returned **2** with five unresolved
gates; that was enforcement, not publication approval. Staged changes were reviewed.
Subsequent maintainer decisions change the gate count, not those test results.

All 26 app files and modes, the app metadata, three license-notice pins and every
existing per-file license assignment are unchanged. New tests/docs use the
existing first-party BSD scope; no component was relicensed. Original repository,
saved handoff, prior work/reference copy and earlier source archive are preserved.
Source-only archive extraction checks bytes/modes, excluded Git/private/reference
files and normalized archive ownership. These checks do not prove encrypted data
can be restored.

PHP-VALIDATION was completed. Ownership, distribution, security/release scope and
publication gates were pending at this checkpoint; see the current
[remaining decisions](remaining-release-decisions.md) for later maintainer answers.
Real services,
framework/FPM/TLS/browser integration, populated lab upgrades, actual database
concurrency, encrypted restore and user acceptance remain untested. Runtime
opt-in guards prevent accidental use; they are not an authorization boundary.
Nothing was pushed, published, deployed or run against real services.
