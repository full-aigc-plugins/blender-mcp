"""有界供应商后台提交；线程只接收已快照的普通数据和网络回调。"""
from __future__ import annotations

import threading
from uuid import uuid4


class ProviderSubmitter:
    """立即登记本地任务，在后台完成可能计费的供应商提交。"""

    def __init__(self, registry, *, max_workers=4, id_factory=None):
        self.registry = registry
        self.max_workers = max_workers
        self.id_factory = id_factory or (lambda: "submit_" + uuid4().hex)
        self._lock = threading.Lock()
        self._workers = {}
        self._closed = threading.Event()

    def submit(self, provider_id, callback, *, remote_id, on_submitted):
        """登记提交并立即返回；callback 与 on_submitted 均不得访问 Blender API。"""
        local_id = str(self.id_factory())
        with self._lock:
            if self._closed.is_set():
                raise RuntimeError("provider submitter is closed")
            self._workers = {key: worker for key, worker in self._workers.items() if worker.is_alive()}
            if len(self._workers) >= self.max_workers:
                raise RuntimeError("provider submission capacity reached")
            task = self.registry.update({
                "operation": "start", "providerId": provider_id, "taskId": local_id,
                "state": "submitting", "stage": "正在提交", "statusText": "正在提交",
                "cancelSupported": False,
            })
            key = provider_id, local_id
            worker = threading.Thread(
                target=self._run,
                args=(key, callback, remote_id, on_submitted),
                name="PartMe-provider-submit", daemon=True,
            )
            self._workers[key] = worker
            worker.start()
        return task

    def _active(self, key):
        task = self.registry.status(*key)
        return not self._closed.is_set() and task is not None and task["active"]

    def _run(self, key, callback, remote_id, on_submitted):
        try:
            result = callback()
            value = remote_id(result)
            if not isinstance(value, (str, int)) or not str(value).strip():
                raise ValueError("provider submission did not return a task id")
            value = str(value).strip()
            if not self._active(key):
                return
            self.registry.update({
                "operation": "update", "providerId": key[0], "taskId": key[1],
                "state": "generating", "stage": "已提交 · 等待生成",
                "statusText": "已提交 · 等待生成", "remoteTaskId": value,
                "cancelSupported": False,
            })
            if self._active(key):
                on_submitted(key[1], value, result)
        except Exception:
            if self._active(key):
                self.registry.update({
                    "operation": "finish", "providerId": key[0], "taskId": key[1],
                    "state": "failed", "stage": "提交结果未知", "statusText": "提交结果未知",
                    "message": "供应商提交失败或结果未知；请检查任务，勿自动重复提交",
                    "cancelSupported": False,
                })

    def join(self, provider_id, task_id, *, timeout=None):
        """测试和受控关闭入口；正常 UI 流程不等待网络线程。"""
        with self._lock:
            worker = self._workers.get((provider_id, task_id))
        if worker is not None:
            worker.join(timeout)
        return worker

    def close(self):
        """阻止后续状态回写；不在 Blender 主线程等待网络。"""
        self._closed.set()
