# Component licensing and provenance

The maintainer reports that the first-party code was generated through ChatGPT
at his direction for his requirements, permits reuse, selected BSD 3-Clause for
rights he controls, and explicitly chose the public copyright name **Sam Covin**.
That declaration is the basis for the new first-party grant; it is not a finding
that all generated material is copyrightable, exclusive, independently authored
or free of third-party rights. See the open questions below.

| Component | Applied license | Basis / limits |
| --- | --- | --- |
| `apps/covin_account_admin/**` | AGPL-3.0-or-later | Existing app LICENSE and metadata retained; no BSD substitution or dual-license claim |
| `host/worker/**` | BSD-3-Clause for first-party source | Maintainer's stated generation/permission; original third-party material, if identified, keeps its own terms |
| `host/account/**` | BSD-3-Clause for first-party source | Same grant; Nextcloud-bootstrap helpers, lab code and mocks require dependency/combined-work review |
| `host/export/**` | BSD-3-Clause for first-party source | Same grant; Nextcloud/Sabre/Dovecot runtime behavior is not itself relicensed |
| `public/**` | BSD-3-Clause for first-party source | Same grant; handler/proxy examples need runtime/privacy review |
| `tools/**`, `docs/**`, root guidance/config | BSD-3-Clause for first-party source | Same grant, including generated preparation tools and documentation |
| `LICENSES/AGPL-3.0-or-later.txt` | Verbatim license document, not a new BSD software grant | Free Software Foundation notice and license-document copying permission retained |
| External runtime/tool dependencies | Their own licenses; not bundled | No license or ownership claim over Nextcloud, Sabre, Mailcow, Authentik, Dovecot, SOGo, PHP, Python, Docker, curl or 7-Zip |

The root [LICENSE](LICENSE) contains the BSD grant for the scoped first-party
components above. It does not override nested app notices or third-party terms.
[LICENSE-MAP.json](LICENSE-MAP.json) assigns every candidate file and pins the
required notice bytes. Existing notices are collected in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The app metadata still says agpl;
its original copyright is `Copyright (C) 2026 Covin Family Services`.

## Maintainer statement and remaining distribution review

The maintainer confirmed no outside material or known employer/client/contributor
ownership restriction for this release. This statement closes the source ownership
question on the evidence available; it is not an independent audit of all inputs.
Reopen it if separate source terms or an agreement are later identified.

The older Covin Family Services app notice remains unchanged. This preparation
does not transfer that attribution, replace AGPL with BSD or assert dual licensing.
Review the actual dependency versions and Nextcloud/Sabre app/helper boundaries
before any combined distribution. A first-party BSD grant does not determine
obligations for a combined or derivative work. The proposed experimental artifact
contains source and notices only, without runtime implementations/images/binaries;
the maintainer explicitly accepted that scope, separately from any deployment
or combined-distribution review.

The chosen personal copyright name is intentionally public. Other personal
addresses, account IDs, private remotes and raw generation/operator transcripts
are not part of the candidate. No third-party source was identified as bundled
in this limited review beyond retained license documents; absence of a vendor
tree is not proof that no earlier code was adapted.

License text references: [OSI BSD 3-Clause](https://opensource.org/license/bsd-3-clause)
and [SPDX AGPL text](https://raw.githubusercontent.com/spdx/license-list-data/main/text/AGPL-3.0-or-later.txt).
