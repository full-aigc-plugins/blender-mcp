# Community Add-on (vendored)

- Source: https://github.com/ahujasid/blender-mcp
- Upstream version: 2.0.0 (pyproject `mcp-for-blender`)
- Pinned commit: 6f992ffbca (2026-09-16), file `addon.py`
- License: MIT © 2025 Siddharth Ahuja — see THIRD_PARTY_NOTICES.md
- Local module name: `blender_mcp_community` (packaging-level rename only; file content is verbatim)
- Capability surface: PolyHaven / Sketchfab / Poly Pizza / Hyper3D (Rodin) / Hunyuan3D asset
  providers plus scene introspection, served on localhost TCP 9876 with a JSON protocol.
- Re-vendoring: download `addon.py` from the pinned commit, byte-compare, then update this file.
