"""Thread-safe, provider-neutral task state used by Blender UI and plugin bridges."""

from __future__ import annotations

import copy
import re
import threading
import time
from collections import OrderedDict


PROVIDER_TASK_SCHEMA = "partme-provider-task/v1"
ACTIVE_STATES = frozenset({"submitting", "generating", "downloading", "staged", "importing"})
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})
VALID_STATES = ACTIVE_STATES | TERMINAL_STATES
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{1,63}")


class ProviderTaskError(ValueError):
    """Raised when a provider task update violates the shared task protocol."""


class ProviderTaskRegistry:
    """Own live provider tasks without coupling the UI to a provider implementation."""

    def __init__(self, *, clock=time.time, limit: int = 128):
        self._clock = clock
        self._limit = limit
        self._tasks: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self._lock = threading.RLock()

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()

    def update(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ProviderTaskError("provider task update must be an object")
        operation = payload.get("operation")
        if operation not in {"start", "update", "finish"}:
            raise ProviderTaskError("provider task operation must be start, update or finish")
        provider_id = self._provider_id(payload.get("providerId"))
        task_id = self._task_id(payload.get("taskId"))
        state = payload.get("state")
        if state not in VALID_STATES:
            raise ProviderTaskError("provider task state is invalid")
        if operation == "finish" and state not in TERMINAL_STATES:
            raise ProviderTaskError("finish requires a terminal provider task state")
        if operation != "finish" and state in TERMINAL_STATES:
            raise ProviderTaskError("terminal provider task states require finish")
        progress = self._progress(payload.get("progress"))
        cancel_supported = payload.get("cancelSupported", False)
        if type(cancel_supported) is not bool:
            raise ProviderTaskError("cancelSupported must be boolean")
        now = self._clock()
        key = (provider_id, task_id)
        with self._lock:
            current = self._tasks.get(key)
            if operation == "start":
                created_at = now
            elif current is None:
                raise ProviderTaskError("provider task does not exist")
            else:
                created_at = current["createdAt"]
                cancel_supported = payload.get("cancelSupported", current["cancelSupported"])
            task = {
                "schemaVersion": PROVIDER_TASK_SCHEMA,
                "providerId": provider_id,
                "taskId": task_id,
                "state": state,
                "active": state in ACTIVE_STATES,
                "progress": progress if progress is not None else (current or {}).get("progress"),
                "stage": self._text(payload.get("stage"), (current or {}).get("stage")),
                "statusText": self._text(payload.get("statusText"), (current or {}).get("statusText")),
                "message": self._text(payload.get("message"), (current or {}).get("message")),
                "cancelSupported": cancel_supported,
                "cancelRequested": bool((current or {}).get("cancelRequested", False)),
                "remoteMayContinue": bool((current or {}).get("remoteMayContinue", False)),
                "createdAt": created_at,
                "updatedAt": now,
            }
            self._tasks[key] = task
            self._tasks.move_to_end(key)
            while len(self._tasks) > self._limit:
                self._tasks.popitem(last=False)
            return copy.deepcopy(task)

    def request_cancel(self, provider_id: str, task_id: str) -> dict:
        provider_id = self._provider_id(provider_id)
        task_id = self._task_id(task_id)
        key = (provider_id, task_id)
        with self._lock:
            current = self._tasks.get(key)
            if current is None:
                raise ProviderTaskError("provider task does not exist")
            if not current["active"]:
                return copy.deepcopy(current)
            remote_may_continue = not current["cancelSupported"]
            message = ("已停止等待，远端任务可能仍在运行" if remote_may_continue else
                       "已请求供应商取消生成")
            task = dict(current)
            task.update({
                "state": "cancelled",
                "active": False,
                "stage": "已终止",
                "statusText": "已终止",
                "message": message,
                "cancelRequested": True,
                "remoteMayContinue": remote_may_continue,
                "updatedAt": self._clock(),
            })
            self._tasks[key] = task
            self._tasks.move_to_end(key)
            return copy.deepcopy(task)

    def status(self, provider_id: str, task_id: str | None = None) -> dict | None:
        provider_id = self._provider_id(provider_id)
        with self._lock:
            if task_id is not None:
                task = self._tasks.get((provider_id, self._task_id(task_id)))
                return copy.deepcopy(task) if task is not None else None
            for (candidate, _), task in reversed(self._tasks.items()):
                if candidate == provider_id:
                    return copy.deepcopy(task)
        return None

    def latest(self, provider_id: str, *, active_only: bool = False) -> dict | None:
        task = self.status(provider_id)
        if active_only and task is not None and not task["active"]:
            return None
        return task

    def snapshot(self) -> dict:
        with self._lock:
            tasks = [copy.deepcopy(task) for task in self._tasks.values()]
        return {"schemaVersion": PROVIDER_TASK_SCHEMA, "tasks": tasks}

    def control(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ProviderTaskError("provider task control must be an object")
        operation = payload.get("operation")
        if operation in {"start", "update", "finish"}:
            return self.update(payload)
        if operation == "status":
            task = self.status(payload.get("providerId"), payload.get("taskId"))
            return task or {"schemaVersion": PROVIDER_TASK_SCHEMA, "task": None}
        if operation == "list":
            return self.snapshot()
        raise ProviderTaskError("unknown provider task operation")

    @staticmethod
    def _provider_id(value) -> str:
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ProviderTaskError("providerId must be lower snake_case")
        return value

    @staticmethod
    def _task_id(value) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ProviderTaskError("taskId must be a non-empty string of at most 256 characters")
        return value.strip()

    @staticmethod
    def _progress(value) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ProviderTaskError("progress must be a number from 0 to 1")
        return float(value)

    @staticmethod
    def _text(value, fallback=None) -> str | None:
        if value is None:
            return fallback
        if not isinstance(value, str):
            raise ProviderTaskError("provider task text fields must be strings")
        return value[:512]


_TASK_REGISTRY = ProviderTaskRegistry()


def get_provider_task_registry() -> ProviderTaskRegistry:
    return _TASK_REGISTRY
