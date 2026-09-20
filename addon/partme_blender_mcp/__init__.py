"""PartMe Blender MCP Add-on for a guarded local Blender session."""

bl_info = {
    "name": "PartMe Blender MCP",
    "author": "PartMe.AI",
    # Blender's Add-on discovery parses bl_info with ast.literal_eval; keep this
    # literal and enforce equality with harness.version in the release tests.
    "version": (0, 5, 2),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > PartMe MCP",
    "description": "Expose Blender through the guarded PartMe MCP Harness",
    "category": "Interface",
}


def register():
    import bpy
    from pathlib import Path
    from . import runtime
    from .panel import register as register_panel
    from .harness.provider_registry import reload_provider_registry
    reload_provider_registry(Path(__file__).with_name("providers.json"))
    register_panel()
    from . import provider_engine
    provider_engine.register()
    if runtime.on_file_loaded not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(runtime.on_file_loaded)


def unregister():
    import bpy
    from . import runtime
    from .panel import unregister as unregister_panel
    from .runtime import stop
    from .harness.provider_registry import get_provider_registry
    stop()
    if runtime.on_file_loaded in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(runtime.on_file_loaded)
    unregister_panel()
    from . import provider_engine
    provider_engine.unregister()
    get_provider_registry().clear()
