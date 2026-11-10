# Experimental source-release checklist — not cleared for publication

The maintainer selected experimental source release followed by a work fork,
confirmed no outside material or known ownership restriction and selected GitHub
private vulnerability reporting after final approval. Existing BSD/AGPL notices
and attribution remain unchanged. LICENSE-MAP.json retains all six gates.

| Gate | Status / remaining action |
| --- | --- |
| OWNERSHIP-REVIEW | Resolved from the explicit maintainer statement; preserve existing notices |
| APP-INTEGRATION-RIGHTS | Resolved: maintainer accepts source-only mixed BSD/AGPL scope without bundled dependencies; future combined-distribution review remains required |
| SECURITY-POLICY | Resolved for disabled experimental examples; enable/verify GitHub private reporting only after final approval and before first source push |
| PHP-VALIDATION | Complete: PHP 8.3.36 lint, 55 PHP mocks and 17 real local PHP/HTTP cases passed |
| SERVICE-VALIDATION | Resolved as experimental source scope; actual service/upgrade/concurrency/restore integration is untested |
| PUBLICATION-APPROVAL | Pending exact owner/name/contents and public work-fork approval; personal identity selected; account authentication and permissions unverified |

The default checker can pass while publication remains blocked. Run
`python3 tools/check-public-release.py --release`; unresolved gates intentionally
return exit 2. Do not erase gate records, treat disabled runtime as a sandbox or
replace missing runtime evidence with a checksum or successful mock test.

The separate local approval dossier contains exact proposed names, identity and
file hashes. No old reference, private preparation audit, imported history or
surrounding handoff directory should be uploaded. Use only the reviewed candidate.
The public fork remains public and keeps the personal source commit's authorship.
The approved personal Git identity is selected locally. No GitHub repository, fork,
Git remote/commit, account setting, push or deployment was created in preparation. Read [decisions](docs/remaining-release-decisions.md)
and [planned sequence](docs/github-handoff.md) before taking any public action.
