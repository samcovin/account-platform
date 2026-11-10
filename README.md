# Account Platform — experimental source

**Mixed licensing:** original first-party source outside `apps/covin_account_admin/`
is offered under BSD 3-Clause, copyright 2026 Sam Covin. The Nextcloud app remains
AGPL-3.0-or-later with its original notice. See [licensing](LICENSING.md),
[per-file map](LICENSE-MAP.json) and [existing notices](THIRD_PARTY_NOTICES.md).
**Experimental source for review and development.** Full Nextcloud, Mailcow,
Authentik, database, upgrade and encrypted-recovery integration is **untested**.
Keep service execution disabled until an independent configuration/integration
review. See the [release scope and evidence matrix](docs/experimental-release.md).

The project implements manual account review and audit in a Nextcloud app,
signed public requests, and separate Mailcow/Authentik host adapters. Additional
tools cover exports, delivery, retention, suspension/session revocation and
read-only closure inventory. App 0.5.0 and approver 0.3.0 remain coordinated
candidates; worker 0.2.0 and public handler 0.3.0 source are included.

Start with [release review](PUBLIC_RELEASE_REVIEW.md), [open checklist](RELEASE_CHECKLIST.md),
[configuration](docs/work-configuration.md), [development](CONTRIBUTING.md),
[security handling](SECURITY.md) and [validation](docs/validation.md).

## Safe source inspection

```sh
python3 tools/check-source.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify-handoff.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/check-public-release.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s host/account -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s host/export -p 'test_*.py' -v
```

The release checker without flags verifies source hygiene/license coverage and
reports pending gates. `--release` additionally fails while any gate is unresolved.
No checker publishes, installs, migrates or contacts a service.

## Runtime is off until deliberately reviewed

Host entrypoints and the public PHP form refuse normal service access unless
`ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1` is explicitly configured by the operator.
Sample systemd services set it to 0. The environment flag is an accidental-use
guard, not authorization or a substitute for checking target hosts, roles,
credentials, policy, TLS/MFA and data preservation. Dry runs can still query
services after opt-in. Nextcloud app installation is a separate service action.

The source retains example domains, compatible `covin` identifiers, host paths,
container/service names and inherited policy defaults. It is not a complete
Compose/DNS/TLS/identity environment. Read [configuration](docs/work-configuration.md)
before service use. Do not enable the flag merely to make a failing command run.
Lab creation is separately explicit and requires reviewed cached images and an
external pinned 0.4.0 baseline for populated upgrades; see [labs](docs/lab-validation.md).

The development directory has fresh, uncommitted Git on
`feature/experimental-source-release`, without imported history or remotes.
The personal release identity was explicitly selected locally; no commit exists.
If using your own extracted copy, select your own identity before committing.
The source-only review archive excludes all Git metadata and private preparation/reference files.

After extracting the source-only archive, enter its `account-platform` directory
and run `git init --initial-branch=feature/source-review`, then `git add --all`,
before using the Git-dependent verifier. This creates local metadata only; choose
your commit identity separately. The public-source checker itself needs no Git.

Local PHP validation is now complete. With PHP CLI/mbstring available, the tools
suite starts only disposable loopback PHP/HTTP/SMTP fixtures; it does not contact
existing services. To run the form cases explicitly:

```sh
ACCOUNT_PLATFORM_TEST_PHP=/path/to/trusted/php \
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p test_public_form.py -v
```

PHP runs with `-n`; mbstring must be available in that isolated configuration.
If PHP/mbstring is unavailable the form cases are skipped, which is not evidence
of passing PHP validation. See [remaining decisions](docs/remaining-release-decisions.md)
and [dependency boundaries](docs/dependency-boundaries.md).
The [personal upstream and work fork guide](docs/github-handoff.md) explains the
proposed sequence. The [release checklist](RELEASE_CHECKLIST.md) records actual
open gates; preparation does not authorize creating or publishing repositories.
