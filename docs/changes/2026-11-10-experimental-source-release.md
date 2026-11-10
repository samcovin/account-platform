# 2026-11-10 — Experimental source-release preparation

Status: implemented and locally checked; not committed/published/deployed

## Request and purpose

Prepare the sanitized candidate for a personal public experimental source
repository followed by a work fork. Explain remaining decisions, show exact
contents/identity/destination before publication, preserve BSD/AGPL notices and
make untested integrations clear. No production connection, push or publication.

## Scope and source

Existing public candidate on feature/experimental-source-release. Fresh initial
import remains staged and uncommitted. The previously validated source artifact
and original repository/archive/reference copies remain preserved separately.
No app, host, form, unit, schema, license text or existing license assignment was
changed. Documentation and source-only hygiene allowance for GitHub docs changed.

## Implementation and decisions

Add prominent experimental scope, an evidence/untested integration matrix, and a
personal-upstream/work-fork guide. Record the maintainer's ownership statement,
source-only release choice and selected future GitHub private reporting route.
Keep deployment privacy/retention/authentication choices explicit prerequisites.
Do not invent a support matrix or claim passing real integrations. Keep actual
account/identity/manifest approval details outside the public source tree.

Select the explicitly approved personal Git author/committer locally after the
one-time initial-import check; no original author settings are imported.
Update the six existing gate records only for documented maintainer decisions
and completed evidence; preserve unresolved decisions and publication approval.
The final reviewed exact gate states are in LICENSE-MAP.json. Generate a fresh
source-only archive and a separate exact file/mode/hash manifest for review.

## Validation

Run source checks, license pins/coverage, both initial-import/development Git
hygiene modes, staged diff review, documentation links and archive round-trip
byte/mode checks. Rerun tools tests for the changed documentation-host allowance
and gate records. No runtime source changed; earlier 166 Python cases, 55 PHP
mock cases, 30 PHP lint files and four offline unit checks remain classified
prior evidence, not newly claimed integration runs. See the newest release
validation JSON for actual commands/results and the earlier detailed record.

## Deployment

Not pushed, published, forked or deployed. No service, database, account, real
recipient, retained data, timer or production setting changed. No production
checkpoint is required. The maintainer's explicitly approved personal Git identity is selected locally;
no remote or commit is created.
Local account checks used read-only public GitHub metadata without credentials.

## Rollback and follow-up

Restore only this task's source/docs changes from the separately preserved
validated source archive, keeping unrelated work and all licenses. No service or
data rollback applies. Resolve the remaining approval-dossier questions before
creating any public repository, initial commit, fork or reporting setting. Future
deployment and combined-distribution review are separate authorized tasks.
