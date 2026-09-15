# PartMe Blender MCP: Blender Add-on Installation and Operation Guide

> Support status: **VERIFIED** (Blender 5.2.1 Add-on install and N-panel validation)  
> Applies to: Blender 4.2--5.2, macOS / Windows / Linux  
> Verified: 2026-09-15

> **Pre-release notice**: `v0.1.0` is a pre-release. Download only from [GitHub Release](https://github.com/partme-ai/blender-mcp/releases/latest) and verify SHA-256 before installing.

## 1. Prerequisites

- Blender 4.2 or later installed ([official download](https://www.blender.org/download/)).
- PartMe Blender MCP Runtime installed (see [macOS install](macos.zh-CN.md) or [Windows install](windows.zh-CN.md)).
- `partme-blender-mcp-addon-0.1.0.zip` downloaded from Release and SHA-256 verified.

## 2. Install from Disk

1. Open Blender and select **Edit → Preferences**.

   ![Open Blender Preferences](../assets/reference/blender-open-preferences.png)

2. Go to **Add-ons**, click the top-right menu, and select **Install from Disk...**.

   ![Install from Disk](../assets/reference/blender-install-from-disk.png)

3. Select `partme-blender-mcp-addon-0.1.0.zip`. Do not extract it.
4. Search for and enable **PartMe Blender MCP**.

Do not confuse the community plugin **MCP for Blender** with the PartMe Add-on.

## 3. N-Panel Controls

Return to 3D View, press `N` to open the sidebar, and select the **PartMe MCP** tab.

| Control | Type | Description |
|:---|:---|:---|
| Output | Directory path | **Required**. MCP exports are restricted to this directory. Must be set before clicking Start. |
| Assets | Directory path | Optional. Approved read directory for image textures and imported assets. |
| Mode | Enum | `interactive` (default): review milestones; `auto_with_budget`: complete authorized task and export; `review_only`: read-only inspection, no scene changes or exports. |
| Design missing assets | Checkbox | Default off. When enabled, allows the Harness to generate placeholder proxies for missing assets. |
| Start MCP Server | Button | Shown when not connected. Requires the Output directory to be set. |
| Revoke Access | Button | Shown when connected. Revokes authorization and disconnects the MCP connection. |

## 4. Connection States

- **Not connected**: Shows Output, Assets, Mode, Design missing assets, and the Start MCP Server button.
- **Connected**: Shows only the connection status label and the Revoke Access button. Other controls are hidden.

After connection succeeds, MCP clients can call `blender_connection_status` and `blender_scene_inspect`. However, the client itself still needs `partme_blender` registered in its configuration to use tools -- Add-on connection alone does not make tools available to the client.

## 5. Configure a Client

After starting the Add-on, register the MCP server on the client side:

- [Codex](codex.zh-CN.md)
- [Claude Desktop](claude-desktop.zh-CN.md)
- [Claude Code](claude-code.zh-CN.md)
- [MiniMax Design](minimax-design.zh-CN.md)
- [Cursor](cursor.zh-CN.md)
- [Generic MCP Client](generic-mcp.zh-CN.md)

## 6. Read-Only Acceptance

After the client loads `partme_blender`, call only:

```text
blender_connection_status
blender_scene_inspect
```

Pass conditions: `connected` is `true`; Blender version matches the window; scene objects are readable; receipts contain no private token; N panel shows Connected. Successful connection does not authorize deletion, overwriting, expert Python, or gated final export.

## 7. Upgrading the Add-on

1. Click **Revoke Access** in the N panel.
2. Exit the MCP client.
3. In Preferences → Add-ons, disable **PartMe Blender MCP**.
4. Install the new version ZIP from disk (see section 2).
5. Re-enable and run read-only acceptance.

See the [upgrade guide](upgrade.zh-CN.md) for detailed steps.

## 8. Uninstalling the Add-on

1. Click **Revoke Access**.
2. Go to **Edit → Preferences → Add-ons**, search for PartMe.
3. Disable **PartMe Blender MCP**. Blender may offer to remove it.
4. Delete the Runtime directory you chose during installation.

Preserve: user `.blend` files, render output, assets, and checkpoint directories. See the [uninstall guide](uninstall.zh-CN.md) for detailed steps.

## 9. Common Errors

| Symptom | Cause | Action |
|:---|:---|:---|
| Add-on not found | ZIP does not have `partme_blender_mcp/` at the top level | Confirm the ZIP is from the Release; restart Blender and reinstall |
| Start button grayed out or errors | Output directory not selected | Select a directory in the Output control first |
| Multi-window behavior issues | Multiple Blender sessions conflict | Stop writing, explicitly select the target window |
| Client reports `BLENDER_NOT_CONNECTED` | Start not clicked in N panel | Click Start MCP Server in the 3D View sidebar |
