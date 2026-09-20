"""隔离进程中的供应商任务状态机与真实后台任务恢复检查。"""
import sys
import time
from pathlib import Path
import bpy
from scripts.harness.runtime import build_registry
from scripts.harness.provider_registry import get_provider_registry, register_native_providers

output = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
registry = build_registry(bpy, approved_output_root=output, approved_asset_roots=(output,))
providers = get_provider_registry()
register_native_providers(providers)
providers.set_status("local_library", {"state": "ready", "statusText": "测试目录已授权"})
assert registry.dispatch("provider.external_action", {
    "providerId": "local_library", "action": "search", "risk": "read",
})["result"]["approved"]
registry.dispatch("provider.task_control", {
    "operation": "start", "providerId": "local_library", "taskId": "isolated-task", "state": "generating",
})
registry.dispatch("provider.task_control", {
    "operation": "finish", "providerId": "local_library", "taskId": "isolated-task", "state": "completed",
})
registry.dispatch("job.submit", {"jobId": "job_recovery_probe", "kind": "EXPORT", "format": "glb"})
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    result = registry.dispatch("job.status", {"jobId": "job_recovery_probe"})["result"]
    if result["state"] in {"completed", "failed"}:
        break
    time.sleep(.1)
assert result["state"] == "completed", result
assert registry.dispatch("job.recover", {"jobId": "job_recovery_probe"})["result"]["state"] == "completed"
print("PROVIDER_JOB=passed; provider state machine only, no external generation")
