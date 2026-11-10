# Public-source privacy and safety review

Status: prepared candidate; no publication or deployment. This is a limited
source review with explicit remaining questions, not a certification.

## Personal information and operational details

No embedded production credential, private key, original personal service domain,
personal home path, applicant dataset, database dump, vault, export payload or
raw user log was identified. Literal test passwords/tokens are synthetic and
configuration key names are not secret values. Checks report categories/paths,
not matched values. Source-only packaging excludes Git metadata, local audit,
older references, private preparation records and original private-repository
branch/commit narratives. The candidate Git was initialized independently.

The public copyright name Sam Covin is included by explicit maintainer choice.
The original Covin Family Services app notice and Free Software Foundation
license-document notice remain intentionally. Legacy covin namespaces, protocols,
tables, units, flow/service-account names and paths remain visible for compatibility.
Renaming them requires coordinated schema/adapter tests and is separate work.

Conventional paths and container/service labels remain as documented examples,
not a protected production inventory. Old cached Docker image IDs were removed;
lab app/DB image IDs must now be explicitly provided and reviewed. No private
remote, server account export, DNS/TLS config or actual identity-flow export is
bundled. Public preparation reports use relative paths and no original file logs.

## Unsafe defaults addressed

- Host worker, approver, access/preflight/export/delivery/cleanup entrypoints and
  the existing-container PHP wrapper now require explicit runtime review opt-in
  before their normal service boundary. The public form is disabled unless a
  server-controlled opt-in is supplied. Example systemd units set it to 0.
- The worker no longer prints an unparsed queue response, which could contain
  private fields or a claim token. Synthetic-response tests cover that path.
- Labs retain explicit ISOLATED selection and external pinned 0.4.0 baseline
  validation and additionally require reviewed cached app/database image IDs.
- Fresh Git has no inherited history, identity, hooks/signing overrides or remote.
  The source-only review archive contains no Git directory at all.

## Remaining risks/decisions

Inherited mailbox payload flags do not enforce MFA/TLS. Some tools load local
Mailcow config, use root/Docker and query real services after opt-in. Dry runs
may query services. The guard is accidental-use protection, not authorization.

Public request notifications include applicant names/email/username and remote
address; runtime exceptions and journals can include paths or identifiers. Review
privacy/log minimization and retention before any live run. No real values are
included in this source. Export delivery currently puts the link and archive
password in one email; plaintext master exports remain protected by permissions,
not encryption. Shared-contact scope, E2EE gaps, indefinite rejection history,
seven-day delivery and 180-day master retention require policy decisions.

The app/approver remain candidates. Local PHP lint, PHP mocks and public-form
HTTP behavior with owned loopback HTTP/SMTP fixtures now pass. Full Nextcloud/
Mailcow/Authentik/FPM/TLS integration, real migrations/concurrency and readable
encrypted recovery remain unvalidated. No production service was contacted.

The public checker rejects missing/empty/duplicate/malformed gate records,
requires evidence for resolved gates, and checks staged/historical Git objects as
well as disk files. PHP-VALIDATION was completed with actual local evidence.

## Experimental source-release decisions — 2026-11-10 UTC

The maintainer now requests experimental source release followed by a work fork,
confirms no outside material or known ownership restrictions, and selects GitHub
private vulnerability reporting after final approval. Ownership, security policy
for disabled source examples, and experimental release-scope decisions are
recorded in LICENSE-MAP.json. This does not approve a real-service installation
or mark integration/upgrade/recovery tests as passed. Reporting is not active yet;
it must be enabled and verified after final approval and before the first push.

The maintainer accepted mixed-license source-only distribution, with future
combined-work review still required. Only exact publication approval remains open. The separate local approval dossier
shows proposed names, author/committer,
file manifest, tree hash and archive hash. The personal Git identity is approved and selected locally. No GitHub repository,
commit, remote, fork, account setting, push, publication or deployment was created. The work fork of a
public repository will be public, with the personal source authorship retained.
See [plain-language decisions](docs/remaining-release-decisions.md),
[experimental evidence matrix](docs/experimental-release.md),
[dependency inventory](docs/dependency-boundaries.md) and RELEASE_CHECKLIST.md.
