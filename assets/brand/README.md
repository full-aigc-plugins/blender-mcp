# PartMe Blender MCP brand assets

| Asset | Use | Size | Notes |
|:---|:---|:---:|:---|
| `logo.png` | Add-on, release, README icon | 1254×1254 RGBA | Transparent orange/blue MCP bridge mark |
| `hero.png` | README and landing hero | 1672×941 RGB | Generic clients flowing into an editable Blender scene |
| `cover.png` | GitHub social preview and release cover | 1254×1254 RGB | Modeling, animation, security, and delivery |
| `architecture.png` | README content illustration | 1672×941 RGB | Client → MCP → guardrails → Blender → verified artifacts |
| `cover-v2.png` | Square safety and recovery cover | 1254×1254 RGB | Vendor-neutral clients → guarded runtime → Blender → verified exports |
| `content-v2.png` | Wide controlled-workflow illustration | 1672×941 RGB | Manual takeover, transaction, scene revision, snapshot, rollback, and export |
| `blender-mcp-cover-v3.png` | Marketing cover and documentation overview | 1672×941 RGB | Text-bearing prompt/tools → editable Blender scene narrative |
| `blender-mcp-content-v3.png` | Documentation and marketplace content card | 1254×1254 RGB | Text-bearing MCP capability-orchestration overview |

## Visual direction

- Bright, optimistic creative studio rather than dark infrastructure imagery.
- Orange represents Blender creation; electric blue represents MCP connectivity; deep navy represents the guarded runtime.
- Generic client cards avoid implying endorsement by Codex, Claude, MiniMax Design, or Cursor.
- The mark is original and does not copy the official Blender logo.
- Canonical `logo.png`, `hero.png`, `cover.png`, and `architecture.png` contain no baked-in explanatory
  copy, so their surrounding README text remains accessible and localizable.
- The versioned `blender-mcp-*-v3.png` marketing illustrations intentionally contain short English
  headings. They supplement, rather than replace, the canonical localization-neutral assets.

## Generation provenance

Generated with the built-in image generation tool on 2026-09-15. References were used for palette,
lighting, and family resemblance only:

- `codex-blender-plugin/assets/blender-cover.png`
- `codex-blender-plugin/assets/banner.webp`
- `codex-dreamina-3d-plugin/assets/dreamina-3d-hero.png`
- `codex-dreamina-3d-plugin/assets/dreamina-3d-cover.png`

The requested subject was a vendor-neutral PartMe MCP bridge, editable 3D viewport, security checkpoint,
recovery loop, and verified artifact delivery, with no third-party client logos, robot mascot, text, or
watermark.

The later `blender-mcp-*-v3.png` pair uses the same reference family for lighting and composition. It
adds explicit Blender MCP workflow headings and shows prompt, tool orchestration, editable scene
structure, materials, animation, and rendering. Generated with the built-in image generation tool on
2026-09-15.

The `cover-v2.png` and `content-v2.png` pair emphasizes the runtime trust boundary: generic MCP
clients, foreground Blender visibility, manual control, transactions, scene revisions, snapshots,
rollback, and verified exports. It was generated with the built-in image generation tool on
2026-09-15 and is kept alongside the complementary v3 marketing pair.
