#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
# Opt-in, fresh isolated Nextcloud/MariaDB migration smoke. Never production.
set -Eeuo pipefail
umask 077

if [[ $EUID -ne 0 || ( ${1:-} != --create-lab && ${1:-} != --create-upgrade-lab && ${1:-} != --create-concurrency-lab ) || ${2:-} != ISOLATED || $# != 2 ]]; then
  echo 'Usage: sudo bash host/account/prepare-closure-lab.sh {--create-lab|--create-upgrade-lab|--create-concurrency-lab} ISOLATED' >&2
  exit 1
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
SOURCE_ROOT=$PWD
LAB_MODE=fresh
[[ $1 != --create-upgrade-lab ]] || LAB_MODE=upgrade
[[ $1 != --create-concurrency-lab ]] || LAB_MODE=concurrency
APP_IMAGE=${COVIN_LAB_APP_IMAGE:-}
DB_IMAGE=${COVIN_LAB_DB_IMAGE:-}
if [[ ! $APP_IMAGE =~ ^sha256:[a-f0-9]{64}$ || ! $DB_IMAGE =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo 'STOP: explicitly configure reviewed cached COVIN_LAB_APP_IMAGE and COVIN_LAB_DB_IMAGE IDs.' >&2
  exit 1
fi
for command in docker git openssl python3 tar timeout chown; do
  command -v "$command" >/dev/null || { echo 'STOP: required lab tool absent.' >&2; exit 1; }
done
CANDIDATE_COMMIT=$(git -c safe.directory="$SOURCE_ROOT" rev-parse --verify 'HEAD^{commit}')
[[ $CANDIDATE_COMMIT =~ ^[a-f0-9]{40}$ ]] || { echo 'STOP: invalid candidate commit.' >&2; exit 1; }
git -c safe.directory="$SOURCE_ROOT" diff --quiet "$CANDIDATE_COMMIT" -- \
  apps/covin_account_admin host/worker/covin-approve-account \
  host/account/prepare-closure-lab.sh host/account/upgrade-baseline-0.4.0.json \
  tools/check-lab-baseline.py || {
    echo 'STOP: account source differs from the selected HEAD commit.' >&2; exit 1;
  }
BASELINE_COMMIT=''
BASELINE_DIR=''
BASELINE_MANIFEST="$SOURCE_ROOT/host/account/upgrade-baseline-0.4.0.json"
if [[ $LAB_MODE == upgrade ]]; then
  BASELINE_DIR=${COVIN_LAB_BASELINE_DIR:-}
  [[ -n $BASELINE_DIR ]] || { echo 'STOP: set COVIN_LAB_BASELINE_DIR to the external pinned reference-0.4.0 source.' >&2; exit 1; }
  # Validate before any Docker command. The work repository's main is unrelated.
  python3 "$SOURCE_ROOT/tools/check-lab-baseline.py" "$BASELINE_DIR" --manifest "$BASELINE_MANIFEST"
  BASELINE_COMMIT=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["source_snapshot"])' "$BASELINE_MANIFEST")
  [[ $BASELINE_COMMIT =~ ^[a-f0-9]{40}$ ]] || { echo 'STOP: invalid baseline snapshot provenance.' >&2; exit 1; }
fi
for script in host/account/lab-install.php host/account/lab-verify.php host/account/lab-upgrade.php \
  host/account/lab-concurrency.php host/account/lab-concurrency-checks.php; do
  [[ -f $script && ! -L $script ]] || { echo 'STOP: missing or symlinked lab script.' >&2; exit 1; }
done

# No pulls or production environment inspection. Reject unexpected image volumes.
for image in "$APP_IMAGE" "$DB_IMAGE"; do
  docker image inspect "$image" |
    python3 -c '
import json, sys
image = json.load(sys.stdin)[0]
expected = "/var/www/html" if image["Id"] == sys.argv[1] else "/var/lib/mysql"
if set((image["Config"].get("Volumes") or {}).keys()) != {expected}:
    raise SystemExit("STOP: unexpected cached-image volumes")
' "$APP_IMAGE"
done

STAGE=$(mktemp -d /var/tmp/covin-closure-lab.XXXXXXXX)
chmod 700 "$STAGE"
printf '%s\n' "$CANDIDATE_COMMIT" >"$STAGE/source-commit.txt"
echo "Isolated candidate source: $CANDIDATE_COMMIT"
RUN_ID=$(openssl rand -hex 12)
NETWORK="covin-guard-net-$RUN_ID"
APP="covin-guard-app-$RUN_ID"
DB="covin-guard-db-$RUN_ID"
LABEL='com.covin.closure-lab'
NETWORK_CREATED=0
APP_CREATED=0
DB_CREATED=0

cleanup_lab() {
  local result=$?
  trap - EXIT
  for resource in "$APP" "$DB"; do
    if [[ $resource == "$APP" && $APP_CREATED == 0 ]] ||
       [[ $resource == "$DB" && $DB_CREATED == 0 ]]; then continue; fi
    if docker inspect "$resource" >/dev/null 2>&1; then
      local found
      if ! found=$(docker inspect "$resource" --format '{{index .Config.Labels "com.covin.closure-lab"}}'); then
        echo 'STOP: cannot verify a lab container label; no removal attempted.' >&2
        result=1
        continue
      fi
      if [[ $found != "$RUN_ID" ]]; then
        echo 'STOP: test-resource label mismatch; no removal attempted.' >&2
        result=1
        continue
      fi
      docker logs "$resource" >"$STAGE/$resource.log" 2>&1 || true
      # --rm containers remove only their own test container when stopped.
      if ! docker stop --timeout 15 "$resource" >"$STAGE/$resource.stop" 2>&1; then
        echo 'STOP: a lab container could not be stopped.' >&2
        result=1
      fi
    fi
  done
  if (( NETWORK_CREATED )) && docker network inspect "$NETWORK" >/dev/null 2>&1; then
    local found
    if ! found=$(docker network inspect "$NETWORK" --format '{{index .Labels "com.covin.closure-lab"}}'); then
      found=''
    fi
    if [[ $found == "$RUN_ID" ]]; then
      docker network rm "$NETWORK" >"$STAGE/network.remove" 2>&1 || result=1
    else
      echo 'STOP: test-network label mismatch; no removal attempted.' >&2
      result=1
    fi
  fi
  if (( result != 0 )); then echo 'STOP: isolated lab failed or cleanup needs review.' >&2; fi
  echo "Protected lab files retained: $STAGE"
  echo 'Do not paste environment files, instance config or raw logs.'
  exit "$result"
}
trap cleanup_lab EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

for resource in "$APP" "$DB"; do
  if docker inspect "$resource" >/dev/null 2>&1; then
    echo 'STOP: generated test-container name already exists.' >&2; exit 1;
  fi
done
if docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo 'STOP: generated test-network name already exists.' >&2; exit 1;
fi

install -d -m 700 "$STAGE/db" "$STAGE/html" "$STAGE/source"
# Pinned Nextcloud image uses www-data uid/gid 33. Only the fresh mount root.
chown 33:33 "$STAGE/html"
install -d -m 755 "$STAGE/tools"
install -m 644 host/account/lab-install.php "$STAGE/tools/install.php"
install -m 644 host/account/lab-verify.php "$STAGE/tools/verify.php"
install -m 644 host/account/lab-upgrade.php "$STAGE/tools/upgrade.php"
install -m 644 host/account/lab-concurrency.php "$STAGE/tools/concurrency.php"
install -m 644 host/account/lab-concurrency-checks.php "$STAGE/tools/concurrency-checks.php"
git -c safe.directory="$SOURCE_ROOT" archive "$CANDIDATE_COMMIT" apps/covin_account_admin |
  tar -xf - -C "$STAGE/source"
INITIAL_SOURCE="$STAGE/source"
if [[ $LAB_MODE == upgrade ]]; then
  install -d -m 700 "$STAGE/baseline"
  python3 "$SOURCE_ROOT/tools/check-lab-baseline.py" "$BASELINE_DIR" \
    --manifest "$BASELINE_MANIFEST" --copy-to "$STAGE/baseline"
  INITIAL_SOURCE="$STAGE/baseline"
  printf '%s\n' "$BASELINE_COMMIT" >"$STAGE/baseline-commit.txt"
  echo "Isolated upgrade baseline: pinned app 0.4.0 snapshot $BASELINE_COMMIT (external source)"
  python3 -c '
import sys, xml.etree.ElementTree as ET
for path, version in [(sys.argv[1], "0.4.0"), (sys.argv[2], "0.5.0")]:
    info = ET.parse(path).getroot()
    if info.findtext("id") != "covin_account_admin" or info.findtext("version") != version:
        raise SystemExit("STOP: unexpected upgrade source identity/version")
' "$STAGE/baseline/apps/covin_account_admin/appinfo/info.xml" "$STAGE/source/apps/covin_account_admin/appinfo/info.xml"
fi

DB_PASSWORD=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -hex 32)
ROOT_PASSWORD=$(openssl rand -hex 32)
{
  printf 'MARIADB_ROOT_PASSWORD=%s\n' "$ROOT_PASSWORD"
  printf 'MARIADB_DATABASE=covin_guard_lab\nMARIADB_USER=covin_guard_lab\n'
  printf 'MARIADB_PASSWORD=%s\n' "$DB_PASSWORD"
} >"$STAGE/db.env"
{
  printf 'COVIN_GUARD_LAB_TEST=%s\n' "$LAB_MODE"
  printf 'COVIN_GUARD_LAB_RUN=%s\n' "$RUN_ID"
  printf 'COVIN_GUARD_LAB_DB_HOST=%s\n' "$DB"
  printf 'COVIN_GUARD_LAB_DB_PASSWORD=%s\n' "$DB_PASSWORD"
  printf 'COVIN_GUARD_LAB_ADMIN_PASSWORD=%s\n' "$ADMIN_PASSWORD"
} >"$STAGE/app.env"
unset DB_PASSWORD ADMIN_PASSWORD ROOT_PASSWORD

NETWORK_CREATED=1
docker network create --internal --label "$LABEL=$RUN_ID" "$NETWORK" >"$STAGE/network.id"
DB_CREATED=1
docker run -d --rm --pull=never --name "$DB" \
  --label "$LABEL=$RUN_ID" --network "$NETWORK" --restart=no \
  --memory=768m --cpus=1 \
  --env-file "$STAGE/db.env" \
  --mount "type=bind,src=$STAGE/db,dst=/var/lib/mysql" \
  "$DB_IMAGE" --transaction-isolation=READ-COMMITTED --binlog-format=ROW >"$STAGE/db.id"
APP_CREATED=1
docker run -d --rm --pull=never --name "$APP" \
  --label "$LABEL=$RUN_ID" --network "$NETWORK" --restart=no \
  --memory=1536m --cpus=1 \
  --env-file "$STAGE/app.env" \
  --mount "type=bind,src=$STAGE/html,dst=/var/www/html" \
  --mount "type=bind,src=$STAGE/tools,dst=/lab,readonly" \
  --user 33:33 --entrypoint /bin/sh "$APP_IMAGE" -c '
    set -eu
    test "$(id -u)" = 33
    test "$(id -g)" = 33
    test ! -e /usr/src/nextcloud/config/config.php
    test ! -e /var/www/html/config/config.php
    echo SOURCE_COPY_STARTED
    # New files belong to www-data immediately; no recursive ownership pass.
    # Exclude all image configuration and data directories.
    for source in /usr/src/nextcloud/* /usr/src/nextcloud/.[!.]* /usr/src/nextcloud/..?*; do
      test -e "$source" || continue
      case "${source##*/}" in config|data) continue ;; esac
      cp -a --no-preserve=ownership "$source" /var/www/html/
    done
    echo SOURCE_COPY_COMPLETE
    mkdir /var/www/html/config /var/www/html/data
    cp /usr/src/nextcloud/config/config.sample.php /var/www/html/config/
    php -r '\''require "/var/www/html/version.php"; exit($OC_VersionString === "32.0.14" ? 0 : 1);'\''
    printf "%s\n" "$COVIN_GUARD_LAB_RUN" > /var/www/html/.covin-guard-lab
    touch /var/www/html/.covin-lab-source-ready
    echo SOURCE_PREPARATION_COMPLETE
    exec sleep infinity
  ' >"$STAGE/app.id"

# Verify zero published ports, one labeled internal network and exact fresh mounts.
docker inspect "$APP" "$DB" |
  python3 -c '
import json, sys
stage, network, run = sys.argv[1:]
for container in json.load(sys.stdin):
    if container["HostConfig"].get("PortBindings") or container["HostConfig"].get("PublishAllPorts"):
        raise SystemExit("STOP: test container publishes ports")
    if container["HostConfig"].get("Privileged"):
        raise SystemExit("STOP: privileged test container")
    if set(container["NetworkSettings"]["Networks"]) != {network}:
        raise SystemExit("STOP: unexpected test network membership")
    if container["Config"]["Labels"].get("com.covin.closure-lab") != run:
        raise SystemExit("STOP: test resource label mismatch")
    name = container["Name"].lstrip("/")
    if name == "covin-guard-app-" + run:
        expected = {"/var/www/html": (stage + "/html", True), "/lab": (stage + "/tools", False)}
    elif name == "covin-guard-db-" + run:
        expected = {"/var/lib/mysql": (stage + "/db", True)}
    else:
        raise SystemExit("STOP: unexpected test container name")
    actual = {}
    for mount in container["Mounts"]:
        if mount["Type"] != "bind" or mount["Destination"] in actual:
            raise SystemExit("STOP: unexpected or duplicate test mount")
        actual[mount["Destination"]] = (mount["Source"], mount["RW"])
    if actual != expected:
        raise SystemExit("STOP: unexpected test mount mapping or permissions")
' "$STAGE" "$NETWORK" "$RUN_ID"
[[ $(docker network inspect "$NETWORK" --format '{{.Internal}}') == true ]]
[[ $(docker network inspect "$NETWORK" --format '{{index .Labels "com.covin.closure-lab"}}') == "$RUN_ID" ]]

echo 'Waiting for fresh isolated source and database...'
READY=0
# Allow up to roughly ten minutes for source copy, ownership and database startup.
for attempt in $(seq 1 300); do
  if docker exec "$APP" php -r '
    if (!is_file("/var/www/html/.covin-lab-source-ready")) exit(1);
    try {
      new PDO("mysql:host=" . getenv("COVIN_GUARD_LAB_DB_HOST") . ";dbname=covin_guard_lab",
        "covin_guard_lab", getenv("COVIN_GUARD_LAB_DB_PASSWORD"));
    } catch (Throwable $e) { exit(1); }
  ' >"$STAGE/readiness.log" 2>&1; then READY=1; break; fi
  if (( attempt % 10 == 0 )); then echo 'Still waiting for isolated source preparation and database readiness...'; fi
  sleep 2
done
(( READY )) || { echo 'STOP: isolated lab did not become ready.' >&2; exit 1; }

echo 'Installing only the empty isolated Nextcloud instance...'
INSTALL_STARTED=$SECONDS
INSTALL_STATUS=0
# A fresh installation may exceed five minutes on the resource-limited lab.
timeout --kill-after=15s 900 docker exec -u www-data "$APP" php /lab/install.php \
  >"$STAGE/install.log" 2>&1 || INSTALL_STATUS=$?
printf 'exit_status=%s\nelapsed_seconds=%s\n' \
  "$INSTALL_STATUS" "$((SECONDS - INSTALL_STARTED))" >"$STAGE/install-result.txt"
if (( INSTALL_STATUS != 0 )); then
  printf 'STOP: isolated installation exited with status %s after %s seconds.\n' \
    "$INSTALL_STATUS" "$((SECONDS - INSTALL_STARTED))" >&2
  exit "$INSTALL_STATUS"
fi
docker exec -u www-data "$APP" php occ config:system:set appstoreenabled \
  --type=boolean --value=false >"$STAGE/appstore.log" 2>&1
docker exec -u www-data "$APP" php occ config:system:set apps_paths --type=json \
  --value='[{"path":"/var/www/html/apps","url":"/apps","writable":false},{"path":"/var/www/html/custom_apps","url":"/custom_apps","writable":true}]' \
  >"$STAGE/app-paths.log" 2>&1

# No production app or data is copied; this is the exact committed candidate.
install -d "$STAGE/html/custom_apps"
cp -a "$INITIAL_SOURCE/apps/covin_account_admin" "$STAGE/html/custom_apps/"
docker exec -u 0:0 "$APP" chown -R www-data:www-data /var/www/html/custom_apps/covin_account_admin
echo 'Enabling the initial app in the isolated instance...'
timeout 180 docker exec -u www-data "$APP" php occ app:enable covin_account_admin >"$STAGE/enable.log" 2>&1
if [[ $LAB_MODE == upgrade ]]; then
  echo 'Seeding synthetic requests and audit history in isolated 0.4.0...'
  timeout 60 docker exec -u www-data "$APP" php /lab/upgrade.php seed >"$STAGE/seed.log" 2>&1
  mv "$STAGE/html/custom_apps/covin_account_admin" "$STAGE/old-app"
  cp -a "$STAGE/source/apps/covin_account_admin" "$STAGE/html/custom_apps/"
  docker exec -u 0:0 "$APP" chown -R www-data:www-data /var/www/html/custom_apps/covin_account_admin
  echo 'Upgrading only the isolated instance to the committed candidate...'
  timeout 300 docker exec -u www-data "$APP" php occ upgrade --no-interaction >"$STAGE/upgrade.log" 2>&1
  timeout 60 docker exec -u www-data "$APP" php /lab/upgrade.php verify >"$STAGE/result.json" 2>"$STAGE/verify.log"
else
  timeout 60 docker exec -u www-data "$APP" php /lab/verify.php >"$STAGE/result.json" 2>"$STAGE/verify.log"
fi

# Verify and print only the allowlisted smoke result, never private install logs.
python3 -c '
import json, sys
report = json.load(open(sys.argv[1]))
expected = {"status": "isolated-migration-smoke-passed", "app_version": "0.5.0",
    "registry_and_mapper_dependency_injection": "passed", "empty_request_and_audit_tables": True,
    "gate_row_count": 1, "transactional_table_count": 5, "empty_claim_query": "passed",
    "real_concurrency_tested": False, "production_deployment": False, "account_deletion": False}
if sys.argv[2] == "upgrade":
    expected = {"status": "isolated-populated-upgrade-passed", "from_version": "0.4.0",
        "app_version": "0.5.0", "preserved_request_rows": 7, "preserved_audit_rows": 7,
        "all_existing_row_fields_preserved": True, "gate_row_count": 1,
        "transactional_table_count": 5, "registry_and_mapper_dependency_injection": "passed",
        "real_concurrency_tested": False, "production_deployment": False, "account_deletion": False}
if report != expected or any(type(report[k]) is not type(v) for k, v in expected.items()):
    raise SystemExit("STOP: unexpected lab report")
print(json.dumps(report, indent=2))
' "$STAGE/result.json" "$LAB_MODE"
if [[ $LAB_MODE == concurrency ]]; then
  mv "$STAGE/result.json" "$STAGE/fresh-result.json"
  echo 'Running separate-process queue and closure races in the isolated instance...'
  timeout 600 docker exec -u www-data "$APP" php /lab/concurrency.php run \
    >"$STAGE/result.json" 2>"$STAGE/concurrency.log"
  python3 -c '
import json, sys
report = json.load(open(sys.argv[1]))
expected = {"status": "isolated-concurrency-passed",
    "scenarios": ["approval", "retry", "resend", "claim", "execution", "double-claim"],
    "contended_rounds": 12, "observed_gate_waiters": 24,
    "unrelated_request_and_audit_preserved": True, "separate_worker_connections": True,
    "production_deployment": False, "account_deletion": False}
if report != expected or any(type(report[k]) is not type(v) for k, v in expected.items()):
    raise SystemExit("STOP: unexpected concurrency report")
print(json.dumps(report, indent=2))
' "$STAGE/result.json"
  echo 'ISOLATED_CLOSURE_CONCURRENCY_PASSED'
elif [[ $LAB_MODE == upgrade ]]; then
  echo 'ISOLATED_CLOSURE_POPULATED_UPGRADE_PASSED'
else
  echo 'ISOLATED_CLOSURE_MIGRATION_SMOKE_PASSED'
fi
