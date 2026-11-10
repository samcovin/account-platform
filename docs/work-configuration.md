# Remaining configuration and policy assumptions

These are inherited example defaults, not approved runtime policy. No credentials
or real account records are included. Host paths, Docker/SMTP and loaded runtime
configuration can still reach real services despite reserved example domains.
Review and configure tools before any service use.

| Area | Remaining assumption | Decision/configuration needed |
| --- | --- | --- |
| Stack | Nextcloud, Mailcow, Authentik/Django, Dovecot and SOGo APIs | Choose work adapters and test API/identity compatibility |
| Mailcow | `/opt/mailcow-dockerized`, local `mailcow.conf`, runtime API key/hostname; HTTPS can resolve to loopback | Supply reviewed targets/credentials outside Git; do not borrow personal config |
| Authentik | `/opt/authentik`, Compose `server`, `ak shell`, flow `covin-account-enrollment`, creator `akadmin`, username/mailbox mappings | Supply actual flows/providers, creator and protected-account policy |
| Domains/senders | `example.test`, `box.example.test`, `auth.example.test`, `cloud.example.test`, `requests@example.test` | Set work URLs/senders and consistent ingress/TLS/domain checks |
| Containers | `nextcloud-app`, `mailcowdockerized-dovecot-mailcow-1`, `mailcowdockerized-postfix-mailcow-1`, `php-fpm-mailcow`, `postfix-mailcow:25` | Supply isolated work targets; public SMTP can send real mail |
| Paths/access | `/usr/local/sbin/covin-*`, `/usr/local/libexec/covin-export`, `/etc/covin`, `/opt/covin-account-*`, `/run/lock/covin-*`; root ownership/locks | Review installation, filesystem/permission boundaries; sample root units are not installed |
| Quotas/invitations | 5 GiB mailbox quota; welcome text promises 10 GB Nextcloud quota; 7/14/30-day invitations default to 14 | Decide quotas and upstream enforcement; welcome text alone sets no quota |
| Mailbox policy | `authsource=generic-oidc`, empty internal password for that integration, `force_pw_update=false`, `force_tfa=false`, `tls_enforce_in/out=false` | Decide work authentication/MFA/TLS policy; payload fields do not establish whole-stack policy |
| Protected users | `admin`, `administrator`, `akadmin`, `root`, `covin-export-delivery`, other provisioning-reserved names | Define exclusions before account access/closure operations |
| Ingress/IDs | Runtime HMAC, `X-Covin-*`, app/protocol/table/flow IDs and `/web/example.test` | Preserve compatibility or rename as one tested change; provision fresh signing material separately |
| Public proxy | Incomplete include refers to help/assets, rate-limit zone and PHP-FPM service | Build the missing work proxy/site/rate-limit configuration |
| Delivery | `covin-export-delivery`, WebDAV app-password file, `Account Exports` folder, Mailcow sendmail container | Create independent work credentials and recipient/access policy; no password is included |
| Retention | Indefinite rejection history; seven-day delivery/share/archive retention; 180-day plaintext master retention | Decide work retention/audit/access before enabling cleanup, which deletes copies |
| Timers | Worker approximately every minute; daily cleanup at 03:17 UTC plus random delay; root units | Review scheduling/permissions/monitoring; none is enabled here |
| Exports | Current files/calendars/contacts/readable mail, opt-in shared contacts; many app/sharing/version/E2EE-key exclusions | Approve scope/recipient handling and independently verify readable preservation/restoration |
| Labs | Explicitly provided cached image IDs, Nextcloud 32.0.14 assertion, MariaDB, Linux/root/Docker, synthetic data | Review cached images/isolation; populated upgrades require pinned external 0.4.0 source |

Production compose files, DNS/TLS, real identity flows, databases, encryption
keys, export payloads and user logs remain outside source control. Actual runs
require deliberate target/configuration review.

Runtime entrypoints now require ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1 after review. Sample units set it to 0. This opt-in is not authorization; inherited MFA/TLS/retention and delivery/logging choices still need decisions.
