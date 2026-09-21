"""Durable target locking and deterministic visual-review state transitions."""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .errors import HarnessError
from .image_artifact import MAX_IMAGE_BYTES, inspect_image_bytes, inspect_image_file
from .path_policy import PathPolicy


_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
_SCORES = ("composition", "lighting", "materials", "details")
_TERMINAL = {"accepted", "stalled", "exhausted", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class VisualLoopStore:
    """Persist visual-loop state below one approved output root."""

    def __init__(self, output_root: Path, *, input_roots=()):
        self.output_root = Path(output_root).resolve()
        self.root = self.output_root / "visual-loops"
        self.input_policy = PathPolicy((self.output_root, *input_roots))

    def create(self, arguments: dict) -> dict:
        loop_id = arguments.get("loopId") or f"visual-{secrets.token_hex(6)}"
        self._require_id(loop_id)
        directory = self.root / loop_id
        if directory.exists():
            raise HarnessError("VISUAL_LOOP_EXISTS", f"visual loop already exists: {loop_id}")
        minimum_score = self._number(arguments.get("minimumScore", 8.0), "minimumScore", 0, 10)
        max_rounds = self._integer(arguments.get("maxRounds", 20), "maxRounds", 1, 100)
        stall_window = self._integer(arguments.get("stallWindow", 2), "stallWindow", 1, 20)
        minimum_improvement = self._number(
            arguments.get("minimumImprovement", 1.0), "minimumImprovement", 0.0, 10.0,
        )
        target_data = arguments.get("targetData")
        target_path = arguments.get("targetPath")
        if (target_data is None) == (target_path is None):
            raise HarnessError("INVALID_ARGUMENT", "provide exactly one of targetData or targetPath")
        if target_data is not None:
            data = self._decode_target(target_data)
        else:
            if not isinstance(target_path, (str, os.PathLike)):
                raise HarnessError("INVALID_ARGUMENT", "targetPath must be a filesystem path string")
            source = self.input_policy.require_file(target_path)
            if source.stat().st_size > MAX_IMAGE_BYTES:
                raise HarnessError("IMAGE_INVALID", "target image exceeds the 20 MiB limit")
            data = source.read_bytes()
        media_type, width, height = inspect_image_bytes(data)
        suffix = ".png" if media_type == "image/png" else ".jpg"
        directory.mkdir(parents=True)
        target = directory / f"target{suffix}"
        temporary = directory / f".target{suffix}.part"
        try:
            self._write_private(temporary, data)
            os.replace(temporary, target)
            receipt = inspect_image_file(target)
            state = {
                "schemaVersion": 1,
                "loopId": loop_id,
                "state": "active",
                "target": receipt,
                "config": {
                    "minimumScore": minimum_score,
                    "maxRounds": max_rounds,
                    "stallWindow": stall_window,
                    "minimumImprovement": minimum_improvement,
                },
                "history": [],
                "currentRound": 0,
                "bestRound": None,
                "bestScore": None,
                "recommendedAction": "revise",
                "pendingTransactionId": None,
                "createdAt": _now(),
                "updatedAt": _now(),
            }
            self._save(state)
            return state
        except Exception:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            if not (directory / "state.json").exists():
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise

    def status(self, arguments: dict) -> dict:
        state = self._load(arguments.get("loopId"))
        current = inspect_image_file(Path(state["target"]["path"]))
        if current["sha256"] != state["target"]["sha256"]:
            raise HarnessError("VISUAL_TARGET_CHANGED", "locked visual target no longer matches its SHA-256")
        return state

    def record_capture(self, arguments: dict) -> dict:
        state = self.status({"loopId": arguments.get("loopId")})
        self._require_active(state)
        if state["history"] and state["history"][-1]["verdict"] is None:
            raise HarnessError("VISUAL_VERDICT_REQUIRED", "record a verdict before starting another round")
        transaction_id = arguments.get("transactionId")
        if not isinstance(transaction_id, str) or not transaction_id.strip():
            raise HarnessError("INVALID_ARGUMENT", "transactionId must be a non-empty string")
        artifact = arguments.get("artifact")
        if not isinstance(artifact, dict):
            raise HarnessError("INVALID_ARGUMENT", "artifact must be an image receipt")
        artifact_path = artifact.get("path")
        if not isinstance(artifact_path, (str, os.PathLike)):
            raise HarnessError("INVALID_ARGUMENT", "artifact.path must be a filesystem path string")
        path = self.input_policy.require_file(artifact_path)
        receipt = inspect_image_file(path)
        if artifact.get("sha256") != receipt["sha256"]:
            raise HarnessError("IMAGE_ARTIFACT_CHANGED", "capture does not match its SHA-256 receipt")
        round_number = len(state["history"]) + 1
        if round_number > state["config"]["maxRounds"]:
            raise HarnessError("VISUAL_LOOP_TERMINAL", "visual loop reached its maximum round count")
        state["history"].append({
            "round": round_number,
            "transactionId": transaction_id,
            "artifact": receipt,
            "verdict": None,
            "capturedAt": _now(),
        })
        state["currentRound"] = round_number
        state["pendingTransactionId"] = transaction_id
        state["updatedAt"] = _now()
        self._save(state)
        return state

    def record_verdict(self, arguments: dict) -> dict:
        state = self.status({"loopId": arguments.get("loopId")})
        self._require_active(state)
        round_number = arguments.get("round")
        if not isinstance(round_number, int) or isinstance(round_number, bool) or round_number != state["currentRound"]:
            raise HarnessError("INVALID_ARGUMENT", "round must identify the current captured round")
        entry = state["history"][-1] if state["history"] else None
        if entry is None or entry["verdict"] is not None:
            raise HarnessError("VISUAL_CAPTURE_REQUIRED", "current round has no unreviewed capture")
        scores = arguments.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(_SCORES):
            raise HarnessError("INVALID_ARGUMENT", "scores must contain composition, lighting, materials, and details")
        normalized = {name: self._number(scores[name], name, 0.0, 10.0) for name in _SCORES}
        issues = self._strings(arguments.get("issues"), "issues")
        next_actions = self._strings(arguments.get("nextActions"), "nextActions")
        judge = arguments.get("judge")
        if not isinstance(judge, dict) or judge.get("type") not in {"human", "agent"}:
            raise HarnessError("INVALID_ARGUMENT", "judge.type must be human or agent")
        total = round(sum(normalized.values()) / len(_SCORES), 2)
        entry["verdict"] = {
            "schemaVersion": 1,
            "scores": normalized,
            "total": total,
            "issues": issues,
            "nextActions": next_actions,
            "judge": {key: str(value)[:120] for key, value in judge.items() if key in {"type", "name", "model"}},
            "createdAt": _now(),
        }
        if state["bestScore"] is None or total > state["bestScore"]:
            state["bestScore"] = total
            state["bestRound"] = round_number
        if total >= state["config"]["minimumScore"]:
            state["state"] = "accepted"
            state["recommendedAction"] = "commit"
        elif round_number >= state["config"]["maxRounds"]:
            state["state"] = "exhausted"
            state["recommendedAction"] = "rollback"
        elif self._stalled(state):
            state["state"] = "stalled"
            state["recommendedAction"] = "rollback"
        else:
            state["recommendedAction"] = "revise"
        state["updatedAt"] = _now()
        self._save(state)
        return state

    def cancel(self, arguments: dict) -> dict:
        state = self.status({"loopId": arguments.get("loopId")})
        if state["state"] == "cancelled":
            return state
        if state["state"] in _TERMINAL:
            raise HarnessError("VISUAL_LOOP_TERMINAL", f"visual loop is already {state['state']}")
        state["state"] = "cancelled"
        state["recommendedAction"] = "rollback"
        state["updatedAt"] = _now()
        self._save(state)
        return state

    def _stalled(self, state: dict) -> bool:
        totals = [entry["verdict"]["total"] for entry in state["history"] if entry["verdict"] is not None]
        window = state["config"]["stallWindow"]
        if len(totals) < window + 1:
            return False
        earlier_best = max(totals[:-window])
        recent_best = max(totals[-window:])
        return recent_best - earlier_best < state["config"]["minimumImprovement"]

    def _load(self, loop_id) -> dict:
        self._require_id(loop_id)
        path = self.root / loop_id / "state.json"
        if path.is_symlink():
            raise HarnessError("VISUAL_LOOP_INVALID", "visual loop state must not be a symlink")
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise HarnessError("VISUAL_LOOP_NOT_FOUND", f"visual loop not found: {loop_id}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise HarnessError("VISUAL_LOOP_INVALID", "visual loop state is unreadable") from exc
        if not isinstance(state, dict) or state.get("loopId") != loop_id or state.get("schemaVersion") != 1:
            raise HarnessError("VISUAL_LOOP_INVALID", "visual loop state has an incompatible contract")
        return state

    def _save(self, state: dict) -> None:
        directory = self.root / state["loopId"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "state.json"
        temporary = directory / f".state.{secrets.token_hex(6)}.part"
        try:
            self._write_private(temporary, json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8"))
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _decode_target(value) -> bytes:
        if not isinstance(value, str) or not value or len(value) > (MAX_IMAGE_BYTES * 4 // 3 + 8):
            raise HarnessError("IMAGE_INVALID", "targetData is empty or exceeds the encoded size limit")
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HarnessError("IMAGE_INVALID", "targetData is not valid Base64") from exc

    @staticmethod
    def _require_id(value) -> str:
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            raise HarnessError("INVALID_ARGUMENT", "loopId must contain 1-80 letters, numbers, underscores, or dashes")
        return value

    @staticmethod
    def _number(value, field: str, minimum: float, maximum: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise HarnessError("INVALID_ARGUMENT", f"{field} must be a finite number")
        number = float(value)
        if not minimum <= number <= maximum:
            raise HarnessError("INVALID_ARGUMENT", f"{field} must be between {minimum} and {maximum}")
        return number

    @staticmethod
    def _integer(value, field: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise HarnessError("INVALID_ARGUMENT", f"{field} must be an integer from {minimum} to {maximum}")
        return value

    @staticmethod
    def _strings(value, field: str) -> list[str]:
        if (not isinstance(value, list) or len(value) > 20
                or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in value)):
            raise HarnessError("INVALID_ARGUMENT", f"{field} must contain at most 20 non-empty strings")
        return [item.strip() for item in value]

    @staticmethod
    def _require_active(state: dict) -> None:
        if state["state"] != "active":
            raise HarnessError("VISUAL_LOOP_TERMINAL", f"visual loop is {state['state']}")
