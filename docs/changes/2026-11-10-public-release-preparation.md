# 2026-11-10 — Public-source licensing and safety candidate

Status: implemented and locally tested; not cleared/published/deployed

## Request and purpose

Prepare eventual public source with BSD 3-Clause for maintainer-controlled original
contributions, preserving AGPL/third-party notices and documenting rights questions.
Review privacy, credentials, operational details and unsafe defaults. Publish nothing.

## Scope and source

Separate candidate on feature/public-release-preparation, staged/uncommitted with
normal fresh Git. The maintainer reports generated first-party code at his direction,
allows reuse and explicitly chose Sam Covin for the BSD copyright. The app retains
its existing AGPL notice; no exclusive rights or third-party ownership is invented.

## Implementation and decisions

Add scoped root BSD license, full unchanged AGPL text, existing/external notices,
component/per-file mapping and explicit unresolved owner/release gates. Apply BSD
headers outside the app and retain app bytes/metadata/notices. Remove private
preparation narratives from the public tree; keep audit/reference material outside.

Add deliberate runtime opt-in before normal host-service boundaries and public
form use; disable it in sample units. The worker no longer prints unparsed service
responses. Labs require explicitly supplied reviewed cached image IDs and keep
external pinned baseline validation. Preserve compatible IDs, permission/encryption
boundaries and existing protocol versions; do not guess work MFA/TLS/retention policy.

## Validation

Current results classify syntax/source, offline mocks and local file-copy checks,
with PHP/HTTP, real service/upgrade/concurrency/browser/restore gaps stated. Review
staged source for credentials/personal data, verify original notices and source/
reference/input preservation, and check source-only packaging. An intentionally
failing --release check demonstrates unresolved human gates, not a test failure.

## Deployment

Not published, pushed or deployed. No account, email, schema, production configuration,
retention deadline or service state changed. No production checkpoint applies.

## Rollback and follow-up

Stop using this separate candidate to abandon it; previous inputs/reference remain
unchanged. Resolve questions in LICENSING.md and RELEASE_CHECKLIST.md, complete
applicable runtime validation and review exact publication contents before any
separately authorized public release. Do not erase notices or silently bypass gates.
