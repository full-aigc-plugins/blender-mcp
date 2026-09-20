"""原生供应商执行结果到界面任务状态的适配，不依赖宿主插件。"""
from .provider_tasks import get_provider_task_registry
import math

GENERATION_COMMANDS = {
    'create_rodin_job': 'hyper3d', 'poll_rodin_job_status': 'hyper3d',
    'create_hunyuan_job': 'hunyuan3d', 'poll_hunyuan_job_status': 'hunyuan3d',
}
TASK_KEYS = ('subscription_key', 'request_id', 'job_id', 'JobId', 'task_uuid', 'uuid', 'id')


def find_value(payload, keys):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload[key]
    for value in payload.values():
        found = find_value(value, keys)
        if found is not None:
            return found
    return None


def record_generation_result(command, params, result, *, registry=None,
                             task_id_override=None, remote_task_id=None):
    provider = GENERATION_COMMANDS.get(command)
    if provider is None or not isinstance(result, dict):
        return None
    task_id = find_value(params, TASK_KEYS) if command.startswith('poll_') else None
    if command == 'create_rodin_job':
        task_id = task_id or find_value(result, ('subscription_key',))
    task_id = task_id or find_value(result, TASK_KEYS)
    remote_task_id = remote_task_id or task_id
    task_id = task_id_override or task_id
    if not isinstance(task_id, (str, int)) or not str(task_id).strip():
        return None
    task_id = str(task_id)
    registry = registry or get_provider_task_registry()
    current = registry.status(provider, task_id)
    if current and current.get('cancelRequested'):
        return current
    # 创建回执允许只有任务 ID；查询回执必须有可解析状态，不能把空响应当成生成中。
    if 'status_list' in result:
        statuses = result['status_list']
    else:
        status = find_value(result, ('status', 'state', 'Status', 'State'))
        statuses = [status if status is not None else (
            'PROCESSING' if command.startswith('create_') else None)]
    if (not isinstance(statuses, list) or not statuses
            or any(not isinstance(status, str) or not status.strip() for status in statuses)):
        raise ValueError('provider response is missing valid generation status')
    statuses = [status.strip().upper() for status in statuses]
    successful = {'COMPLETE', 'COMPLETED', 'SUCCEED', 'SUCCEEDED', 'SUCCESS', 'SUCCESSFUL', 'DONE', 'FINISHED'}
    if any(any(token in status for token in ('FAIL', 'ERROR', 'REJECT')) for status in statuses):
        state, stage = 'failed', '生成失败'
    elif any('CANCEL' in status for status in statuses):
        state, stage = 'cancelled', '供应商已取消'
    elif all(status in successful for status in statuses):
        state, stage = 'completed', '生成完成'
    else:
        state, stage = 'generating', '已提交 · 等待生成' if command.startswith('create_') else '正在轮询结果'
    progress = find_value(result, ('progress', 'Progress', 'percentage', 'percent'))
    if isinstance(progress, (float, int)) and not isinstance(progress, bool) and math.isfinite(progress):
        progress = max(0.0, min(1.0, progress / 100 if progress > 1 else progress))
    else:
        progress = None
    if state == 'completed':
        progress = 1.0
    if current is None:
        registry.update({'operation': 'start', 'providerId': provider, 'taskId': task_id,
                         'state': 'generating', 'cancelSupported': False,
                         'remoteTaskId': remote_task_id})
    return registry.update({'operation': 'finish' if state in {'completed', 'failed', 'cancelled'} else 'update',
        'providerId': provider, 'taskId': task_id, 'state': state, 'progress': progress,
        'stage': stage, 'statusText': stage, 'cancelSupported': False,
        'remoteTaskId': remote_task_id})
