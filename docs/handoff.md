# Continuing this public-source candidate

Read README.md, LICENSING.md, PUBLIC_RELEASE_REVIEW.md and RELEASE_CHECKLIST.md.
BSD covers the maintainer's scoped first-party host/public/tools/docs contributions;
the complete app keeps AGPL-3.0-or-later. Preserve all existing/third-party notices
and keep the license map complete. Follow the recorded ownership/source-scope
decisions and revisit them if outside material or restrictions are identified.

The working repository uses `feature/experimental-source-release` with a staged,
uncommitted initial import, normal core defaults, explicitly selected personal
Git identity and no remote.
No original Git history, reflogs, hooks/signing overrides or credentials were
imported. The new personal identity was selected by the maintainer; extracted
source copies must select their own identity before committing. Source-only
packaging excludes every Git directory and surrounding private audit/reference.

Initial-import hygiene passed before the personal identity was selected. For a
new extracted copy, use `tools/verify-handoff.py --initial-import` before the first
commit or identity/real configuration, then default development mode thereafter.
The initial-import mode intentionally refuses a selected author. Default mode
permits normal authors/remotes/domains while checking index/tracked source and available
local Git objects. `check-public-release.py` adds public source/license coverage;
`--release` enforces unresolved human gates. None publishes or contacts services.

Before any runtime use choose work service adapters, domains/senders, paths,
containers, flow/admin/protected users, quotas, MFA/TLS, approval/audit policy,
retention and recipient/privacy controls. See docs/work-configuration.md.
The operator/server must explicitly enable ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1
only after that review; units ship at 0. Dry runs can still query private services.
The flag is not authorization or a guarantee that source assumptions are correct.

Compatible covin IDs, HMAC headers, tables, flows, units and paths remain. Keep
renaming coordinated across schema, app, public ingress, workers and tests.
The app copyright and chosen personal copyright name remain intentionally public.
Use CONTRIBUTING.md and the change template for source work, run offline checks,
review staged changes and keep deployment/publication separate.

Labs require explicit isolated selection, reviewed cached image IDs and, for
populated upgrade, an external hash-pinned 0.4.0 source directory. They never use
work main as the baseline. No real lab or service operation ran in preparation.
To roll back, stop using this separate candidate; no production/data effects need
reversal. Original input/reference copies remain unchanged outside public source.

The current release target is experimental source only. Read
[scope and untested integrations](experimental-release.md) and the
[personal-upstream/work-fork plan](github-handoff.md). Exact publication identity,
destination and manifest remain in a separate local approval dossier; no public
repository/fork, account setting, commit or push is authorized by this guide.
