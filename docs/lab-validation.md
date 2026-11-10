# PHP checks and opt-in isolated labs

With a separately installed compatible local PHP runtime:

```sh
find apps host public -type f -name '*.php' -exec php -l '{}' \;
php host/account/test_closure_guards.php
php host/account/test_concurrency_checks.php
```

The suites are mocks, not database/Nextcloud integration. The existing-container
wrapper additionally requires deliberate runtime review opt-in and sudo/container
access. Neither real wrapper nor lab creation was executed in preparation.

The optional lab keeps its explicit ISOLATED argument and requires reviewed
cached SHA-256 image IDs through COVIN_LAB_APP_IMAGE and COVIN_LAB_DB_IMAGE.
No old host image ID is embedded and no image is pulled. The helper still expects
Nextcloud 32.0.14 source and a compatible MariaDB image; review versions separately.

Populated upgrade additionally requires COVIN_LAB_BASELINE_DIR pointing to an
external source-only app 0.4.0 reference. The manifest in
host/account/upgrade-baseline-0.4.0.json pins its app file set, bytes, modes and
version. It is independent of this repository's main branch. Read-only check:

```sh
python3 tools/check-lab-baseline.py /path/to/reviewed-0.4.0-reference
```

The older source is intentionally excluded from this public repository. Keep a
verified copy separately or review a replacement baseline/manifest as a source
change; do not substitute unrelated code merely to pass validation.

After committing reviewed candidate/lab source with an intended identity, a
separately authorized upgrade-lab run can use this example, replacing all example
paths/IDs with reviewed cached sources first:

```sh
sudo env COVIN_LAB_APP_IMAGE=sha256:REVIEWED-APP-ID \
  COVIN_LAB_DB_IMAGE=sha256:REVIEWED-DB-ID \
  COVIN_LAB_BASELINE_DIR=/path/to/reviewed-0.4.0-reference \
  bash host/account/prepare-closure-lab.sh --create-upgrade-lab ISOLATED
```

These literal image placeholders deliberately fail validation. Real lab execution
creates/removes labeled resources, installs/migrates disposable services and writes
protected staging data/diagnostics. It is not a source check or Git side effect.

## Completed local PHP checks

The current validation used a temporary signature-verified PHP 8.3.36 CLI with
INI loading disabled, without installing system packages. Run the form fixtures
with `ACCOUNT_PLATFORM_TEST_PHP=/path/to/trusted/php` and the README unittest
command; they bind only new owned loopback ports and replace only the throwaway
handler's ingress/SMTP targets. No production services or real recipients are
used. Full Nginx/FPM/TLS/Nextcloud/database integration remains separate.
