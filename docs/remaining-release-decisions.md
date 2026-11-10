# Experimental source release decisions — 2026-11-10 UTC

The maintainer chose an experimental source release on a personal GitHub account,
followed by a work-account fork. That authorizes preparation, not repository
creation, a commit, push, publication, private-reporting activation or a fork. The personal
Git author/committer identity was approved separately and is selected locally.
Current exact gate states are in LICENSE-MAP.json.

| Gate | Plain-language status | What remains |
| --- | --- | --- |
| OWNERSHIP-REVIEW | Resolved by maintainer statement: no outside material or known ownership restrictions; earlier generated-code permission retained | Preserve notices; revisit if new outside material or an agreement is identified. This is not independent provenance proof |
| APP-INTEGRATION-RIGHTS | Resolved: maintainer accepts mixed BSD/AGPL source only, no bundled dependencies and deferred combined-distribution review | Review actual versions/combined-work obligations before later deployment or bundling; no license was changed |
| SECURITY-POLICY | Resolved for experimental source scope: service execution remains disabled by default; GitHub private reporting selected | After final approval, enable and verify reporting before source push. Real-installation MFA/TLS, privacy, retention and delivery decisions remain prerequisites |
| PHP-VALIDATION | Complete: 30 lint files, 55 PHP mock cases and 17 real local PHP/HTTP fixtures passed | Full framework/FPM/TLS and service compatibility remain untested |
| SERVICE-VALIDATION | Resolved as the explicit experimental source-release choice, not as an integration pass | Real services, migrations, populated upgrades, database races and readable encrypted recovery remain untested; require a separately approved isolated test plan |
| PUBLICATION-APPROVAL | Pending exact contents and personal/work destination review; personal author/committer identity selected | Confirm work owner/public-fork permission and approve the local dossier, exact repository name/contents and reporting setup before any public action; authenticated-account/name checks remain |

## Choices intentionally deferred until installation

No real-service policy was approved by selecting experimental source scope.
Choose MFA/TLS enforcement, independent credentials, log/IP minimization and audit
access/retention before service use. Review indefinite rejection history, seven-day
delivery expiry, 180-day plaintext master retention, shared-contact/export scope,
E2EE exclusions and whether export passwords may travel with their links. Existing
records, deadlines and service defaults were not changed or run.

BSD for scoped first-party source, public copyright Sam Covin and preservation of
the app's existing AGPL notice are settled. No license change is proposed. See
[scope/evidence](experimental-release.md), [dependency boundaries](dependency-boundaries.md)
and [fork handoff](github-handoff.md). The private reporting feature is planned,
not active merely because this document describes it.
