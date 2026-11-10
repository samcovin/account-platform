# Working on Account Platform

Read README.md and docs/current-state.md before proposing a deployment.
Use source files and recorded evidence; do not infer deployment from an archive
being present. Historical recovery commits must use their actual import date.

For every functional change:
1. State the user problem and intended behavior.
2. Work on a feature branch, preserving unrelated edits.
3. Update relevant documentation and create a record under docs/changes using
   docs/change-template.md. Include tests, limitations and rollback requirements.
4. Run source checks and relevant behavioral tests. Distinguish syntax checks,
   mocked tests, real integration tests and user-reported results.
5. Review the staged diff for secrets and personal data.
6. Record deployment separately with component versions, commit, UTC date,
   protected checkpoint location and actual verification results.

Never put production secrets, signing keys, private keys, database dumps, account
exports, applicant records or raw user logs in Git, including private branches.
Never expose a secret in a command transcript. Examples use clear placeholders.

Keep historical snapshots immutable. Preserve encryption and access boundaries.
Do not automatically run production provisioning, deletion, database restoration,
or schema migrations as part of source validation or Git operations.
Do not treat gzip/checksum success as proof that encrypted account data can be restored.

Follow the user's current authorization and priorities. Repository access does
not by itself authorize contacting applicants or creating real accounts.
