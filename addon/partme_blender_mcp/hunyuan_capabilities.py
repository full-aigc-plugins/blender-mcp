"""腾讯混元 3D 官方 API 的账户 Profile 与可扩展能力注册表。"""
from __future__ import annotations

from typing import NamedTuple


AUTH_ADAPTER_IDS = ('TENCENT_CLOUD_API', 'TOKENHUB_API_KEY')
FUTURE_CAPABILITY_IDS = ()

# TokenHub 的所有 3D 能力共用 submit/query 协议；参数契约仍按能力隔离。
TOKENHUB_MODELS = {
    'PROFESSIONAL': 'hy-3d-3.1',
    'RAPID': 'hy-3d-express',
    'PART': 'hy-3d-component',
    'FORMAT_CONVERSION': 'hy-3d-format',
    'TEXTURE': 'hy-3d-texture',
    'UV': 'hy-3d-uv',
    'REDUCE_FACE': 'hy-3d-retopology',
    'AUTO_RIGGING': 'hy-3d-rigging',
    'MOTION': 'hy-3d-motion',
    'POLYGEN_IMAGE': 'hy-3d-polygen-image',
    'POLYGEN_MESH': 'hy-3d-polygen-mesh',
}


class HunyuanProfile(NamedTuple):
    """一个可签名的腾讯云账户区域与服务组合。"""

    account_region: str
    service_type: str
    service: str
    version: str
    region: str
    submit_body: dict


class HunyuanCapability(NamedTuple):
    """一个独立提交、查询和结果契约。"""

    capability_id: str
    label: str
    submit_action: str
    query_action: str
    supported_profiles: tuple[tuple[str, str], ...]
    input_modes: tuple[str, ...]
    result_type: str
    risk: str


_PROFILES = {
    ('MAINLAND', 'AI3D'): HunyuanProfile(
        account_region='MAINLAND', service_type='AI3D', service='ai3d',
        version='2025-05-13', region='ap-guangzhou', submit_body={},
    ),
    ('INTERNATIONAL', 'HUNYUAN'): HunyuanProfile(
        account_region='INTERNATIONAL', service_type='HUNYUAN', service='hunyuan',
        version='2023-09-01', region='ap-singapore', submit_body={'EnablePBR': True},
    ),
}

_CAPABILITIES = {
    'PROFESSIONAL': HunyuanCapability(
        capability_id='PROFESSIONAL', label='专业版',
        submit_action='SubmitHunyuanTo3DProJob',
        query_action='QueryHunyuanTo3DProJob',
        supported_profiles=tuple(_PROFILES), input_modes=('text', 'image'),
        result_type='model_3d', risk='paid_generation',
    ),
    'RAPID': HunyuanCapability(
        capability_id='RAPID', label='极速版',
        submit_action='SubmitHunyuanTo3DRapidJob',
        query_action='QueryHunyuanTo3DRapidJob',
        supported_profiles=(('MAINLAND', 'AI3D'),), input_modes=('text', 'image'),
        result_type='model_3d', risk='paid_generation',
    ),
}


def resolve_profile(account_region: str, service_type: str) -> HunyuanProfile:
    """解析明确的账户区域与服务组合，不进行隐式跨区回退。"""
    key = (str(account_region).upper(), str(service_type).upper())
    profile = _PROFILES.get(key)
    if profile is None:
        raise ValueError(f'腾讯混元 3D 不支持账户区域/服务组合：{key[0]}/{key[1]}')
    return profile._replace(submit_body=dict(profile.submit_body))


def resolve_capability(capability_id: str, account_region: str,
                       service_type: str) -> HunyuanCapability:
    """解析已启用能力，并验证其是否支持指定账户 Profile。"""
    identifier = str(capability_id).upper()
    if identifier in FUTURE_CAPABILITY_IDS:
        raise ValueError(f'腾讯混元 3D 能力尚未启用：{identifier}')
    capability = _CAPABILITIES.get(identifier)
    if capability is None:
        raise ValueError(f'未知腾讯混元 3D 能力：{identifier}')
    profile_key = (str(account_region).upper(), str(service_type).upper())
    resolve_profile(*profile_key)
    if profile_key not in capability.supported_profiles:
        raise ValueError(f'{capability.label}不支持账户区域/服务组合：{profile_key[0]}/{profile_key[1]}')
    return capability


def resolve_request(capability_id: str, account_region: str, service_type: str) -> dict:
    """返回提交线程可安全复制的能力与签名 Profile 快照。"""
    capability = resolve_capability(capability_id, account_region, service_type)
    profile = resolve_profile(account_region, service_type)
    return {
        'capability_id': capability.capability_id,
        'label': capability.label,
        'submit_action': capability.submit_action,
        'query_action': capability.query_action,
        'risk': capability.risk,
        'service': profile.service,
        'version': profile.version,
        'region': profile.region,
        'submit_body': dict(profile.submit_body),
    }


def resolve_tokenhub_model(capability_id: str) -> str:
    """解析 TokenHub 独立能力模型名，供统一 HTTP 适配器使用。"""
    identifier = str(capability_id).upper()
    model = TOKENHUB_MODELS.get(identifier)
    if model is None:
        raise ValueError(f'未知 TokenHub 3D 能力：{identifier}')
    return model
