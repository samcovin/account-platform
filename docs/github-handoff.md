# Personal upstream and work fork

This plan concerns an experimental source repository. No repository, remote,
commit, fork, private-reporting setting or publication has been created by this
preparation. Exact account names, identity, file hashes and proposed artifact are
in the separate local approval dossier, outside this public source tree.

## Review before publication

The proposed repository name is `account-platform`, with default branch `main`.
The first commit should contain only this sanitized initial import, using the
explicitly reviewed personal author and committer. Use the actual commit date;
no historical import date or recovered personal repository history is recreated.
Do not have GitHub generate another license, README or initial commit. Preserve
the nested app AGPL notice and every file in LICENSE-MAP.json.

Review the exact file manifest, source-tree hash and archive hash; resolve or
explicitly reassess the named release gates with recorded evidence. Publication
approval is separate from permission to prepare source. Authentication, final
repository-name availability and account permissions still require verification.
Never paste a token into source, issue text, a command transcript or an archive.

After explicit final approval, the intended order is:

1. Select the reviewed repository-local personal author/committer, make the fresh
   initial source commit and select `main` for publication. Do not push any older
   refs, branches, tags or history.
2. Authenticate to the personal account and recheck the exact destination. Create
   only the approved repository; this step itself can expose its public name.
3. Enable GitHub private vulnerability reporting and verify it before the first
   source push. If it cannot be verified, stop and review the reporting decision.
   Do not claim the route is active solely because SECURITY.md describes it.
4. Push only the reviewed source commit to `main`, then record the actual commit,
   UTC publication date, visibility, source contents and private-reporting result.
   This is source publication, not service deployment. No package/image, GitHub
   Release tag, Pages site, workflow or deployment is part of this plan.
5. Create the approved fork under the work account only after verifying its owner,
   permissions, policy and intended public visibility. Keep license notices and
   original source attribution intact. Verify that it is a fork of the intended
   personal upstream, not an independently initialized repository.

No step above is authorized to run automatically by this document.

## What the work fork means

GitHub public-repository forks are also public. A work fork remains connected to
the personal upstream, and the original commit's authorship remains in its history.
It does not become private or acquire a different license by moving to work.
Organization and managed-user policies can restrict where a fork may be created.
See [GitHub fork rules](https://docs.github.com/en/pull-requests/reference/forks).

Clone the work fork into a separate work directory. Its `origin` should be the
work fork and its `upstream` the personal repository; review both URLs before
writing. Set a separately selected repository-local work author/email for future
work commits. That choice does not rewrite the personal source commit. Use
feature branches and preserve the existing change/test documentation practices.

Keep company secrets, service settings, employee/account data and private work
changes out of this public fork. If private work is needed, establish a separately
authorized private repository or private configuration store; a public fork cannot
be made private independently. Do not automatically send work changes upstream.
An employer's adoption, contribution and publication rules remain separate checks.

## Licenses and compatibility

Keep the root BSD scope, complete AGPL app scope and license-document copying
notice. A first-party grant does not relicense external frameworks or establish
all obligations for a future combined distribution. Keep covin namespaces,
protocol headers, table names, service labels and path identifiers until a
coordinated change is tested. No old reference code is mixed into this starting
point. The optional 0.4.0 upgrade baseline remains an external pinned reference.
