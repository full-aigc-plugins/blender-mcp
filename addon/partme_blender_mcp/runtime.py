"""Lifecycle adapter from the Blender Add-on to the shared Harness."""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path


_CURRENT = None


def _default_start_function():
    try:
        from .harness.server import start_harness
    except ImportError:
        from scripts.harness.server import start_harness
    return start_harness


def start(bpy_module, *, session_id: str | None = None, runtime_dir: Path | None = None, approved_output_root: Path | None = None, approved_asset_roots=(), start_function=None, execution_policy=None):
    global _CURRENT
    if _CURRENT is not None and not getattr(_CURRENT, "closed", False):
        return _CURRENT
    session_id = session_id or "partme-" + secrets.token_hex(8)
    runtime_dir = Path(runtime_dir or os.environ.get("PARTME_BLENDER_RUNTIME_DIR") or (Path(tempfile.gettempdir()) / "partme-blender"))
    function = start_function or _default_start_function()
    try:
        from .harness.provider_tasks import get_provider_task_registry
    except ImportError:
        from scripts.harness.provider_tasks import get_provider_task_registry
    get_provider_task_registry().clear()
    _CURRENT = function(
        bpy_module,
        session_id=session_id,
        runtime_dir=runtime_dir,
        approved_output_root=approved_output_root,
        approved_asset_roots=approved_asset_roots,
        execution_policy=execution_policy,
        runtime_mode="connector",
    )
    return _CURRENT


def stop():
    global _CURRENT
    if _CURRENT is not None:
        _CURRENT.close()
        _CURRENT = None
    try:
        from .harness.provider_tasks import get_provider_task_registry
    except ImportError:
        from scripts.harness.provider_tasks import get_provider_task_registry
    get_provider_task_registry().clear()


def current():
    return _CURRENT


def is_running() -> bool:
    return _CURRENT is not None and not getattr(_CURRENT, "closed", False)


def on_file_loaded(_unused=None):
    """Revoke the old scene authorization whenever Blender loads another file."""
    if not getattr(_CURRENT, "executing", False):
        stop()
