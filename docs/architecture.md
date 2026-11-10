# Reusable design and trust boundaries

The public PHP form validates an applicant's fields, signs a server-to-server JSON
request with HMAC, and sends it to a narrow Nextcloud public-ingress endpoint. It
may send receipt/administrator emails. The signing key is loaded from a separate
runtime file; it is not present in this copy.

Nextcloud stores requests and audit events. Administrators review, approve,
reject, retry and request replacement invitations. Approval queues a job; it does
not grant the web application host credentials. Rejection archive/search and
matching history are review aids, not automatic identity decisions.

A separate root-owned host worker uses `occ` to claim a job and receive an
ephemeral token, invokes the host approver, and completes or fails the job. The
approver uses protected Mailcow/Authentik credentials outside Nextcloud. Worker,
app and approver versions must be coordinated. Provisioning is a privileged,
multi-service operation with possible partial failures, not an atomic transaction.

The later snapshot adds a fail-closed closure registry and execution reservations
to stop approval/retry/resend/claim races. The app/approver pair remains a candidate.
Account suspension revokes service access and sessions while preserving incoming
mail and account data. Resume does not recreate revoked tokens.

The exporter reads current home files via Nextcloud APIs plus calendars, contacts
and readable mailbox messages. Delivery validates a completed export, encrypts a
delivery ZIP, uploads it and emails the verified recipient. Master exports remain
plaintext in protected storage. Retention cleanup is separate and potentially
destructive; it uses exact receipt paths and independent delivery/master deadlines.

Read-only closure preflight inventories preservation/dependency blockers. Export,
suspension and preflight do not authorize final account deletion. No complete
final-deletion workflow is implemented here. Server-side encryption and end-to-end
encryption have different recovery requirements; this source is not a backup.

Credentials, applicant records, user content, encryption keys, account exports,
database dumps and private operational logs belong outside source control.
