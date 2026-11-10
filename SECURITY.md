# Security handling and operational limits

Do not put credentials, signing/encryption keys, environment files, databases,
account exports, recipient records, filenames from user data or raw user logs in
Git or public issues. The personal upstream's **GitHub private vulnerability
reporting** was enabled and independently verified at **2026-11-10T02:00:45+00:00** before
the first source push. Use the personal upstream repository's
**Security → Report a vulnerability** route. A fork's reporting setting must be
verified independently; do not assume it inherits that feature.
If the private reporting control is unavailable, do not post sensitive evidence
in a public issue; request a private channel without disclosing vulnerability or
personal data. No public issue or pull request substitutes for private reporting.
See [GitHub's reporting setup](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

Host CLIs and the public PHP form use an explicit operator/server-controlled
`ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1` opt-in. Units ship with it disabled. It is
not a secret, authorization check, sandbox or permission to run against production.
The app retains its existing admin/HMAC boundaries. Mock backend injection is
for trusted test code and is not a public security interface.

After opt-in, commands can load host credentials, query private account data,
provision accounts, revoke sessions, send email, upload exports or delete export
copies. Root execution, Docker access and dry runs do not imply safe targets.
Never enable the flag without reviewing configuration and recovery boundaries.

Known decisions remain: Mailcow MFA/TLS flags, complete identity flows, log/IP
collection, export/shared-contact scope, plaintext master retention, indefinite
rejection history and sending export passwords with links in the same email.
No claim is made that source checks establish runtime security, encrypted restore,
full PHP/FPM/TLS deployment correctness or real Nextcloud/Mailcow/Authentik compatibility.

Local PHP lint/mocks and form HTTP/SMTP fixtures pass; this does not choose the unresolved runtime/privacy policy or authorize any production run.

This release is experimental source only. Selecting a reporting route does not
approve an installation's MFA/TLS, logging/IP collection, export scope, password
transport or retention. Those decisions remain prerequisites before service use.
No production-safety or support commitment is implied. See
[experimental scope](docs/experimental-release.md).
