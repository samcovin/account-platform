# 2026-11-10 — Independent release-gate validation

Status: implemented and locally tested; not published/deployed

## Request and purpose

Explain each remaining gate, separate maintainer decisions from local engineering
checks and finish the independent checks/fixes. Preserve current licenses and do
not contact production services, push or publish.

## Scope and source

Existing public candidate; feature/release-gate-validation. Initial source remains
staged/uncommitted. Existing BSD/AGPL/license-document files, pins and per-file
assignments are unchanged; new first-party tests/docs use the existing BSD scope.

## Implementation and decisions

Require exactly the six named release gates with valid states. Resolved gates
need a resolution and existing candidate evidence. Missing/empty/duplicate/malformed
gate data cannot imply clearance. Include staged/historical Git-object hygiene
in the public checker when a Git directory is present. Add regression tests.

Add real PHP/form tests using disposable owned loopback PHP/HTTP/SMTP fixtures.
Only a throwaway handler copy changes its two service targets. No source runtime
opt-in was enabled for actual services. Use a signature-verified temporary PHP
8.3.36 runtime with INI loading disabled; no system package was installed and no
runtime binary is bundled in Git. Inventory external dependency boundaries.

## Validation

PHP lint, the 55 existing PHP mock cases, 17 PHP/HTTP fixture tests, Python mocks,
source/license/privacy checks and offline unit verification are classified in
current validation records. Unit verification uses a disposable filesystem root,
not the running service manager. Source-only archive extraction is checked.

PHP-VALIDATION is resolved with actual evidence. Ownership, integration-rights,
security policy, real service/release-scope and publication decisions remain open.
No human gate was resolved automatically. Staged changes were reviewed for secrets
and personal data; original input/archive/reference and license bytes are checked.

## Deployment

Not deployed/pushed/published. No actual account, real email, production database,
retention deadline, configuration or service state changed. No production checkpoint
applies. Fake SMTP messages existed only in fixture memory.

## Rollback and follow-up

Restore only this task's source changes or return to the preserved earlier source
archive; keep unrelated edits and licenses. No production/data rollback is required.
Answer docs/remaining-release-decisions.md before approving a public release or a
separate isolated integration plan. Local fixture success is not encrypted restore
or full application/database integration evidence.
