"""End-to-end verification of the packaged Add-on and both local approval surfaces.

Runs headless against an isolated configuration:

    BLENDER_USER_CONFIG=/tmp/x/config BLENDER_USER_SCRIPTS=/tmp/x/scripts \
      /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
      --python-exit-code 1 --python tests/runtime/addon_and_approval_smoke.py -- /tmp/x/addon

The argument after ``--`` is a directory containing ``partme_blender_mcp`` extracted from
the packaged Add-on ZIP, so the shipped layout is what gets installed.
"""

import json
import sys
import tempfile
from pathlib import Path

ADDON_ROOT = None
if "--" in sys.argv:
    ADDON_ROOT = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
if ADDON_ROOT is None or not (ADDON_ROOT / "partme_blender_mcp").is_dir():
    raise SystemExit("pass the directory that contains partme_blender_mcp/ after '--'")
sys.path.insert(0, str(ADDON_ROOT))

import addon_utils  # noqa: E402
import bpy  # noqa: E402

report = {"blender": bpy.app.version_string}

# 1. Install and enable exactly as a user does from Preferences > Add-ons.
discovered = [module.__name__ for module in addon_utils.modules()]
report["addonDiscovered"] = "partme_blender_mcp" in discovered
bpy.ops.preferences.addon_enable(module="partme_blender_mcp")
report["addonEnabled"] = "partme_blender_mcp" in bpy.context.preferences.addons
report["addonPanelRegistered"] = hasattr(bpy.types, "VIEW3D_PT_partme_blender_mcp")
report["legacyProviderPanelsAbsent"] = not any(hasattr(bpy.types, name) for name in (
    "VIEW3D_PT_partme_blender_permissions",
    "VIEW3D_PT_partme_blender_assets",
    "VIEW3D_PT_partme_blender_ai_models",
))
report["defaultWorkbenchTab"] = bpy.context.window_manager.partme_blender_ui_tab
report["assetStrategyDefault"] = bpy.context.scene.partme_blender_asset_strategy
report["polypizzaConfigureResult"] = list(bpy.ops.partme_blender.provider_settings(
    "EXEC_DEFAULT", provider_id="polypizza", api_key="smoke-polypizza-key",
))
report["polypizzaCredentialStored"] = (
    bpy.context.preferences.addons["partme_blender_mcp"].preferences.polypizza_api_key
    == "smoke-polypizza-key"
)

from partme_blender_mcp import runtime as addon_runtime  # noqa: E402

# 2. Start a live session from the Add-on. The default runtime directory lives under the
#    system temp path, which is short enough for a Unix socket on macOS.
runtime_dir = Path(tempfile.gettempdir()) / "partme-blender"
output_root = Path(tempfile.mkdtemp(prefix="pbm-out-"))
handle = addon_runtime.start(bpy, approved_output_root=output_root)
report["runtimeDir"] = str(runtime_dir)
report["sessionStarted"] = addon_runtime.is_running()
report["descriptorMode"] = oct(handle.descriptor_path.stat().st_mode & 0o777)

# 3. Register shared session operators. The Add-on owns the only visible workbench;
#    Frontend contributes actions and the header but no second sidebar panel.
from partme_blender_mcp.harness.frontend import Frontend  # noqa: E402

frontend = Frontend(bpy, handle)
frontend.register()
report["singleWorkbenchPreserved"] = hasattr(bpy.types, "VIEW3D_PT_partme_blender_mcp")
report["approvalOperators"] = sorted(
    name for name in dir(bpy.ops.partme_blender)
    if name in {"approve_request", "deny_request", "approve_pending", "deny_pending"}
)

session = handle.session
registry = handle.session.dispatch


def call(request_id, command, arguments, *, transaction="tx-read", revision=None):
    payload = {
        "protocolVersion": "codex-blender/v1", "sessionId": session.session_id,
        "requestId": request_id, "transactionId": transaction,
        "command": command, "arguments": arguments,
    }
    if revision is not None:
        payload["expectedSceneRevision"] = revision
    # The transport sets this while a real client's command runs; it tells the runtime's
    # file-load handlers that a snapshot restore belongs to the running command.
    handle.executing = True
    try:
        response = session.handle(payload)
    finally:
        handle.executing = False
    return response.get("error", {}).get("code") or response.get("status")


def begin(transaction):
    return call("begin-" + transaction, "transaction.begin", {}, transaction=transaction)


def commit(transaction):
    return call("commit-" + transaction, "transaction.commit", {}, transaction=transaction)


# Mutations run inside a milestone transaction, as a real client does.
report["beginCreate"] = begin("tx-create")
registry("object.create_mesh", {"name": "SmokeProbe", "primitive": "cube"})
report["probeCreated"] = "SmokeProbe" in bpy.data.objects
report["commitCreate"] = commit("tx-create")

# 4. A gated command is refused and waits for a local decision.
report["beginGated"] = begin("tx-gated")
report["deleteRefused"] = call("ui-1", "object.delete", {"name": "SmokeProbe"},
                               transaction="tx-gated", revision=session.scene_revision)
report["pendingListed"] = [entry["requestId"] for entry in session.pending_authorizations()]
report["probeSurvivesRefusal"] = "SmokeProbe" in bpy.data.objects

# 5. Approve through the Add-on panel operator, which is what a user clicks.
approve_result = bpy.ops.partme_blender.approve_request(request_id="ui-1")
report["addonApproveResult"] = list(approve_result)
report["deleteAfterApproval"] = call("ui-1", "object.delete", {"name": "SmokeProbe"},
                                     transaction="tx-gated", revision=session.scene_revision)
report["probeDeleted"] = "SmokeProbe" not in bpy.data.objects
report["pendingAfterApproval"] = len(session.pending_authorizations())
report["rollbackGated"] = call("rollback-tx-gated", "transaction.rollback", {}, transaction="tx-gated")
report["probeRestoredByRollback"] = "SmokeProbe" in bpy.data.objects

# 6. Deny through the shared session panel operator.
report["beginDeny"] = begin("tx-deny")
report["denyRefused"] = call("ui-2", "object.delete", {"name": "SmokeProbe"},
                             transaction="tx-deny", revision=session.scene_revision)
deny_result = bpy.ops.partme_blender.deny_pending(request_id="ui-2")
report["sessionDenyResult"] = list(deny_result)
report["pendingAfterDeny"] = len(session.pending_authorizations())
report["denyDoesNotReask"] = call("ui-2", "object.delete", {"name": "SmokeProbe"},
                                  transaction="tx-deny", revision=session.scene_revision)
report["rollbackDeny"] = call("rollback-tx-deny", "transaction.rollback", {}, transaction="tx-deny")

# 7. User takeover through the shared session panel: pause, resume, re-inspect.
bpy.ops.partme_blender.pause_work()
report["paused"] = session.paused
bpy.ops.partme_blender.resume_work()
report["resumedNotPaused"] = not session.paused
report["mutationRefusedAfterTakeover"] = call("after-resume", "object.create_mesh",
                                              {"name": "Blocked", "primitive": "cube"})
call("reinspect", "scene.inspect", {})
report["beginFinal"] = begin("tx-final")
report["mutationAllowedAfterReinspect"] = call(
    "after-inspect", "object.create_mesh", {"name": "Allowed", "primitive": "cube"},
    transaction="tx-final", revision=session.scene_revision)
report["commitFinal"] = commit("tx-final")
report["allowedProbeExists"] = "Allowed" in bpy.data.objects
report["blockedProbeAbsent"] = "Blocked" not in bpy.data.objects

# 8. Apply new execution settings to the live session without reconnecting.
reconfigured_output = Path(tempfile.mkdtemp(prefix="pbm-reconfigured-out-"))
reconfigured_assets = Path(tempfile.mkdtemp(prefix="pbm-reconfigured-assets-"))
settings_result = bpy.ops.partme_blender.execution_settings(
    "EXEC_DEFAULT",
    output_root=str(reconfigured_output),
    asset_root=str(reconfigured_assets),
    execution_mode="auto_with_budget",
    asset_strategy="auto_search_generate",
)
descriptor_after_settings = json.loads(handle.descriptor_path.read_text())
report["executionSettingsResult"] = list(settings_result)
report["executionSettingsLive"] = (
    handle.session is session
    and session.execution_policy.mode.value == "auto_with_budget"
    and session.execution_policy.asset_strategy == "auto_search_generate"
)
report["executionSettingsDescriptor"] = (
    descriptor_after_settings["outputRoot"] == str(reconfigured_output.resolve())
    and descriptor_after_settings["assetRoots"] == [str(reconfigured_assets.resolve())]
    and descriptor_after_settings["executionPolicy"]["assetStrategy"] == "auto_search_generate"
)

report["automaticProviderGate"] = call(
    "provider-auto", "provider.external_action",
    {"providerId": "polypizza", "action": "download", "risk": "network_download"},
    transaction="provider-auto", revision=session.scene_revision,
)
report["automaticProviderHasNoApproval"] = not session.pending_authorizations()

# A configured cumulative budget remains automatic while the estimate fits, then
# creates the same trusted local approval card as every other gated action.
from partme_blender_mcp.harness.execution_policy import ExecutionPolicy  # noqa: E402

budget_policy = ExecutionPolicy.from_dict({
    "mode": "auto_with_budget",
    "approvedOutputRoot": str(reconfigured_output.resolve()),
    "assetStrategy": "auto_search_generate",
    "downstreamBudgetLimit": "5.00",
})
handle.reconfigure(
    approved_output_root=reconfigured_output,
    approved_asset_roots=(reconfigured_assets,),
    execution_policy=budget_policy,
    runtime_mode="connector",
)
report["budgetFirst"] = call(
    "provider-budget-1", "provider.external_action",
    {"providerId": "polypizza", "action": "generate", "risk": "paid_generation",
     "estimatedCost": "3.00"}, transaction="provider-budget-1", revision=session.scene_revision,
)
report["budgetExceeded"] = call(
    "provider-budget-2", "provider.external_action",
    {"providerId": "polypizza", "action": "generate", "risk": "paid_generation",
     "estimatedCost": "3.00"}, transaction="provider-budget-2", revision=session.scene_revision,
)
report["budgetPendingApproval"] = [
    entry["requestId"] for entry in session.pending_authorizations()
] == ["provider-budget-2"]
bpy.ops.partme_blender.deny_pending(request_id="provider-budget-2")

# 9. Provider-neutral task progress and trusted local cancellation.
from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry  # noqa: E402

provider_tasks = get_provider_task_registry()
provider_tasks.update({
    "operation": "start", "providerId": "hunyuan3d", "taskId": "smoke-task",
    "state": "generating", "progress": 0.68, "stage": "正在轮询结果",
    "cancelSupported": False,
})
cancel_result = bpy.ops.partme_blender.cancel_provider_task(
    provider_id="hunyuan3d", task_id="smoke-task",
)
cancelled = provider_tasks.status("hunyuan3d", "smoke-task")
report["providerCancelResult"] = list(cancel_result)
report["providerCancelled"] = cancelled["state"] == "cancelled"
report["providerRemoteMayContinue"] = cancelled["remoteMayContinue"]

# 10. Orderly shutdown.
frontend.unregister()
report["singleWorkbenchAfterFrontendStop"] = hasattr(bpy.types, "VIEW3D_PT_partme_blender_mcp")
addon_runtime.stop()
report["sessionStopped"] = not addon_runtime.is_running()
report["descriptorRemoved"] = not handle.descriptor_path.exists()
bpy.ops.preferences.addon_disable(module="partme_blender_mcp")
report["addonDisabled"] = "partme_blender_mcp" not in bpy.context.preferences.addons

print("ADDON_SMOKE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
