"""有界后台轮询：只运行纯网络回调与线程安全任务状态，不访问 bpy。"""
import threading
import time

from .provider_execution import GENERATION_COMMANDS, TASK_KEYS, find_value, record_generation_result


class ProviderPoller:
    def __init__(self, registry, *, interval=5.0, max_errors=3, max_duration=7200, max_workers=8):
        self.registry = registry
        self.interval = interval
        self.max_errors = max_errors
        self.max_duration = max_duration
        self.max_workers = max_workers
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._workers = {}

    def start(self, command, params, query, *, task_id=None):
        """query 必须已捕获所需普通数据，禁止在线程内读取 Blender 上下文。"""
        if not command.startswith('poll_') or command not in GENERATION_COMMANDS:
            raise ValueError('unsupported polling command')
        provider = GENERATION_COMMANDS[command]
        task_id = str(task_id or find_value(params, TASK_KEYS) or '')
        key = provider, task_id
        if not task_id or self.registry.status(*key) is None:
            raise ValueError('polling requires a registered task')
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError('poller is closed')
            if key in self._workers:
                return self._workers[key]
            if len(self._workers) >= self.max_workers:
                raise RuntimeError('polling capacity reached')
            worker = threading.Thread(target=self._run, args=(key, command, dict(params), query),
                                      name='PartMe-provider-poll', daemon=True)
            self._workers[key] = worker
            worker.start()
            return worker

    def _active(self, key):
        task = self.registry.status(*key)
        return not self._stop.is_set() and task is not None and task['active']

    def _fail(self, key, message):
        if self._active(key):
            self.registry.update({'operation': 'finish', 'providerId': key[0], 'taskId': key[1],
                'state': 'failed', 'stage': '自动查询已停止', 'statusText': '自动查询已停止',
                'message': message})

    def _run(self, key, command, params, query):
        deadline, errors = time.monotonic() + self.max_duration, 0
        try:
            while self._active(key):
                if time.monotonic() >= deadline:
                    self._fail(key, '自动查询超时；远端状态未知，请检查供应商任务')
                    return
                try:
                    result = query()
                    response = result.get('Response', result) if isinstance(result, dict) else None
                    if (not isinstance(response, dict) or result.get('error') or response.get('Error')):
                        raise ValueError('provider query failed')
                    if not self._active(key):
                        return
                    record_generation_result(
                        command, params, result, registry=self.registry,
                        task_id_override=key[1], remote_task_id=find_value(params, TASK_KEYS),
                    )
                    errors = 0
                except Exception:
                    errors += 1
                    if errors >= self.max_errors:
                        self._fail(key, '连续查询失败；远端状态未知，请检查网络与供应商任务')
                        return
                if self._stop.wait(self.interval):
                    return
        finally:
            with self._lock:
                self._workers.pop(key, None)

    def close(self):
        """不在 Blender 主线程等待网络；在途回调返回后也不得更新界面状态。"""
        self._stop.set()
