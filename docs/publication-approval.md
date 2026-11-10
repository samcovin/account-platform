# Public experimental source approval — 2026-11-10T01:57:28+00:00

The maintainer explicitly approved public experimental source publication to
`samcovin/account-platform`, GitHub private vulnerability reporting before the
first source push, and the subsequent public fork
`doublednurseryama/account-platform`. The selected author/committer is Sam Covin
using the maintainer-approved GitHub noreply identity. This approval does not
authorize production deployment, real-service operations or employer endorsement.

The fresh initial commit `141c3f7ac3940c5db893cc5b5e4c1f82a5568a36` contains the exact reviewed 103-file
source tree `69d77c1070e67fa93430a06dcb7853e293bab0ef`. No recovered private Git history was imported.
A separate documentation commit records this approval and closes the final gate;
application/runtime code, existing per-file grants, license notices and app
metadata remain unchanged. The two new approval/change records use the existing
first-party BSD scope. This is not a stable binary, image or service release.

GitHub authenticated the approved personal owner. A new empty public repository
was created without a generated README/license or source branch. GitHub private
vulnerability reporting was enabled and verified at **2026-11-10T02:00:45+00:00**, while
there were still zero branches and before any source push. The remote setting is
verified independently of SECURITY.md. It must be rechecked before pushing.

All six named source-release gates now have recorded evidence. PHP has actual
local lint/mock/loopback-fixture evidence. Ownership and source-distribution scope
are maintainer statements/decisions. Security and service gates refer to disabled
experimental source with disclosed limits, not to passed real integrations.
Nextcloud/Mailcow/Authentik, FPM/TLS/browser, migrations, populated upgrades, real
database races and encrypted recovery remain untested. Installation privacy,
MFA/TLS, retention, export scope and password delivery still need configuration.

The reviewed archive and exact pre-publication manifest are protected separately
outside Git. Actual source-push/fork results, final remote commit and UTC times
are recorded separately after verification. This approval checkpoint itself does
not assert those later operations completed. See
[scope](experimental-release.md), [security](../SECURITY.md),
[release checklist](../RELEASE_CHECKLIST.md) and [handoff](github-handoff.md).
