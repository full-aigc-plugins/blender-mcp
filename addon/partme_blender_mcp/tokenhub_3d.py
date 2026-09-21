"""TokenHub 3D 官方 HTTP 协议适配器。"""
from __future__ import annotations

from urllib.parse import urlparse

from .harness.errors import HarnessError


BASE_URL = "https://tokenhub.tencentmaas.com/v1/api/3d"
_STATUS = {
    "queued": "WAIT", "in_progress": "RUN", "completed": "DONE", "failed": "FAIL",
}


def _post(http, path: str, payload: dict, api_key: str) -> dict:
    if not isinstance(api_key, str) or not api_key.strip():
        raise HarnessError("PROVIDER_CONFIGURATION_REQUIRED", "TokenHub API Key 未配置")
    with http.post(
        BASE_URL + path,
        headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
        json=payload,
        timeout=(5, 30),
        allow_redirects=False,
    ) as response:
        if response.status_code not in {200, 201, 202}:
            raise HarnessError(
                "PROVIDER_REQUEST_FAILED", "TokenHub 请求未确认；请检查任务，勿自动重复提交")
        result = response.json()
    if not isinstance(result, dict) or result.get("error"):
        raise HarnessError("PROVIDER_REQUEST_FAILED", "TokenHub 返回错误，请检查凭证与参数")
    return result


def submit(http, model: str, payload: dict, api_key: str) -> dict:
    """提交任务并保留现有异步执行器可识别的 JobId。"""
    result = _post(http, "/submit", {"model": model, **payload}, api_key)
    task_id = result.get("id")
    if not isinstance(task_id, (str, int)) or not str(task_id).strip():
        raise HarnessError("PROVIDER_BAD_RESULT", "TokenHub 提交响应缺少任务 ID")
    return {**result, "JobId": str(task_id)}


def query(http, model: str, task_id: str, api_key: str) -> dict:
    """查询任务并归一化为现有混元轮询与资产解析契约。"""
    result = _post(http, "/query", {"model": model, "id": task_id}, api_key)
    status = _STATUS.get(str(result.get("status", "")).lower())
    if status is None:
        raise HarnessError("PROVIDER_BAD_RESULT", "TokenHub 返回未知任务状态")
    files = []
    for item in result.get("data") or []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("url"), str):
            files.append({"Type": str(item.get("type", "")).upper(), "Url": item["url"]})
        for kind in ("glb", "fbx", "obj"):
            url = item.get(kind + "_url")
            if isinstance(url, str):
                files.append({"Type": kind.upper(), "Url": url})
    response = {"JobId": str(task_id), "Status": status, "ResultFile3Ds": files}
    if result.get("error"):
        response["Error"] = {"Code": "TokenHubTaskFailed", "Message": "TokenHub 任务失败"}
    return {"Response": response, "_tokenhub": {"requestId": result.get("request_id")}}


def trusted_result_url(url: str) -> bool:
    """校验 TokenHub 返回的腾讯对象存储 HTTPS 地址。"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and (host.endswith(".tencentcos.cn") or (".cos." in host and host.endswith(".myqcloud.com"))))
