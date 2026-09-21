"""PartMe 所有的进程内供应商执行器；不注册社区 UI，不监听 9876。"""
from . import provider_backend
from .hunyuan_capabilities import resolve_request, resolve_tokenhub_model
from .hunyuan_sdk import invoke_hunyuan_sdk
from .tokenhub_3d import query as query_tokenhub_3d, submit as submit_tokenhub_3d
from .harness.errors import HarnessError
import base64
import re
import json
from urllib.parse import urlparse


COMMANDS = {
    'ping': ('base', 'read'),
    'get_addon_info': ('base', 'read'),
    'get_scene_info': ('base', 'read'),
    'get_world_state_snapshot': ('base', 'read'),
    'get_object_info': ('base', 'read'),
    'describe_node_type': ('base', 'read'),
    'bpy_api_lookup': ('base', 'read'),
    'get_polyhaven_categories': ('polyhaven', 'read'),
    'search_polyhaven_assets': ('polyhaven', 'read'),
    'search_sketchfab_models': ('sketchfab', 'read'),
    'get_sketchfab_model_preview': ('sketchfab', 'read'),
    'create_rodin_job': ('hyper3d', 'paid_generation'),
    'poll_rodin_job_status': ('hyper3d', 'read'),
    'create_hunyuan_job': ('hunyuan3d', 'paid_generation'),
    'poll_hunyuan_job_status': ('hunyuan3d', 'read'),
}

_poller = None
_local_generation = None
_submitter = None
_query_runner = None
_last_task_snapshot = None

NETWORK_QUERY_COMMANDS = frozenset({
    'get_polyhaven_categories', 'search_polyhaven_assets',
    'search_sketchfab_models', 'get_sketchfab_model_preview',
    'poll_rodin_job_status', 'poll_hunyuan_job_status',
})


def _sketchfab_settings(preferences):
    """在主线程捕获可用 Token；仅在 OAuth 临近过期时执行一次有界刷新。"""
    mode = str(getattr(preferences, 'sketchfab_auth_mode', 'API_TOKEN'))
    access_token = str(getattr(preferences, 'sketchfab_access_token', ''))
    if mode == 'OAUTH':
        from .sketchfab_auth import refresh_access_token
        try:
            access_token = refresh_access_token(preferences, http=provider_backend.requests)
        except ValueError as exc:
            preferences.sketchfab_oauth_status = 'ERROR'
            raise HarnessError('PROVIDER_AUTH_FAILED', str(exc)) from exc
    return {
        'sketchfab_api_key': str(getattr(preferences, 'sketchfab_api_key', '')),
        'sketchfab_auth_mode': mode,
        'sketchfab_access_token': access_token,
    }


def _hunyuan_settings(preferences, *, task_type=None):
    """读取新配置并兼容旧版 international Pro 布尔首选项。"""
    legacy_international = bool(getattr(preferences, 'hunyuan3d_intl_pro', False))
    account_region = str(getattr(preferences, 'hunyuan3d_account_region', '') or
                         ('INTERNATIONAL' if legacy_international else 'MAINLAND'))
    service_type = str(getattr(preferences, 'hunyuan3d_service_type', '') or
                       ('HUNYUAN' if legacy_international else 'AI3D'))
    selected_task = str(task_type or getattr(
        preferences, 'hunyuan3d_task_type', 'PROFESSIONAL') or 'PROFESSIONAL')
    return {
        'hunyuan3d_auth_mode': str(getattr(
            preferences, 'hunyuan3d_auth_mode', 'TENCENT_CLOUD_API')),
        'hunyuan3d_secret_id': str(getattr(preferences, 'hunyuan3d_secret_id', '')),
        'hunyuan3d_secret_key': str(getattr(preferences, 'hunyuan3d_secret_key', '')),
        'hunyuan3d_tokenhub_api_key': str(getattr(preferences, 'hunyuan3d_tokenhub_api_key', '')),
        'hunyuan3d_account_region': account_region,
        'hunyuan3d_service_type': service_type,
        'hunyuan3d_task_type': selected_task,
    }


def _redraw_provider_tasks():
    """Blender 主线程定时器：后台任务变化时刷新侧栏，不在线程里调用 UI。"""
    global _last_task_snapshot
    from .harness.provider_tasks import get_provider_task_registry
    snapshot = get_provider_task_registry().snapshot()
    if snapshot != _last_task_snapshot:
        _last_task_snapshot = snapshot
        manager = provider_backend.bpy.context.window_manager
        if manager is not None:
            for window in manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
    return 0.5


def _start_generation_poll(command, task, *, remote_task_id=None, settings=None):
    """在主线程捕获配置；回调只执行有超时的 HTTP，不接触 bpy。"""
    global _poller
    from .harness.provider_tasks import get_provider_task_registry
    from .harness.provider_polling import ProviderPoller
    if settings is None:
        preferences = provider_backend.bpy.context.preferences.addons['partme_blender_mcp'].preferences
        settings = {
            'hyper3d_api_key': str(getattr(preferences, 'hyper3d_api_key', '')),
            'hyper3d_mode': str(getattr(preferences, 'hyper3d_mode', 'MAIN_SITE')),
            **_hunyuan_settings(preferences),
        }
    task_id = str(remote_task_id or task.get('remoteTaskId') or task['taskId'])
    http = provider_backend.requests
    if command == 'create_rodin_job':
        key = settings['hyper3d_api_key']
        if settings['hyper3d_mode'] == 'MAIN_SITE':
            poll_command, params = 'poll_rodin_job_status', {'subscription_key': task_id}
            def query():
                with http.post('https://api.hyper3d.com/api/v2/status',
                        headers={'Authorization': f'Bearer {key}'}, json=params,
                        timeout=(5, 20), allow_redirects=False) as response:
                    response.raise_for_status()
                    return {'status_list': [job['status'] for job in response.json()['jobs']]}
        else:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', task_id):
                raise ValueError('invalid request id')
            poll_command, params = 'poll_rodin_job_status', {'request_id': task_id}
            def query():
                with http.get(f'https://queue.fal.run/fal-ai/hyper3d/requests/{task_id}/status',
                        headers={'Authorization': f'KEY {key}'}, timeout=(5, 20),
                        allow_redirects=False) as response:
                    response.raise_for_status()
                    return response.json()
    elif command == 'create_hunyuan_job':
        poll_command, params = 'poll_hunyuan_job_status', {'job_id': task_id}
        if settings['hunyuan3d_auth_mode'] == 'TOKENHUB_API_KEY':
            model = resolve_tokenhub_model(settings['hunyuan3d_task_type'])
            def query():
                return query_tokenhub_3d(
                    http, model, task_id.removeprefix('job_'),
                    settings['hunyuan3d_tokenhub_api_key'])
        else:
            secret_id, secret_key = settings['hunyuan3d_secret_id'], settings['hunyuan3d_secret_key']
            profile = resolve_request(
                settings['hunyuan3d_task_type'], settings['hunyuan3d_account_region'],
                settings['hunyuan3d_service_type'])
            def query():
                data = {'JobId': task_id.removeprefix('job_')}
                return invoke_hunyuan_sdk(
                    profile['query_action'], data, profile, secret_id, secret_key)
    else:
        raise ValueError('local provider polling is not available')
    if _poller is None:
        _poller = ProviderPoller(get_provider_task_registry())
    return _poller.start(poll_command, params, query, task_id=task['taskId'])


class ProviderEngine(provider_backend.BlenderMCPServer):
    """复用 MIT 上游查询方法；凭证与执行策略由 PartMe 管理。"""

    @staticmethod
    def _describe_property(prop):
        """枚举集合使用 default_flag，避免把空集合当成无效单选枚举 0。"""
        if prop.type != 'ENUM' or not getattr(prop, 'is_enum_flag', False):
            return provider_backend.BlenderMCPServer._describe_property(prop)
        entry = {'identifier': prop.identifier, 'name': prop.name,
                 'type': prop.type, 'description': prop.description,
                 'is_enum_flag': True,
                 'enum_items': [item.identifier for item in prop.enum_items],
                 'default': sorted(prop.default_flag)}
        for attr in ('is_required', 'is_readonly', 'is_argument_optional', 'array_length'):
            value = getattr(prop, attr, None)
            if value is not None:
                entry[attr] = value
        return entry

    def _get_config_value(self, scene_attr, pref_attr=None, env_var=None):
        preferences = provider_backend.bpy.context.preferences.addons['partme_blender_mcp'].preferences
        return getattr(preferences, pref_attr, '') if pref_attr else ''

    def _get_hyper3d_api_key(self):
        return self._get_config_value('', 'hyper3d_api_key')

    def _sketchfab_headers(self):
        mode = self._get_config_value('', 'sketchfab_auth_mode') or 'API_TOKEN'
        if mode == 'OAUTH':
            token = self._get_config_value('', 'sketchfab_access_token')
            if not token:
                raise HarnessError('PROVIDER_CONFIGURATION_REQUIRED', 'Sketchfab OAuth 未授权')
            return {'Authorization': f'Bearer {token}'}
        token = self._get_config_value('', 'sketchfab_api_key')
        if not token:
            raise HarnessError('PROVIDER_CONFIGURATION_REQUIRED', 'Sketchfab API Token 未配置')
        return {'Authorization': f'Token {token}'}

    def search_sketchfab_models(self, query, categories=None, count=20, downloadable=True):
        if not isinstance(query, str) or not query.strip() or not 1 <= int(count) <= 100:
            raise HarnessError('INVALID_ARGUMENT', 'Sketchfab 搜索参数无效')
        params = {'type': 'models', 'q': query.strip(), 'count': int(count),
                  'downloadable': bool(downloadable), 'archives_flavours': False}
        if categories:
            params['categories'] = categories
        with provider_backend.requests.get('https://api.sketchfab.com/v3/search',
                headers=self._sketchfab_headers(), params=params, timeout=(5, 30),
                allow_redirects=False) as response:
            if response.status_code == 401:
                raise HarnessError('PROVIDER_AUTH_FAILED', 'Sketchfab 凭证无效或已过期')
            if response.status_code != 200:
                raise HarnessError('PROVIDER_REQUEST_FAILED', 'Sketchfab 搜索失败')
            payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get('results', []), list):
            raise HarnessError('PROVIDER_BAD_RESULT', 'Sketchfab 搜索响应无效')
        return payload

    def resolve_sketchfab_download(self, uid):
        if not isinstance(uid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,128}', uid):
            raise HarnessError('INVALID_ARGUMENT', 'Sketchfab 模型 ID 无效')
        with provider_backend.requests.get(f'https://api.sketchfab.com/v3/models/{uid}/download',
                headers=self._sketchfab_headers(), timeout=(5, 30), allow_redirects=False) as response:
            if response.status_code == 401:
                raise HarnessError('PROVIDER_AUTH_FAILED', 'Sketchfab 凭证无效或已过期')
            if response.status_code != 200:
                raise HarnessError('PROVIDER_REQUEST_FAILED', 'Sketchfab 下载地址解析失败')
            payload = response.json()
        gltf = payload.get('gltf') if isinstance(payload, dict) else None
        if not isinstance(gltf, dict) or not isinstance(gltf.get('url'), str):
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '该模型没有可下载的 glTF')
        return {'providerId': 'sketchfab', 'url': gltf['url'], 'filename': f'{uid}.zip'}

    def _rodin_submit(self, url, scheme, **payload):
        key = self._get_hyper3d_api_key()
        if not key:
            raise HarnessError('PROVIDER_CONFIGURATION_REQUIRED', 'Rodin 凭证未配置')
        with provider_backend.requests.post(url, headers={'Authorization': f'{scheme} {key}'},
                timeout=(5, 30), allow_redirects=False, **payload) as response:
            if response.status_code not in {200, 201, 202}:
                raise HarnessError('PROVIDER_REQUEST_FAILED', 'Rodin 提交未确认；请检查任务，勿自动重复提交')
            result = response.json()
        if not isinstance(result, dict) or result.get('error'):
            raise HarnessError('PROVIDER_REQUEST_FAILED', 'Rodin 返回错误，请检查参数和任务状态')
        return result

    def create_rodin_job_main_site(self, text_prompt=None, images=None, bbox_condition=None):
        files = [('tier', (None, 'Sketch')), ('mesh_mode', (None, 'Raw')),
                 ('texture_mode', (None, 'high'))]
        if images:
            if not isinstance(images, list) or len(images) > 5:
                raise HarnessError('INVALID_ARGUMENT', 'Rodin 参考图数量无效')
            for index, item in enumerate(images):
                if not isinstance(item, (tuple, list)) or len(item) != 2:
                    raise HarnessError('INVALID_ARGUMENT', 'Rodin 参考图应为扩展名与 base64 内容')
                suffix, encoded = item
                if suffix not in {'.png', '.jpg', '.jpeg'} or not isinstance(encoded, (str, bytes)):
                    raise HarnessError('INVALID_ARGUMENT', 'Rodin 参考图格式无效')
                if len(encoded) > 28 * 1024 * 1024:
                    raise HarnessError('INVALID_ARGUMENT', 'Rodin 参考图过大')
                try:
                    raw = base64.b64decode(encoded, validate=True) if isinstance(encoded, str) else encoded
                except ValueError as exc:
                    raise HarnessError('INVALID_ARGUMENT', 'Rodin 图片 base64 无效') from exc
                if len(raw) > 20 * 1024 * 1024:
                    raise HarnessError('INVALID_ARGUMENT', 'Rodin 参考图超过 20MB')
                files.append(('images', (f'{index:04d}{suffix}', raw)))
        if text_prompt:
            files.append(('prompt', (None, text_prompt)))
        if bbox_condition:
            files.append(('bbox_condition', (None, json.dumps(bbox_condition))))
        return self._rodin_submit('https://api.hyper3d.com/api/v2/rodin', 'Bearer', files=files)

    def create_rodin_job_fal_ai(self, text_prompt=None, images=None, bbox_condition=None):
        data = {'tier': 'Sketch'}
        if text_prompt:
            data['prompt'] = text_prompt
        if images:
            data['input_image_urls'] = images
        if bbox_condition:
            data['bbox_condition'] = bbox_condition
        return self._rodin_submit('https://queue.fal.run/fal-ai/hyper3d/rodin', 'Key', json=data)

    def poll_rodin_job_status_main_site(self, subscription_key):
        if not isinstance(subscription_key, str) or not subscription_key.strip() or len(subscription_key) > 256:
            raise HarnessError('INVALID_ARGUMENT', 'Rodin subscription_key 无效')
        key = self._get_hyper3d_api_key()
        if not key:
            raise HarnessError('PROVIDER_CONFIGURATION_REQUIRED', 'Rodin API Key 未配置')
        with provider_backend.requests.post('https://api.hyper3d.com/api/v2/status',
                headers={'Authorization': f'Bearer {key}'},
                json={'subscription_key': subscription_key.strip()}, timeout=(5, 20),
                allow_redirects=False) as response:
            response.raise_for_status()
            result = response.json()
        jobs = result.get('jobs') if isinstance(result, dict) else None
        if (not isinstance(jobs, list) or not jobs
                or any(not isinstance(job, dict) or not isinstance(job.get('status'), str)
                       for job in jobs)):
            raise HarnessError('PROVIDER_BAD_RESULT', 'Rodin 状态响应无效')
        return {'status_list': [job['status'] for job in jobs]}

    def resolve_rodin_asset(self, task_uuid=None, request_id=None, **_kwargs):
        """解析短效结果 URL；OAuth 模式由客户端 MCP 返回结果，不进入此路径。"""
        key = self._get_hyper3d_api_key()
        if not key:
            raise HarnessError('PROVIDER_CONFIGURATION_REQUIRED', 'Rodin API Key 未配置')
        mode = self._get_config_value('', 'hyper3d_mode') or 'MAIN_SITE'
        if mode == 'MAIN_SITE':
            if (not isinstance(task_uuid, str)
                    or not re.fullmatch(r'[0-9a-fA-F-]{16,64}', task_uuid)):
                raise HarnessError('INVALID_ARGUMENT', 'Rodin task_uuid 无效')
            with provider_backend.requests.post('https://api.hyper3d.com/api/v2/download',
                    headers={'Authorization': f'Bearer {key}'}, json={'task_uuid': task_uuid},
                    timeout=(5, 30), allow_redirects=False) as response:
                if response.status_code not in {200, 201}:
                    raise HarnessError('PROVIDER_REQUEST_FAILED', 'Rodin 下载列表请求失败')
                payload = response.json()
            candidates = payload.get('list') if isinstance(payload, dict) else None
            item = next((entry for entry in candidates or []
                         if isinstance(entry, dict)
                         and str(entry.get('name', '')).lower().endswith('.glb')
                         and isinstance(entry.get('url'), str)), None)
            if item is None:
                raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', 'Rodin 尚无可下载的 GLB')
            filename, url = item['name'], item['url']
        elif mode == 'FAL_AI':
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', request_id):
                raise HarnessError('INVALID_ARGUMENT', 'fal.ai request_id 无效')
            with provider_backend.requests.get(
                    f'https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}',
                    headers={'Authorization': f'Key {key}'}, timeout=(5, 30),
                    allow_redirects=False) as response:
                response.raise_for_status()
                payload = response.json()
            url = payload.get('model_mesh', {}).get('url') if isinstance(payload, dict) else None
            filename = f'{request_id}.glb'
            if not isinstance(url, str):
                raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', 'fal.ai 尚无可下载的 GLB')
        else:
            raise HarnessError('INVALID_ARGUMENT', '未知 Hyper3D API 平台')
        try:
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                    or parsed.port not in (None, 443)):
                raise ValueError
        except ValueError as exc:
            raise HarnessError('PROVIDER_BAD_RESULT', 'Rodin 返回了不安全的下载地址') from exc
        return {'providerId': 'hyper3d', 'url': url, 'filename': filename}

    def _hunyuan_request(self, action, data, profile):
        secret_id = self._get_config_value('', 'hunyuan3d_secret_id')
        secret_key = self._get_config_value('', 'hunyuan3d_secret_key')
        return invoke_hunyuan_sdk(action, data, profile, secret_id, secret_key)

    def create_hunyuan_job_main_site(self, text_prompt=None, image=None, task_type=None):
        """有界提交；本地参考图必须经过当前授权素材根校验。"""
        if bool(text_prompt) == bool(image):
            raise HarnessError('INVALID_ARGUMENT', '提示词和参考图必须且只能提供一项')
        fields = {}
        if text_prompt:
            if not isinstance(text_prompt, str) or not text_prompt.strip() or len(text_prompt) > 1024:
                raise HarnessError('INVALID_ARGUMENT', '提示词必须为 1–1024 字符')
            fields['Prompt'] = text_prompt
        else:
            if not isinstance(image, str):
                raise HarnessError('INVALID_ARGUMENT', '参考图参数无效')
            parsed = urlparse(image)
            if parsed.scheme in {'http', 'https'}:
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                    raise HarnessError('INVALID_ARGUMENT', '远端参考图必须为不含凭证的 HTTPS 地址')
                fields['ImageUrl'] = image
            else:
                from .harness.path_policy import PathPolicy
                roots = getattr(self, '_approved_asset_roots', ())
                if not roots:
                    raise HarnessError('ASSET_NOT_AUTHORIZED', '参考图需要授权素材目录')
                path = PathPolicy(roots).require_file(image)
                with path.open('rb') as source:
                    raw = source.read(20 * 1024 * 1024 + 1)
                if len(raw) > 20 * 1024 * 1024:
                    raise HarnessError('INVALID_ARGUMENT', '参考图超过 20MB')
                if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff')):
                    raise HarnessError('INVALID_ARGUMENT', '参考图必须为 PNG 或 JPEG')
                fields['ImageBase64'] = base64.b64encode(raw).decode('ascii')
        legacy = bool(self._get_config_value('', 'hunyuan3d_intl_pro'))
        account_region = self._get_config_value('', 'hunyuan3d_account_region') or (
            'INTERNATIONAL' if legacy else 'MAINLAND')
        service_type = self._get_config_value('', 'hunyuan3d_service_type') or (
            'HUNYUAN' if legacy else 'AI3D')
        selected_task = task_type or self._get_config_value('', 'hunyuan3d_task_type') or 'PROFESSIONAL'
        try:
            profile = resolve_request(selected_task, account_region, service_type)
        except ValueError as exc:
            raise HarnessError('INVALID_ARGUMENT', str(exc)) from exc
        if self._get_config_value('', 'hunyuan3d_auth_mode') == 'TOKENHUB_API_KEY':
            model = resolve_tokenhub_model(selected_task)
            tokenhub_fields = {
                {'Prompt': 'prompt', 'ImageUrl': 'image_url', 'ImageBase64': 'image_base64'}[key]: value
                for key, value in fields.items()
            }
            return submit_tokenhub_3d(
                provider_backend.requests, model, tokenhub_fields,
                self._get_config_value('', 'hunyuan3d_tokenhub_api_key'))
        data = {**profile['submit_body'], **fields}
        return self._hunyuan_request(profile['submit_action'], data, profile)

    def poll_hunyuan_job_status_ai(self, job_id, task_type=None):
        if not isinstance(job_id, str) or not re.fullmatch(r'(?:job_)?[A-Za-z0-9_-]{1,128}', job_id):
            raise HarnessError('INVALID_ARGUMENT', '混元任务 ID 无效')
        legacy = bool(self._get_config_value('', 'hunyuan3d_intl_pro'))
        account_region = self._get_config_value('', 'hunyuan3d_account_region') or (
            'INTERNATIONAL' if legacy else 'MAINLAND')
        service_type = self._get_config_value('', 'hunyuan3d_service_type') or (
            'HUNYUAN' if legacy else 'AI3D')
        selected_task = task_type or self._get_config_value('', 'hunyuan3d_task_type') or 'PROFESSIONAL'
        try:
            if self._get_config_value('', 'hunyuan3d_auth_mode') == 'TOKENHUB_API_KEY':
                return query_tokenhub_3d(
                    provider_backend.requests, resolve_tokenhub_model(selected_task),
                    job_id.removeprefix('job_'),
                    self._get_config_value('', 'hunyuan3d_tokenhub_api_key'))
            profile = resolve_request(selected_task, account_region, service_type)
        except ValueError as exc:
            raise HarnessError('INVALID_ARGUMENT', str(exc)) from exc
        return self._hunyuan_request(profile['query_action'], {'JobId': job_id.removeprefix('job_')}, profile)

    def ping(self):
        return {'pong': True}

    def resolve_hunyuan_asset(self, job_id, task_type=None):
        """只解析官方任务结果；下载仍由授权目录守卫执行，不直接导入。"""
        if not isinstance(job_id, str) or not re.fullmatch(r'(?:job_)?[A-Za-z0-9_-]{1,128}', job_id):
            raise HarnessError('INVALID_ARGUMENT', '混元任务 ID 无效')
        if self._get_config_value('', 'hunyuan3d_mode') != 'OFFICIAL_API':
            raise HarnessError('INVALID_ARGUMENT', '本地混元结果暂不支持官方任务引用下载')
        result = self.poll_hunyuan_job_status_ai(job_id=job_id, task_type=task_type)
        response = result.get('Response', {}) if isinstance(result, dict) else {}
        if (not isinstance(response, dict) or response.get('Error') or response.get('ErrorCode')
                or response.get('Status') != 'DONE'):
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '混元任务尚未成功完成或查询失败')
        files = response.get('ResultFile3Ds')
        if not isinstance(files, list):
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '混元任务没有可下载的模型文件')
        candidates = []
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get('Url'), str):
                continue
            try:
                parsed = urlparse(item['Url'])
                host = (parsed.hostname or '').lower()
                trusted = (host.endswith('.tencentcos.cn') or
                           ('.cos.' in host and host.endswith('.myqcloud.com')))
                if (parsed.scheme != 'https' or not trusted or parsed.username or parsed.password
                        or parsed.port not in (None, 443)):
                    continue
            except ValueError:
                continue
            suffix = parsed.path.lower().rsplit('.', 1)[-1]
            kind = str(item.get('Type', '')).upper()
            # OBJ 的官方结果常为含贴图的 ZIP；不把裸 OBJ 当作完整资产。
            if (kind, suffix) not in {('GLB', 'glb'), ('FBX', 'fbx'), ('OBJ', 'zip')}:
                continue
            candidates.append(({'glb': 0, 'fbx': 1, 'zip': 2}[suffix], item['Url'], suffix))
        if not candidates:
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '混元结果无受支持的可信模型下载地址')
        _, url, suffix = min(candidates, key=lambda item: item[0])
        return {'url': url, 'filename': f'hunyuan-{job_id.removeprefix("job_")}.{suffix}'}

    def get_addon_info(self):
        from .harness.version import PRODUCT_NAME, VERSION_TUPLE
        return {'name': PRODUCT_NAME, 'addon_version': list(VERSION_TUPLE),
                'protocol_version': 'codex-blender/v1',
                'capabilities': sorted(COMMANDS),
                'blender_version': provider_backend.bpy.app.version_string}

    def get_sketchfab_model_preview(self, uid):
        """仅内存预览：不导入、不落盘、不把凭证发送给缩略图主机。"""
        if not isinstance(uid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,128}', uid):
            raise HarnessError('INVALID_ARGUMENT', 'Sketchfab 模型 ID 无效')
        with provider_backend.requests.get(f'https://api.sketchfab.com/v3/models/{uid}',
                headers=self._sketchfab_headers(),
                timeout=(5, 20), allow_redirects=False) as response:
            if response.status_code != 200:
                raise HarnessError('PROVIDER_REQUEST_FAILED', '无法读取 Sketchfab 模型信息')
            data = response.json()
        thumbnails = data.get('thumbnails', {}).get('images', [])
        if not thumbnails:
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '该模型没有缩略图')
        thumbnail = next((item for item in thumbnails if 400 <= item.get('width', 0) <= 800), thumbnails[0])
        url = thumbnail.get('url', '')
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or parsed.username or parsed.password or
                not (host == 'sketchfab.com' or host.endswith('.sketchfab.com'))):
            raise HarnessError('PROVIDER_BAD_RESULT', '缩略图地址不在允许的供应商域名内')
        payload = bytearray()
        with provider_backend.requests.get(url, stream=True, timeout=(5, 20), allow_redirects=False) as response:
            if response.status_code != 200:
                raise HarnessError('PROVIDER_REQUEST_FAILED', '无法读取模型缩略图')
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 5 * 1024 * 1024:
                    raise HarnessError('PROVIDER_BAD_RESULT', '缩略图超过 5MB 上限')
        image_format = 'png' if payload.startswith(b'\x89PNG\r\n\x1a\n') else 'jpeg' if payload.startswith(b'\xff\xd8\xff') else None
        if image_format is None:
            raise HarnessError('PROVIDER_BAD_RESULT', '缩略图不是 PNG 或 JPEG')
        return {'success': True, 'image_data': base64.b64encode(payload).decode('ascii'),
                'format': image_format, 'model_name': data.get('name', 'Unknown'),
                'author': data.get('user', {}).get('username', 'Unknown'), 'uid': uid,
                'thumbnail_width': thumbnail.get('width'), 'thumbnail_height': thumbnail.get('height')}

    def get_polyhaven_categories(self, asset_type):
        if asset_type not in {'hdris', 'textures', 'models', 'all'}:
            raise HarnessError('INVALID_ARGUMENT', '素材类型无效')
        response = provider_backend.requests.get(
            f'https://api.polyhaven.com/categories/{asset_type}',
            headers=provider_backend.REQ_HEADERS, timeout=(5, 20))
        response.raise_for_status()
        return {'categories': response.json()}

    def search_polyhaven_assets(self, asset_type=None, categories=None):
        if asset_type not in {None, 'all', 'hdris', 'textures', 'models'}:
            raise HarnessError('INVALID_ARGUMENT', '素材类型无效')
        params = {}
        if asset_type and asset_type != 'all':
            params['type'] = asset_type
        if categories:
            params['categories'] = categories
        response = provider_backend.requests.get('https://api.polyhaven.com/assets',
            params=params, headers=provider_backend.REQ_HEADERS, timeout=(5, 20))
        response.raise_for_status()
        assets = response.json()
        limited = dict(list(assets.items())[:20])
        return {'assets': limited, 'total_count': len(assets), 'returned_count': len(limited)}


def _require_not_cancelled(provider_id, params):
    from .harness.provider_tasks import get_provider_task_registry
    keys = ('subscription_key', 'request_id', 'job_id', 'JobId', 'task_uuid', 'uuid', 'id')
    for key in keys:
        task_id = params.get(key)
        if isinstance(task_id, (str, int)) and str(task_id).strip():
            task = get_provider_task_registry().status(provider_id, str(task_id))
            if task is None:
                task = get_provider_task_registry().find_by_remote(provider_id, str(task_id))
            if task and task.get('cancelRequested'):
                raise HarnessError('PROVIDER_TASK_CANCELLED', '任务已在本地终止，不再查询或下载；远端可能仍在运行')


def _submission_reference(result):
    """只保留后续查询/下载所需的短标识，不公开 URL、凭证或供应商原始响应。"""
    from .harness.provider_execution import find_value
    keys = ('subscription_key', 'request_id', 'task_uuid', 'JobId', 'job_id', 'uuid', 'id')
    reference = {}
    for key in keys:
        value = find_value(result, (key,))
        if isinstance(value, (str, int)) and str(value).strip():
            reference[key] = str(value).strip()
    return reference


def _task_reference(result, command, settings):
    reference = _submission_reference(result)
    if command == 'create_hunyuan_job':
        reference['task_type'] = settings['hunyuan3d_task_type']
    return reference


def _capture_official_submission(command, preferences, approved_asset_roots, params=None):
    """在 Blender 主线程捕获普通值；返回的回调禁止再读取 bpy。"""
    settings = {
        'hyper3d_api_key': str(getattr(preferences, 'hyper3d_api_key', '')),
        'hyper3d_mode': str(getattr(preferences, 'hyper3d_mode', 'MAIN_SITE')),
        **_hunyuan_settings(preferences, task_type=(params or {}).get('task_type')),
    }
    engine = ProviderEngine()
    engine._approved_asset_roots = tuple(approved_asset_roots)
    engine._get_config_value = lambda _scene, pref_attr=None, _env=None: settings.get(pref_attr, '')
    engine._get_hyper3d_api_key = lambda: settings['hyper3d_api_key']
    if command == 'create_rodin_job':
        method = (engine.create_rodin_job_main_site if settings['hyper3d_mode'] == 'MAIN_SITE'
                  else engine.create_rodin_job_fal_ai if settings['hyper3d_mode'] == 'FAL_AI'
                  else None)
    elif command == 'create_hunyuan_job':
        method = engine.create_hunyuan_job_main_site
    else:
        method = None
    if method is None:
        raise HarnessError('INVALID_ARGUMENT', '未知供应商提交模式')
    return method, settings


def _capture_network_query(command, params, preferences):
    """复制查询配置和参数；返回的回调禁止读取 Blender 上下文。"""
    settings = {
        **_sketchfab_settings(preferences),
        'hyper3d_api_key': str(getattr(preferences, 'hyper3d_api_key', '')),
        'hyper3d_mode': str(getattr(preferences, 'hyper3d_mode', 'MAIN_SITE')),
        **_hunyuan_settings(preferences, task_type=params.get('task_type')),
    }
    engine = ProviderEngine()
    engine._get_config_value = lambda _scene, pref_attr=None, _env=None: settings.get(pref_attr, '')
    engine._get_hyper3d_api_key = lambda: settings['hyper3d_api_key']
    if command == 'poll_rodin_job_status':
        if settings['hyper3d_mode'] == 'MAIN_SITE':
            method = engine.poll_rodin_job_status_main_site
        elif settings['hyper3d_mode'] == 'FAL_AI':
            method = engine.poll_rodin_job_status_fal_ai
        else:
            raise HarnessError('INVALID_ARGUMENT', '未知 Hyper3D API 平台')
    elif command == 'poll_hunyuan_job_status':
        method = engine.poll_hunyuan_job_status_ai
    else:
        method = getattr(engine, command)
    copied = json.loads(json.dumps(params, ensure_ascii=False))
    return lambda: method(**copied)


def execute(arguments, *, approved_asset_roots=()):
    command = arguments['action']
    expected = COMMANDS.get(command)
    if expected != (arguments['providerId'], arguments['risk']):
        raise HarnessError('INVALID_ARGUMENT', '供应商操作或风险等级不匹配')
    if not isinstance(arguments.get('params'), dict):
        raise HarnessError('INVALID_ARGUMENT', 'params 必须是对象')
    if command in {'poll_rodin_job_status', 'poll_hunyuan_job_status'}:
        _require_not_cancelled(arguments['providerId'], arguments['params'])
    preferences = provider_backend.bpy.context.preferences.addons['partme_blender_mcp'].preferences
    scene = provider_backend.bpy.context.scene
    if (arguments['providerId'] == 'hyper3d'
            and getattr(preferences, 'hyper3d_auth_mode', 'API_KEY') == 'MCP_OAUTH'):
        raise HarnessError('HYPER3D_CLIENT_MCP_REQUIRED',
            'OAuth 模式由当前客户端的 hyper3d MCP 执行；生成结果再通过 PartMe 授权目录和事务导入')
    global _local_generation, _submitter, _query_runner
    if (command == 'poll_hunyuan_job_status'
            and str(arguments['params'].get('job_id', '')).startswith('local_')):
        if _local_generation is None:
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '本地任务不存在或进程已重启')
        return _local_generation.status(arguments['params']['job_id'])
    if (command in {'create_hunyuan_job', 'poll_hunyuan_job_status'}
            and preferences.hunyuan3d_mode == 'LOCAL_API'):
        if command != 'create_hunyuan_job':
            raise HarnessError('INVALID_ARGUMENT', '本地查询需要本次进程生成的 local_ 任务 ID')
        if not approved_asset_roots:
            raise HarnessError('ASSET_NOT_AUTHORIZED', '本地生成需要授权素材目录')
        from .harness.local_generation import LocalGeneration
        from .harness.provider_tasks import get_provider_task_registry
        if _local_generation is None:
            _local_generation = LocalGeneration(get_provider_task_registry(), provider_backend.requests)
        options = {name: getattr(scene, 'blendermcp_hunyuan3d_' + name) for name in (
            'octree_resolution', 'num_inference_steps', 'guidance_scale', 'texture')}
        return _local_generation.submit(str(preferences.hunyuan3d_api_url), arguments['params'],
                                         options, approved_asset_roots)
    if command in {'create_rodin_job', 'create_hunyuan_job'}:
        from .harness.provider_execution import find_value
        from .harness.provider_submission import ProviderSubmitter
        from .harness.provider_tasks import get_provider_task_registry
        tasks = get_provider_task_registry()
        params = dict(arguments['params'])
        method, settings = _capture_official_submission(
            command, preferences, approved_asset_roots, params)
        preferred_keys = (('subscription_key',) if command == 'create_rodin_job'
                          and settings['hyper3d_mode'] == 'MAIN_SITE'
                          else ('request_id',) if command == 'create_rodin_job'
                          else ('JobId', 'job_id'))
        if _submitter is None:
            _submitter = ProviderSubmitter(tasks)

        def submitted(local_id, remote_id, result):
            current = tasks.update({
                'operation': 'update', 'providerId': arguments['providerId'],
                'taskId': local_id, 'state': 'generating',
                'stage': '已提交 · 等待生成', 'statusText': '已提交 · 等待生成',
                'remoteTaskId': remote_id,
                'resultReference': _task_reference(result, command, settings),
                'cancelSupported': False,
            })
            try:
                _start_generation_poll(command, current, remote_task_id=remote_id, settings=settings)
            except Exception:
                # 供应商已接收时绝不能把调度失败伪装成提交失败，避免客户端重试计费。
                tasks.update({
                    'operation': 'update', 'providerId': current['providerId'],
                    'taskId': current['taskId'], 'state': 'generating',
                    'statusText': '已提交 · 自动查询未启动',
                    'message': '请通过任务查询检查结果；不要重复提交生成',
                    'remoteTaskId': remote_id,
                    'resultReference': _task_reference(result, command, settings),
                    'cancelSupported': False,
                })

        try:
            task = _submitter.submit(
                arguments['providerId'], lambda: method(**params),
                remote_id=lambda result: find_value(result, preferred_keys),
                on_submitted=submitted,
            )
        except RuntimeError as exc:
            raise HarnessError('PROVIDER_BUSY', '供应商提交队列已满，请稍后再试') from exc
        return {'accepted': True, 'submissionId': task['taskId'], '_partmeTask': task}
    if command in NETWORK_QUERY_COMMANDS:
        from .harness.provider_queries import ProviderQueryRunner
        from .harness.provider_tasks import get_provider_task_registry
        callback = _capture_network_query(command, arguments['params'], preferences)
        if _query_runner is None:
            _query_runner = ProviderQueryRunner(get_provider_task_registry())
        try:
            task = _query_runner.submit(arguments['providerId'], callback)
        except RuntimeError as exc:
            raise HarnessError('PROVIDER_BUSY', '供应商查询队列已满，请稍后再试') from exc
        return {'accepted': True, 'queryId': task['taskId'], '_partmeTask': task}
    # 仅同步无凭证的平台选项；不复制 Key 到 .blend。
    scene.blendermcp_hyper3d_mode = preferences.hyper3d_mode
    scene.blendermcp_hunyuan3d_mode = preferences.hunyuan3d_mode
    selection = _hunyuan_settings(preferences)
    scene.blendermcp_hunyuan3d_account_region = selection['hunyuan3d_account_region']
    scene.blendermcp_hunyuan3d_service_type = selection['hunyuan3d_service_type']
    scene.blendermcp_hunyuan3d_task_type = selection['hunyuan3d_task_type']
    try:
        engine = ProviderEngine()
        engine._approved_asset_roots = tuple(approved_asset_roots)
        result = getattr(engine, command)(**arguments['params'])
    except provider_backend.requests.exceptions.RequestException as exc:
        raise HarnessError('PROVIDER_REQUEST_FAILED', '供应商网络请求失败或超时') from exc
    if isinstance(result, dict) and result.get('error'):
        # 上游异常可能包含敏感 URL，不直接回显到公开回执。
        raise HarnessError('PROVIDER_REQUEST_FAILED', '供应商请求失败，请检查凭证、参数及网络')
    from .harness.provider_execution import record_generation_result
    task = record_generation_result(command, arguments['params'], result)
    if task is not None and command.startswith('create_') and task['active']:
        try:
            _start_generation_poll(command, task)
        except Exception:
            # 已经提交的付费任务不能因调度失败返回提交失败，避免客户端重复付费。
            from .harness.provider_tasks import get_provider_task_registry
            task = get_provider_task_registry().update({'operation': 'update',
                'providerId': task['providerId'], 'taskId': task['taskId'], 'state': 'generating',
                'statusText': '已提交 · 自动查询未启动',
                'message': '请通过任务查询检查结果；不要重复提交生成'})
    return {**result, '_partmeTask': task} if task is not None else result


def query_result(provider_id, task_id):
    """读取后台查询结果；不会重新发起网络请求。"""
    if _query_runner is None:
        raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '查询任务不存在或进程已重启')
    try:
        return _query_runner.result(provider_id, task_id)
    except ValueError as exc:
        raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '查询任务不存在或结果不可用') from exc


def register():
    bpy = provider_backend.bpy
    if not bpy.app.timers.is_registered(_redraw_provider_tasks):
        bpy.app.timers.register(_redraw_provider_tasks, first_interval=0.5, persistent=True)
    bpy.types.Scene.blendermcp_hyper3d_mode = bpy.props.StringProperty(default='MAIN_SITE', options={'SKIP_SAVE'})
    bpy.types.Scene.blendermcp_hunyuan3d_mode = bpy.props.StringProperty(default='OFFICIAL_API', options={'SKIP_SAVE'})
    bpy.types.Scene.blendermcp_hunyuan3d_account_region = bpy.props.StringProperty(default='MAINLAND', options={'SKIP_SAVE'})
    bpy.types.Scene.blendermcp_hunyuan3d_service_type = bpy.props.StringProperty(default='AI3D', options={'SKIP_SAVE'})
    bpy.types.Scene.blendermcp_hunyuan3d_task_type = bpy.props.StringProperty(default='PROFESSIONAL', options={'SKIP_SAVE'})
    bpy.types.Scene.blendermcp_hunyuan3d_octree_resolution = bpy.props.IntProperty(default=256)
    bpy.types.Scene.blendermcp_hunyuan3d_num_inference_steps = bpy.props.IntProperty(default=20)
    bpy.types.Scene.blendermcp_hunyuan3d_guidance_scale = bpy.props.FloatProperty(default=5.5)
    bpy.types.Scene.blendermcp_hunyuan3d_texture = bpy.props.BoolProperty(default=False)


def capture_asset_resolver(provider_id, params):
    """在 Blender 主线程快照下载配置，返回不再访问 bpy 的解析回调。"""
    resolvers = {'sketchfab': 'resolve_sketchfab_download', 'hyper3d': 'resolve_rodin_asset',
                 'hunyuan3d': 'resolve_hunyuan_asset'}
    if provider_id not in resolvers or not isinstance(params, dict):
        raise HarnessError('INVALID_ARGUMENT', '供应商不支持该下载引用')
    _require_not_cancelled(provider_id, params)
    if provider_id == 'hunyuan3d' and str(params.get('job_id', '')).startswith('local_'):
        if set(params) != {'job_id'} or _local_generation is None:
            raise HarnessError('INVALID_ARGUMENT', '本地任务引用无效')
        result = _local_generation.status(params['job_id'])
        if result['Status'] != 'DONE' or not result.get('path'):
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '本地模型尚未完成暂存')
        path = result['path']
        return lambda: {'path': path}
    preferences = provider_backend.bpy.context.preferences.addons['partme_blender_mcp'].preferences
    if (provider_id == 'hyper3d'
            and getattr(preferences, 'hyper3d_auth_mode', 'API_KEY') == 'MCP_OAUTH'):
        raise HarnessError('HYPER3D_CLIENT_MCP_REQUIRED',
            'OAuth 模式的结果链接由客户端 hyper3d MCP 提供，请使用受控生成结果导入')
    settings = {
        **_sketchfab_settings(preferences),
        'hyper3d_api_key': str(getattr(preferences, 'hyper3d_api_key', '')),
        'hyper3d_mode': str(getattr(preferences, 'hyper3d_mode', 'MAIN_SITE')),
        'hunyuan3d_mode': str(getattr(preferences, 'hunyuan3d_mode', 'OFFICIAL_API')),
        **_hunyuan_settings(preferences, task_type=params.get('task_type')),
    }
    copied = json.loads(json.dumps(params, ensure_ascii=False))
    engine = ProviderEngine()
    engine._get_config_value = lambda _scene, pref_attr=None, _env=None: settings.get(pref_attr, '')
    engine._get_hyper3d_api_key = lambda: settings['hyper3d_api_key']
    method = getattr(engine, resolvers[provider_id])

    def resolve():
        try:
            result = method(**copied)
        except TypeError as exc:
            raise HarnessError('INVALID_ARGUMENT', '供应商下载引用参数无效') from exc
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError('PROVIDER_REQUEST_FAILED', '无法解析供应商下载结果') from exc
        if not isinstance(result, dict) or result.get('error') or not isinstance(result.get('url'), str):
            raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '供应商下载结果尚不可用')
        return {'url': result['url'], 'filename': result.get('filename')}
    return resolve


def resolve_asset(provider_id, params):
    """兼容同步调用；公开 MCP 路径使用 capture_asset_resolver 后台执行。"""
    return capture_asset_resolver(provider_id, params)()


def unregister():
    global _poller, _last_task_snapshot, _local_generation, _submitter, _query_runner
    if _submitter is not None:
        _submitter.close()
        _submitter = None
    if _local_generation is not None:
        _local_generation.close()
        _local_generation = None
    if _poller is not None:
        _poller.close()
        _poller = None
    if _query_runner is not None:
        _query_runner.close()
        _query_runner = None
    _last_task_snapshot = None
    if provider_backend.bpy.app.timers.is_registered(_redraw_provider_tasks):
        provider_backend.bpy.app.timers.unregister(_redraw_provider_tasks)
    for name in ('hyper3d_mode', 'hunyuan3d_mode', 'hunyuan3d_account_region',
                 'hunyuan3d_service_type', 'hunyuan3d_task_type',
                 'hunyuan3d_octree_resolution', 'hunyuan3d_num_inference_steps',
                 'hunyuan3d_guidance_scale', 'hunyuan3d_texture'):
        attr = 'blendermcp_' + name
        if hasattr(provider_backend.bpy.types.Scene, attr):
            delattr(provider_backend.bpy.types.Scene, attr)
