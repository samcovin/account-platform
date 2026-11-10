# Experimental source-release checklist — approved source scope

The maintainer explicitly approved public experimental source publication and
the public work fork. GitHub private vulnerability reporting was enabled and
verified before source push at 2026-11-10T02:00:45+00:00. See
[approval evidence](docs/publication-approval.md). All six named gate records
remain in LICENSE-MAP.json; none was deleted or bypassed.

| Gate | Recorded resolution / limits |
| --- | --- |
| OWNERSHIP-REVIEW | Maintainer confirms no outside material or known ownership restriction; preserve notices |
| APP-INTEGRATION-RIGHTS | Mixed BSD/AGPL source only, no bundled dependencies; later combined-distribution review remains required |
| SECURITY-POLICY | Disabled experimental examples; selected private reporting independently enabled/verified; installation policy still needs review |
| PHP-VALIDATION | PHP 8.3.36 lint, 55 PHP mock cases and 17 real local PHP/HTTP cases passed |
| SERVICE-VALIDATION | Explicit experimental source scope; actual service/upgrade/concurrency/restore integration remains untested |
| PUBLICATION-APPROVAL | Explicit maintainer approval of exact destinations, reviewed source, noreply identity, reporting and public fork; actual remote execution recorded separately |

`python3 tools/check-public-release.py --release` must now pass for the approved
source. It does not authorize real-service operations, prove legal rights or
certify runtime security. Changes to scope, dependencies or source require review.

Push only the reviewed source history to the approved main branch. Do not upload
surrounding handoffs, old references, private preparation, original Git history,
credentials, real records or runtime packages. Verify remote visibility, refs,
identity, fork relationship and reporting; record actual commit/UTC results after
publication. No app installation, migration, provisioning, email, retention cleanup,
Pages, image/package or deployment accompanies this source publication.
