"""有界素材网络任务；工作线程不得访问 Blender API。"""

from __future__ import annotations

import copy
import json
import threading
from collections import OrderedDict
from uuid import uuid4


class AssetTransferRunner:
    """在后台执行下载/查询，并通过供应商任务协议暴露状态。"""

    def __init__(self, registry, *, max_workers=4, max_results=32,
                 max_result_bytes=8 * 1024 * 1024, id_factory=None):
        self.registry = registry
        self.max_workers = max_workers
        self.max_results = max_results
        self.max_result_bytes = max_result_bytes
        self.id_factory = id_factory or (lambda: "asset_" + uuid4().hex)
        self._lock = threading.RLock()
        self._workers = {}
        self._results = OrderedDict()
        self._closed = threading.Event()

    def submit(self, provider_id, callback, *, state="downloading", stage="正在下载"):
        task_id = str(self.id_factory())
        key = provider_id, task_id
        with self._lock:
            if self._closed.is_set():
                raise RuntimeError("asset transfer runner is closed")
            self._workers = {item: worker for item, worker in self._workers.items()
                             if worker.is_alive()}
            if len(self._workers) >= self.max_workers:
                raise RuntimeError("asset transfer capacity reached")
            task = self.registry.update({
                "operation": "start", "providerId": provider_id, "taskId": task_id,
                "state": state, "stage": stage, "statusText": stage,
                "cancelSupported": True,
            })
            worker = threading.Thread(
                target=self._run, args=(key, callback),
                name="PartMe-asset-transfer", daemon=True,
            )
            self._workers[key] = worker
            worker.start()
        return task

    def _active(self, key):
        task = self.registry.status(*key)
        return not self._closed.is_set() and task is not None and task["active"]

    def _cancelled(self, key):
        return not self._active(key)

    def _bounded_result(self, value):
        if not isinstance(value, dict):
            raise ValueError("asset transfer returned a non-object")
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > self.max_result_bytes:
            raise ValueError("asset transfer result exceeds the memory limit")
        return copy.deepcopy(value)

    def _run(self, key, callback):
        try:
            result = self._bounded_result(callback(lambda: self._cancelled(key)))
            if not self._active(key):
                return
            with self._lock:
                if not self._active(key):
                    return
                self._results[key] = result
                self._results.move_to_end(key)
                while len(self._results) > self.max_results:
                    self._results.popitem(last=False)
            self.registry.update({
                "operation": "finish", "providerId": key[0], "taskId": key[1],
                "state": "completed", "stage": "素材已暂存", "statusText": "素材已暂存",
                "progress": 1, "cancelSupported": True,
            })
        except Exception:
            if self._active(key):
                self.registry.update({
                    "operation": "finish", "providerId": key[0], "taskId": key[1],
                    "state": "failed", "stage": "素材处理失败", "statusText": "素材处理失败",
                    "message": "素材查询或下载失败", "cancelSupported": True,
                })

    def result(self, provider_id, task_id):
        task = self.registry.status(provider_id, task_id)
        if task is None:
            raise ValueError("asset transfer task does not exist")
        response = dict(task)
        if task["state"] == "completed":
            with self._lock:
                result = self._results.get((provider_id, task_id))
            if result is None:
                response.update({"state": "failed", "active": False,
                                 "statusText": "素材结果已过期", "message": "请重新执行"})
            else:
                response["result"] = copy.deepcopy(result)
        return response

    def join(self, provider_id, task_id, *, timeout=None):
        with self._lock:
            worker = self._workers.get((provider_id, task_id))
        if worker is not None:
            worker.join(timeout)
        return worker

    def close(self):
        self._closed.set()
        with self._lock:
            self._results.clear()
