# Experimental source release decisions — 2026-11-10 UTC

The maintainer approved the exact public experimental source plan, personal
upstream, public work fork, selected identity and GitHub private reporting before
source push at 2026-11-10T01:57:28+00:00. All six source gates have recorded resolutions;
[approval evidence](publication-approval.md) supersedes earlier preparation-only
statements. Actual remote execution is recorded separately after verification.

| Gate | Resolution in plain language | Remaining operational limits |
| --- | --- | --- |
| OWNERSHIP-REVIEW | Maintainer confirms no outside material or known ownership restriction | Reopen if outside inputs or restrictions are identified; this is not an independent audit |
| APP-INTEGRATION-RIGHTS | Mixed BSD/AGPL source only, without bundled dependency implementations | Review actual versions and combined-work obligations before deployment or bundling |
| SECURITY-POLICY | Disabled experimental source examples; private reporting selected and verified on personal upstream | Verify fork reporting separately; choose installation authentication/privacy/retention/delivery policy |
| PHP-VALIDATION | Local PHP lint, mocks and owned loopback HTTP/SMTP fixtures pass | Full framework/FPM/TLS and service compatibility remain untested |
| SERVICE-VALIDATION | Maintainer accepts experimental source scope with untested integrations clearly labeled | Real services, migrations, upgrades, races and encrypted recovery require separate isolated validation |
| PUBLICATION-APPROVAL | Explicit yes to exact personal/work destinations, reviewed contents/identity, reporting and public fork | Authenticate/verify each owner and remote action; do not overwrite conflicting destinations or treat approval as completed publication |

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
