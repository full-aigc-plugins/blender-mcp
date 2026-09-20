"""社区截图/导出参数兼容层；文件权限和导出回执由 PartMe 所有。"""
from pathlib import Path
from .harness.errors import HarnessError
from .harness.exporter import Exporter
from .harness.operation_context import OperationContext
from .provider_engine import ProviderEngine, provider_backend


def execute(command, params, output_root, scene_revision=0):
    if output_root is None:
        raise HarnessError('OUTPUT_NOT_AUTHORIZED', '尚未授权输出目录')
    if not isinstance(params, dict):
        raise HarnessError('INVALID_ARGUMENT', 'params 必须是对象')
    allowed = ({'filepath', 'format', 'max_size'} if command == 'get_viewport_screenshot'
               else {'filepath', 'format', 'object_names', 'selection_only', 'apply_modifiers'})
    if command not in {'get_viewport_screenshot', 'export_scene'} or set(params) - allowed:
        raise HarnessError('INVALID_ARGUMENT', '不支持的文件操作或参数')
    filepath = params.get('filepath')
    if not isinstance(filepath, str) or not filepath.strip():
        raise HarnessError('INVALID_ARGUMENT', 'filepath 必须为授权目录下的文件路径')
    original = Path(filepath)
    path = original.resolve()
    if original.is_symlink() or not path.is_relative_to(Path(output_root).resolve()):
        raise HarnessError('OUTPUT_NOT_AUTHORIZED', '文件路径超出授权目录')
    if path.exists():
        raise HarnessError('OVERWRITE_AUTHORIZATION_REQUIRED', '兼容入口不覆盖已有文件')
    bpy = provider_backend.bpy
    if command == 'get_viewport_screenshot':
        fmt = params.get('format', 'png').lower()
        size = params.get('max_size', 800)
        if fmt not in {'png', 'jpg', 'jpeg'} or path.suffix.lower() not in {'.' + fmt, '.jpeg' if fmt == 'jpg' else '.' + fmt}:
            raise HarnessError('INVALID_ARGUMENT', '截图格式或文件扩展名无效')
        if type(size) is not int or not 64 <= size <= 4096:
            raise HarnessError('INVALID_ARGUMENT', '截图尺寸应在 64 到 4096 之间')
        path.parent.mkdir(parents=True, exist_ok=True)
        result = ProviderEngine().get_viewport_screenshot(max_size=size, filepath=str(path),
                                                        format='jpeg' if fmt == 'jpg' else fmt)
        if result.get('error') or not path.is_file() or path.stat().st_size == 0:
            raise HarnessError('PREVIEW_FAILED', '无法截取视口，请确认前台存在 3D 视图')
        return result
    fmt = params.get('format', 'glb').lower()
    if fmt not in {'glb', 'fbx'} or path.suffix.lower() != '.' + fmt:
        raise HarnessError('INVALID_ARGUMENT', '导出格式与扩展名应为 GLB 或 FBX')
    names = params.get('object_names') or []
    selected_only = params.get('selection_only', False)
    modifiers = params.get('apply_modifiers', True)
    if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
            or type(selected_only) is not bool or type(modifiers) is not bool):
        raise HarnessError('INVALID_ARGUMENT', '对象选择或修改器参数无效')
    objects = []
    for name in names:
        obj = bpy.context.scene.objects.get(name)
        if obj is None:
            raise HarnessError('OBJECT_NOT_FOUND', '导出对象不存在于当前场景')
        for child in [obj, *obj.children_recursive]:
            if child not in objects:
                objects.append(child)
    if not names:
        objects = list(bpy.context.selected_objects if selected_only else bpy.context.scene.objects)
    if not objects:
        raise HarnessError('INVALID_ARGUMENT', '没有可导出的对象')
    parameters = ({'use_selection': True, 'export_apply': modifiers, 'export_animations': True}
                  if fmt == 'glb' else {'use_selection': True, 'use_mesh_modifiers': modifiers, 'bake_anim': True})
    with OperationContext(bpy).active_objects(objects, active=objects[0]):
        receipt = Exporter(bpy, approved_output_root=output_root).export(path,
            session_id='active', scene_revision=scene_revision, snapshot_id='uncommitted', parameters=parameters)
    return {'path': str(path), 'bytes': path.stat().st_size, 'exported': [obj.name for obj in objects],
            'selection_only': bool(names or selected_only), 'artifact': receipt}
