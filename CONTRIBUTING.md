# Development and contributions

Use a feature branch and describe the problem and intended behavior. Update the
relevant guide and a record using `docs/change-template.md`. Run source checks
and appropriate offline tests. Review the staged diff for credentials/personal
data before committing, using a deliberately selected Git identity.

The working candidate uses `feature/experimental-source-release` with a staged,
uncommitted initial import; the explicitly approved personal identity is selected
locally and no remote exists. Initial-import hygiene passed before identity
selection. In a new extracted copy, run `tools/verify-handoff.py --initial-import`
once before the first work commit, local identity/remote or real configuration. For normal development use
the default verifier, which permits normal identities/remotes/domains and checks
tracked/index source and available local Git objects. It never contacts remotes.

Keep `LICENSE-MAP.json` complete when adding/removing files. Respect the app's
AGPL exception, the first-party BSD grant and all third-party notices. Do not
assume a top-level BSD file supersedes nested notices. Track contribution/source
provenance and any separate terms; no CLA or employer assignment is invented here.

The README commands use mocks and source checks. Do not run privileged host tools,
install the app, enable timers, create a real lab, send notifications, migrate a
database or alter accounts as part of a source check or Git operation. See
`docs/lab-validation.md` for opt-in lab requirements and `SECURITY.md` for reports.

Run `tools/check-public-release.py --release` before proposing publication.
Pending gates must be resolved or explicitly reassessed with evidence by the
maintainer; do not silently change their status to bypass review. Nothing in the
preparation workflow configures or pushes a public remote.

Gate records must contain all six distinct gate IDs and valid states; a resolved record needs a rationale and existing evidence files. Source-only checks now also scan staged/historical Git objects when Git is present. Never remove gates to imply clearance.

For this experimental source release, use the release-scope evidence matrix and
keep mock/local-fixture success distinct from real integration. The intended
personal upstream/work fork sequence is in docs/github-handoff.md. Work-account
contributions and private employer data require separate review; do not publish
raw configuration/logs or silently broaden the proposed source-only scope.
