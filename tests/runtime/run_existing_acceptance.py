"""在隔离 Blender 中复用插件验收用例，但强制测试当前 runtime 源码。

参数：-- <plugin/tests/runtime/example.py> <全新输出目录>
每项命令记录实际执行次数，不把 maturity 或目录存在当作通过证据。
"""
import importlib
import atexit
import json
import runpy
import sys
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[2]
case, output = map(Path, sys.argv[sys.argv.index("--") + 1:])
output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(case.resolve().parents[2]))
import scripts  # noqa: E402

harness = importlib.import_module("partme_blender_mcp.harness")
sys.modules["scripts.harness"] = harness
scripts.harness = harness
runtime = importlib.import_module("scripts.harness.runtime")
original = runtime.build_registry
attempts, successes, failures = Counter(), Counter(), Counter()
catalog = []


def instrumented(*args, **kwargs):
    registry = original(*args, **kwargs)
    dispatch = registry.dispatch
    offset = 0
    while True:
        page = dispatch("capability.list", {"offset": offset, "limit": 100})["result"]
        catalog.extend(item["id"] for item in page["items"])
        if page["nextOffset"] is None:
            break
        offset = page["nextOffset"]

    def measured(command, *args, **kwargs):
        attempts[command] += 1
        try:
            result = dispatch(command, *args, **kwargs)
        except Exception:
            failures[command] += 1
            raise
        successes[command] += 1
        return result

    registry.dispatch = measured
    return registry


runtime.build_registry = instrumented
sys.argv = [str(case), "--", str(output.resolve())]
passed = False
deferred = case.name in {"p7_tracking_foreground.py", "p5_sculpt_foreground.py", "viewport_foreground_acceptance.py"}


def save_coverage():
    result = passed
    if deferred:
        receipt = output / "acceptance.json"
        result = receipt.is_file() and json.loads(receipt.read_text()).get("passed") is True
    (output / "measured-coverage.json").write_text(json.dumps({
        "case": case.name, "passed": result, "source": str(root / "src"),
        "catalog": sorted(set(catalog)), "attempts": attempts,
        "successes": successes, "exceptions": failures,
    }, ensure_ascii=False, indent=2))


if deferred:
    atexit.register(save_coverage)
try:
    runpy.run_path(str(case), run_name="__main__")
    passed = True
finally:
    if not deferred:
        save_coverage()
