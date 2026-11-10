#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
# Temporary, isolated source lint/mock tests in the existing PHP container.
# No Nextcloud bootstrap, migration, installed-source update or service mutation.
set -Eeuo pipefail

if [[ ${ACCOUNT_PLATFORM_RUNTIME_REVIEWED:-0} != 1 ]]; then
  echo 'STOP: this wrapper uses an existing container; review targets and explicitly set ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1.' >&2
  exit 1
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."

FILES=(
  apps/covin_account_admin/lib/Db/AccountRequest.php
  apps/covin_account_admin/lib/Db/AccountRequestMapper.php
  apps/covin_account_admin/lib/Service/ClosureRegistry.php
  apps/covin_account_admin/lib/Command/ClosureGuardCommand.php
  apps/covin_account_admin/lib/Migration/Version050000Date20261012000000.php
  apps/covin_account_admin/lib/Controller/ApiController.php
  apps/covin_account_admin/lib/Controller/PublicRequestController.php
  apps/covin_account_admin/lib/Repair/InitializeClosureGate.php
  host/account/test_closure_guards.php
  host/account/lab-install.php
  host/account/lab-upgrade.php
  host/account/lab-concurrency.php
  host/account/lab-concurrency-checks.php
  host/account/test_concurrency_checks.php
  host/account/lab-verify.php
)
for file in "${FILES[@]}"; do
  if [[ ! -f $file || -L $file ]]; then
    echo 'STOP: missing or symlinked candidate source.' >&2
    exit 1
  fi
done

# Authenticate sudo before starting the pipe; its input is the source archive.
sudo -v
tar --no-recursion -cf - "${FILES[@]}" |
  sudo docker exec -i -u www-data nextcloud-app sh -c '
    set -eu
    guard_test_dir=$(mktemp -d /tmp/covin-closure-guard-tests.XXXXXX)
    trap '\''rm -rf -- "$guard_test_dir"'\'' EXIT
    tar -xf - -C "$guard_test_dir"
    find "$guard_test_dir" -type f -name "*.php" |
      while IFS= read -r guard_test_file; do
        php -l "$guard_test_file"
      done
    COVIN_GUARD_SOURCE_ROOT="$guard_test_dir" \
      php "$guard_test_dir/host/account/test_closure_guards.php"
    php "$guard_test_dir/host/account/test_concurrency_checks.php"
  '
