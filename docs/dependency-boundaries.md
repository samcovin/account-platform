# Observed dependency and distribution boundaries

This is a source inventory, not a legal determination or a runtime compatibility
claim. No third-party implementation/vendor tree or dependency lock file is
bundled. The existing mixed license scope and all notices remain unchanged.

| Source area | External interfaces actually referenced | What was checked / what remains |
| --- | --- | --- |
| App Application, Db, Controller, Migration and Repair classes | Nextcloud OCP bootstrap/app framework, DB/query builder/schema, admin/user services and occ commands | PHP lint and fake OCP/DB mock suites passed; no installed Nextcloud/database or real migrations were run |
| host/account/nextcloud-closure-preflight.php | `/var/www/html/lib/base.php`, OC server, OCP user/file/DB APIs and DAV backends | Parsed successfully; actual bootstrap/service and installed app coverage remain external |
| host/export/nextcloud-export.php | Nextcloud file/user/DAV APIs and Sabre VObject Reader | Parsed successfully; PHP/Dovecot export readability and E2EE restoration remain unproven |
| host/worker and host/account adapters | Docker/Compose, Nextcloud occ protocol, Mailcow API/config, Authentik/Django ORM/flows, Dovecot/SOGo session/schema behavior | Offline mocks and refusal tests passed; target versions, mappings and service semantics need an isolated integration plan |
| Public form | PHP mbstring/filter/hash/HTTP streams plus SMTP; HMAC ingress protocol | Real PHP 8.3.36 with HTTP/SMTP fixtures on owned loopback ports passed; fixture copy changes only the two external targets; real TLS/FPM/Nginx/Mailcow/Nextcloud were not exercised |
| Export delivery/cleanup | Nextcloud WebDAV/OCS APIs, curl, 7-Zip, Docker sendmail, filesystem receipts | Offline mocks passed; real delivery, password transport, retention and restore policy are not approved by those tests |
| Units/timers | Linux/systemd, root paths, Docker and runtime opt-in | Four files verified with systemd-analyze against a disposable root and dependency/executable fixtures; no manager, service or timer was started |
| Local checks | Python stdlib, Bash/jq/openssl/flock, Node syntax checking, PHP CLI | Tools/tests only; the temporary signed PHP package is not installed system-wide or bundled in source |

The app metadata advertises Nextcloud 28–35 and PHP 8.1+, but this is not a tested
matrix. PHP 8.3 is listed by the [Nextcloud 32 requirements](https://docs.nextcloud.com/server/32/admin_manual/installation/system_requirements.html).
The current test runtime was PHP 8.3.36 with host INI loading disabled. This does
not choose or certify a production dependency stack.

For a source-only experimental release, preserve notices and disclose these
boundaries. For a combined distribution or deployment, review the exact external
releases, their licenses and integration obligations. The tool can inventory
references; it cannot establish hidden input rights or settle legal scope.

## Experimental source distribution

The current proposal distributes these source files and preserved notices only.
It does not bundle dependency implementations, images, binaries, full environment
configuration or claim one BSD license over the entire project. Exact dependency
versions, combined-work obligations and deployment compatibility remain separate
review requirements before any such distribution or installation. A maintainer's
acceptance of this source-only scope is recorded in the release decision ledger;
it is not a legal certification of future combinations.
