# Portable export, delivery and retention source

The exporter reads current home files, owned calendars and contacts, optionally
shared contacts, and readable mailbox messages. It writes a root-only plaintext
master export with checksums and a completion marker. It excludes application
databases, most sharing/version metadata, client-held E2EE keys and configuration.
It is not an atomic full-account snapshot or a restore/deletion readiness signal.

Delivery validates the completed payload, creates an AES-256 ZIP, uploads it via
WebDAV and sends a verified recipient its download link and password. Runtime
credentials are loaded from protected files. The config example contains only
placeholders. A dry run does not grant authority to send a real message later.

Cleanup uses independent seven-day delivery and 180-day master retention. It
requires exact receipt paths/hashes and never guesses unregistered master exports.
These are inherited defaults for review, not an approved work-project policy.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s host/export -p 'test_*.py' -v
```

These are offline mocks; PHP/Dovecot/Nextcloud and encrypted restore were not
executed. Host commands and sample systemd units are not installed. Running the
tools can read user content, send email and delete export copies; see
[the adaptation guide](../../docs/handoff.md) before any separately authorized run.

Runtime entrypoints require ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1 after review. The flag is not authorization; sample cleanup units set it to 0. Links and archive passwords currently travel in the same email; review that policy before live delivery.
