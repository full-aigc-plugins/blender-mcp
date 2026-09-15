# v0.1.1 License Compliance Triage

> Engineering compliance review, not legal advice  
> Review date: 2026-09-15

## Policy

The release must allow open-source and commercial use without requiring disclosure of downstream project source. All shipped source must carry an identified license; Blender itself and vendor services must not be redistributed.

## Inventory

| Coordinate/component | Scope | Declared license | Usage | Decision | Obligations |
|:---|:---|:---|:---|:---|:---|
| `partme-blender-mcp 0.1.1` | Runtime/Add-on | Apache-2.0 | Original and migrated PartMe source | Pass | Ship LICENSE and NOTICE |
| Python standard library | Runtime/build | PSF | Dynamic runtime dependency | Pass | No bundled interpreter |
| Blender | External host | GPL | Interoperability target, not redistributed | Not in release | Preserve trademark attribution |
| Generated brand images | Documentation | Project-owned generated assets | README/release artwork | Pass | Keep provenance note |

`pyproject.toml` declares no third-party Python runtime dependencies. GitHub Actions are build infrastructure and are not bundled in the release archives.

## Result

- Raw dependency findings: 0
- Confirmed false positives: 0
- Blocking licenses: 0
- Unresolved license expressions: 0
- Decision: pass for prerelease packaging, subject to preserving LICENSE, NOTICE, THIRD_PARTY_NOTICES, and the generated-image provenance file.

Trademark and product-name rights are outside this engineering license review. The README describes Blender and client products only as interoperability targets and does not imply endorsement.
