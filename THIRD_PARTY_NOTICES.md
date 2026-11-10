# Existing notices and external dependencies

The complete Nextcloud app package remains under its existing AGPL declaration.
The following notice is preserved verbatim in `apps/covin_account_admin/LICENSE`:

```text
SPDX-License-Identifier: AGPL-3.0-or-later

Copyright (C) 2026 Covin Family Services
```

The app's remaining permission/warranty notice and `appinfo/info.xml` licence
field are unchanged. A full, unmodified AGPL text is supplied in
`LICENSES/AGPL-3.0-or-later.txt`, including its Free Software Foundation copyright
and verbatim-copy permission. The root BSD grant does not replace either notice.

The candidate references external Nextcloud/OCP and Sabre APIs plus Mailcow,
Authentik/Django, Dovecot/SOGo and host utilities. Their complete implementations,
images, binaries, dependencies and production configuration are not bundled.
Consult the exact dependency releases' licenses for any actual distribution.
This file does not declare those products BSD or grant rights over their code.

No other third-party copyright header/vendor payload was identified in this
limited source review. Any subsequently identified third-party text, code or
asset must retain its actual notice and be entered in the license map; do not
replace it with a first-party header. Ownership questions remain in LICENSING.md.
