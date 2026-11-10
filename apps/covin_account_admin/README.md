# Account Administration — source 0.5.0

Nextcloud administrator request queue and audit trail. Administrative access is
required for review endpoints. Public ingress uses a separate runtime HMAC secret.
The application does not contain host credentials, a Docker socket or direct
provisioning authority. Approvals are claimed by a separate host worker through
`covin-account:claim`, `complete` and `fail` commands with an ephemeral claim token.

See [architecture](../../docs/architecture.md), [handoff](../../docs/handoff.md) and
[current state](../../docs/current-state.md) for version pairing and candidate limits.
The original app license notice is retained in `LICENSE`.
