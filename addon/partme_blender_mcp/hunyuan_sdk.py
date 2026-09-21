"""腾讯云官方 Python SDK 的最小、可测试适配层。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from .harness.errors import HarnessError


def _import_sdk() -> SimpleNamespace:
    from tencentcloud.common import credential
    from tencentcloud.common.common_client import CommonClient
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.ai3d.v20250513 import models
    from tencentcloud.ai3d.v20250513.ai3d_client import Ai3dClient

    return SimpleNamespace(
        Credential=credential.Credential,
        CommonClient=CommonClient,
        Ai3dClient=Ai3dClient,
        models=models,
        ClientProfile=ClientProfile,
        HttpProfile=HttpProfile,
        sdk_exception=TencentCloudSDKException,
    )


def _load_sdk() -> SimpleNamespace:
    """优先使用声明依赖；Blender ZIP 使用私有 vendor 根，不执行运行时安装。"""
    try:
        return _import_sdk()
    except (ImportError, ModuleNotFoundError):
        vendor_root = Path(__file__).with_name("_vendor")
        if not vendor_root.is_dir():
            raise HarnessError(
                "PROVIDER_DEPENDENCY_MISSING",
                "腾讯云 AI3D SDK 未包含在当前安装包中，请重新安装官方 PartMe Add-on",
            ) from None
        vendor_path = str(vendor_root)
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)
        try:
            return _import_sdk()
        except (ImportError, ModuleNotFoundError) as exc:
            raise HarnessError(
                "PROVIDER_DEPENDENCY_MISSING",
                "腾讯云 AI3D SDK 加载失败，请重新安装官方 PartMe Add-on",
            ) from exc


def _client_profile(sdk, profile):
    http_profile = sdk.HttpProfile()
    http_profile.endpoint = f"{profile['service']}.tencentcloudapi.com"
    http_profile.reqTimeout = 30
    http_profile.reqMethod = "POST"
    http_profile.protocol = "https"
    http_profile.scheme = "https"
    client_profile = sdk.ClientProfile(httpProfile=http_profile)
    client_profile.signMethod = "TC3-HMAC-SHA256"
    client_profile.retryer = None
    return client_profile


def invoke_hunyuan_sdk(action, payload, profile, secret_id, secret_key):
    """调用一个已由能力注册表批准的 Action，并统一还原腾讯云 Response 包装。"""
    if not secret_id or not secret_key:
        raise HarnessError("PROVIDER_CONFIGURATION_REQUIRED", "混元官方凭证未配置")
    if not isinstance(action, str) or not action or not isinstance(payload, dict):
        raise HarnessError("INVALID_ARGUMENT", "混元 SDK 请求参数无效")
    sdk = _load_sdk()
    client_profile = _client_profile(sdk, profile)
    credential = sdk.Credential(secret_id, secret_key)
    try:
        if profile["service"] == "ai3d" and profile["version"] == "2025-05-13":
            request_class = getattr(sdk.models, f"{action}Request", None)
            method = getattr(sdk.Ai3dClient, action, None)
            if request_class is None or method is None:
                raise HarnessError("INVALID_ARGUMENT", f"腾讯混元 3D SDK 不支持操作：{action}")
            request = request_class()
            request.from_json_string(json.dumps(payload, ensure_ascii=False))
            client = sdk.Ai3dClient(credential, profile["region"], client_profile)
            body = json.loads(method(client, request).to_json_string())
        else:
            common_client = getattr(sdk, "CommonClient", None)
            if common_client is None:
                raise HarnessError("INVALID_ARGUMENT", "腾讯云兼容服务需要 CommonClient")
            client = common_client(
                profile["service"], profile["version"], credential,
                profile["region"], client_profile,
            )
            body = client.call_json(action, payload)
    except HarnessError:
        raise
    except Exception as exc:
        raise HarnessError(
            "PROVIDER_REQUEST_FAILED",
            "腾讯混元 3D 官方 SDK 请求失败；提交结果未知时不要自动重试",
        ) from exc
    if isinstance(body, dict) and isinstance(body.get("Response"), dict):
        result = body
    elif isinstance(body, dict):
        result = {"Response": body}
    else:
        raise HarnessError("PROVIDER_BAD_RESULT", "腾讯混元 3D SDK 返回结果无效")
    if result["Response"].get("Error"):
        raise HarnessError("PROVIDER_REQUEST_FAILED", "腾讯混元 3D 官方 API 返回错误")
    return result
