# 2026-11-10 — Approved experimental source publication

Status: approved and source-checked; remote operations recorded separately

## Request and purpose

The maintainer approved the exact experimental source plan, personal repository,
public work fork, selected Git identity and private reporting before source push.
Record that decision, clear the final source gate and publish only reviewed
source. No production service or application deployment is authorized.

## Scope and source

Work remains on a feature branch. Initial import `141c3f7ac3940c5db893cc5b5e4c1f82a5568a36` exactly
matches reviewed tree `69d77c1070e67fa93430a06dcb7853e293bab0ef` and has no parents. A separate
documentation commit records approval/reporting evidence; no runtime, schema,
app metadata or existing license assignment changes. Preserve BSD and AGPL.

## Implementation and decisions

Resolve only PUBLICATION-APPROVAL using the maintainer's explicit approval and
actual reporting check. Keep all six named gates and their earlier evidence.
Update current guides from preparation-only status to approved source scope.
Preserve dated earlier validation checkpoints as historical evidence. Add these
two BSD documentation records; do not add account data or authentication material.

## Validation

Check source/index/history hygiene, license notice pins and all file assignments,
source syntax, documentation links and the staged diff. Real integration remains
untested. Private reporting was independently verified at 2026-11-10T02:00:45+00:00 before
any source branch existed. Before push, recheck the authenticated owner, remote
setting and exact commits. After publication, verify remote refs, public visibility,
fork relationship, author/committer and unchanged license bytes. Save actual
results outside Git; do not infer success from creating an empty repository.

## Deployment

No application/service, account, schema, timer, export or retention action occurs.
This authorization covers source publication only. Component versions stay app
0.5.0 candidate, approver 0.3.0 candidate, worker 0.2.0 and public handler 0.3.0.
The protected reviewed source archive and manifest remain outside Git. Actual
GitHub publication/fork commits, UTC dates and verification are recorded separately.

## Rollback and follow-up

Local source can be recovered from the preserved reviewed archive and initial
commit. Public copies/forks cannot be recalled by a local Git rollback. Do not
delete repositories, rewrite public history or force-push as an automatic rollback.
Future code changes need normal source/tests/notice review. Deployment, combined
runtime distribution and private work configuration remain separate decisions.
