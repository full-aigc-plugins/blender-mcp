"""有界供应商只读查询；网络线程不接触 Blender API。"""

from __future__ import annotations

import copy
import json
import threading
from collections import OrderedDict
from uuid import uuid4


class ProviderQueryRunner:
    """立即登记查询任务，在后台保存有界、可轮询的 JSON 结果。"""

    def __init__(self, registry, *, max_workers=4, max_results=32,
                 max_result_bytes=8 * 1024 * 1024, id_factory=None):
        self.registry = registry
        self.max_workers = max_workers
        self.max_results = max_results
        self.max_result_bytes = max_result_bytes
        self.id_factory = id_factory or (lambda: "query_" + uuid4().hex)
        self._lock = threading.RLock()
        self._workers = {}
        self._results = OrderedDict()
        self._closed = threading.Event()

    def submit(self, provider_id, callback):
        """登记并启动只读查询；callback 只能使用已快照的普通数据。"""
        task_id = str(self.id_factory())
        key = provider_id, task_id
        with self._lock:
            if self._closed.is_set():
                raise RuntimeError("provider query runner is closed")
            self._workers = {item: worker for item, worker in self._workers.items()
                             if worker.is_alive()}
            if len(self._workers) >= self.max_workers:
                raise RuntimeError("provider query capacity reached")
            task = self.registry.update({
                "operation": "start", "providerId": provider_id, "taskId": task_id,
                "state": "querying", "stage": "正在查询", "statusText": "正在查询",
                "cancelSupported": False,
            })
            worker = threading.Thread(target=self._run, args=(key, callback),
                                      name="PartMe-provider-query", daemon=True)
            self._workers[key] = worker
            worker.start()
        return task

    def _active(self, key):
        task = self.registry.status(*key)
        return not self._closed.is_set() and task is not None and task["active"]

    def _bounded_result(self, value):
        if not isinstance(value, dict):
            raise ValueError("provider query returned a non-object")
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("provider query returned non-JSON data") from exc
        if len(encoded.encode("utf-8")) > self.max_result_bytes:
            raise ValueError("provider query result exceeds the memory limit")
        return copy.deepcopy(value)

    def _run(self, key, callback):
        try:
            result = self._bounded_result(callback())
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
                "state": "completed", "stage": "查询完成", "statusText": "查询完成",
                "progress": 1, "cancelSupported": False,
            })
        except Exception:
            if self._active(key):
                self.registry.update({
                    "operation": "finish", "providerId": key[0], "taskId": key[1],
                    "state": "failed", "stage": "查询失败", "statusText": "查询失败",
                    "message": "供应商查询失败或超时", "cancelSupported": False,
                })

    def result(self, provider_id, task_id):
        """返回任务状态；仅完成且结果仍在有界缓存中时附带 result。"""
        task = self.registry.status(provider_id, task_id)
        if task is None:
            raise ValueError("provider query task does not exist")
        response = dict(task)
        if task["state"] == "completed":
            with self._lock:
                result = self._results.get((provider_id, task_id))
            if result is None:
                response.update({"state": "failed", "active": False,
                                 "statusText": "查询结果已过期", "message": "请重新查询"})
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
        """停止接受查询并阻止晚到结果回写；不等待网络线程。"""
        self._closed.set()
        with self._lock:
            self._results.clear()
