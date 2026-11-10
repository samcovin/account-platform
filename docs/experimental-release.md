# Experimental source release scope — 2026-11-10 UTC

Status: public experimental source publication approved; see the dated approval
checkpoint and separate remote execution record. This is
source for inspection and development, not an installable deployment bundle or a
production-readiness claim. Component version strings remain compatibility IDs:
app 0.5.0 candidate, approver 0.3.0 candidate, worker 0.2.0, public handler 0.3.0.
There is no new stable project version, release tag, binary or container release.

## Maintainer decisions recorded

The maintainer requested an experimental source release to a personal GitHub
repository, followed by a work-account fork. The maintainer confirmed there is no
outside input/material or known employer/client/contributor ownership restriction,
building on the earlier permission to reuse the generated first-party work.
This records the maintainer's statement; it is not independent proof of rights.
The BSD copyright name remains Sam Covin. Existing BSD and AGPL notices, app
attribution, app metadata and all existing file-license assignments are preserved.

For this source release, service execution stays disabled by default and runtime
privacy, retention, MFA/TLS and delivery choices remain installation prerequisites.
GitHub private vulnerability reporting is selected, to be enabled and verified
after final approval, before the first source push. It was enabled and verified
on the personal upstream before source push; see SECURITY.md for the dated check.
The source itself cannot enable a repository reporting setting. No private
email address, work account identity or credential is embedded in this release.

The maintainer accepts the source-only mixed-license scope: no dependency
implementations/images/binaries are bundled and combined-distribution obligations
must be reviewed before any deployment or bundling. This does not settle those
future obligations or change an existing license.

See [remaining decisions](remaining-release-decisions.md) for the current gate
states. Accepting experimental scope is not a successful service integration
test. The personal Git identity was explicitly selected. The maintainer approved exact
contents, destinations and publication; see publication-approval.md for evidence.
Actual push/fork verification is recorded separately after execution.

## Evidence and untested integrations

| Area | Actual local evidence | Not tested / no claim made |
| --- | --- | --- |
| PHP and public request handler | 30 PHP files linted with PHP 8.3.36; 55 PHP mock cases; 17 real PHP/HTTP tests with owned local HTTP/SMTP fixtures | Full Nextcloud framework, FPM/Nginx, real TLS/proxy, browser rendering and installed PHP extension/configuration matrix |
| Nextcloud app and closure guards | Fake OCP/DB logic and synthetic concurrency-outcome tests | Real database transactions/races, app install/repair/migrations, Nextcloud 28–35 compatibility, existing-account safety |
| Mailcow and Authentik adapters | Mocked host behavior, protocol and default-refusal checks | Actual API/ORM/flow/schema versions, SSO/MFA/TLS, account provisioning, suspension and session revocation |
| Exports, delivery and cleanup | Python filesystem/adapter mocks and refusal tests | Real account-data extraction, readable encrypted restoration, E2EE completeness, actual mail/upload delivery or retention deletion |
| Units/timers and host configuration | Four unit/timer files passed offline systemd verification with fixture dependencies | A running service manager, timers, Docker/Compose, permissions, scheduling or operational monitoring |
| Install/upgrade labs | Source and mock checks; explicit reviewed image IDs and external hash-pinned 0.4.0 baseline required | Real lab creation, populated upgrades, schema migration, image compatibility or container isolation |

The full local record is [validation.md](validation.md). The newest source-only
preparation checks are recorded separately in
[experimental-release-validation.json](experimental-release-validation.json).
Metadata version ranges are not a tested support matrix. Runtime opt-in is
accidental-use protection, not an authorization boundary or security guarantee.

## Before running anything against real services

Read [configuration](work-configuration.md), [security policy](../SECURITY.md),
[dependency boundaries](dependency-boundaries.md) and [lab limits](lab-validation.md).
Host entrypoints and the form require deliberate operator/server opt-in; sample
units leave it at 0. Nextcloud app installation/migrations remain separate
privileged service actions, not source checks. Dry runs may query real services.

Choose service targets, fresh independent credentials/HMAC material, permissions,
containers and paths; review quotas and authentication/MFA/TLS; decide what
names/emails/IPs and logs to retain. Review indefinite rejection history, seven-day
delivery expiry, 180-day plaintext master retention, shared-contact/export scope,
E2EE exclusions and sending a password with its link. None is approved for a real
installation by this source-release decision. Verify readable recovery separately.

No deployment configuration, environment, real data, dependency implementation,
binary, image, production credentials, private Git history or older reference
snapshot is bundled. The public source remains mixed licensed; it is not an
exclusive BSD grant over the app or external runtime dependencies.
