"""本地混元同步 HTTP 接口的后台任务适配；只暂存 GLB，不操作 Blender。"""
import base64
import os
import struct
import tempfile
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

from .errors import HarnessError
from .path_policy import PathPolicy


class LocalGeneration:
    def __init__(self, registry, http, *, max_workers=4, max_bytes=500 * 1024 * 1024):
        self.registry, self.http = registry, http
        self.max_workers, self.max_bytes = max_workers, max_bytes
        self._jobs = {}
        self._lock = threading.RLock()
        self._closed = False

    def submit(self, endpoint, params, options, roots):
        if not roots:
            raise HarnessError('ASSET_NOT_AUTHORIZED', '本地生成需要授权素材目录')
        root = Path(roots[0]).resolve()
        if not root.is_dir():
            raise HarnessError('ASSET_NOT_AUTHORIZED', '授权素材目录不存在')
        if not isinstance(endpoint, str):
            raise HarnessError('INVALID_ARGUMENT', '本地混元服务地址无效')
        parsed = urlparse(endpoint)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise HarnessError('INVALID_ARGUMENT', '本地混元服务地址无效')
        if set(params) - {'text_prompt', 'image'}:
            raise HarnessError('INVALID_ARGUMENT', '本地生成参数无效')
        prompt, image = params.get('text_prompt'), params.get('image')
        if prompt is not None and (not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1024):
            raise HarnessError('INVALID_ARGUMENT', '提示词必须为 1–1024 字符')
        if not prompt and not image:
            raise HarnessError('INVALID_ARGUMENT', '需要提示词或授权目录中的参考图片')
        payload = dict(options)
        if prompt:
            payload['text'] = prompt
        if image:
            if not isinstance(image, str):
                raise HarnessError('INVALID_ARGUMENT', '图片必须为授权素材文件路径')
            source = PathPolicy(roots).require_file(image)
            if source.stat().st_size > 20 * 1024 * 1024:
                raise HarnessError('INVALID_ARGUMENT', '参考图片超过 20MB')
            data = source.read_bytes()
            if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')):
                raise HarnessError('INVALID_ARGUMENT', '参考图片必须为 PNG 或 JPEG')
            payload['image'] = base64.b64encode(data).decode('ascii')
        with self._lock:
            if self._closed or sum(job['thread'].is_alive() for job in self._jobs.values()) >= self.max_workers:
                raise HarnessError('PROVIDER_UNAVAILABLE', '本地生成队列已满或已停止')
            # 保留当前任务及最近结果，避免运行期无界增长。
            for key in list(self._jobs):
                if len(self._jobs) < 128:
                    break
                if not self._jobs[key]['thread'].is_alive():
                    self._jobs.pop(key)
            task_id = 'local_' + uuid.uuid4().hex
            stop = threading.Event()
            worker = threading.Thread(target=self._run, args=(task_id, endpoint.rstrip('/') + '/generate',
                payload, root, stop), name='PartMe-local-generation', daemon=True)
            self._jobs[task_id] = {'thread': worker, 'stop': stop, 'path': None}
            task = self.registry.update({'operation': 'start', 'providerId': 'hunyuan3d',
                'taskId': task_id, 'state': 'submitting', 'statusText': '本地生成中',
                'message': '结果仅暂存到授权目录；导入需要独立事务'})
            worker.start()
        return {'JobId': task_id, 'Status': 'RUN', '_partmeTask': task}

    def _active(self, task_id, stop):
        task = self.registry.status('hunyuan3d', task_id)
        return not stop.is_set() and task is not None and task['active']

    def _run(self, task_id, url, payload, root, stop):
        partial = None
        directory = None
        try:
            if not self._active(task_id, stop):
                return
            with self.http.post(url, json=payload, stream=True, timeout=(5, 120), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError('generation response failed')
                if not self._active(task_id, stop):
                    return
                directory = Path(tempfile.mkdtemp(prefix='partme-hunyuan-', dir=root))
                partial = directory / 'model.glb.part'
                count = 0
                with partial.open('xb') as sink:
                    for chunk in response.iter_content(65536):
                        if not self._active(task_id, stop):
                            return
                        count += len(chunk)
                        if count > self.max_bytes:
                            raise ValueError('model too large')
                        sink.write(chunk)
                with partial.open('rb') as source:
                    header = source.read(12)
                if len(header) != 12 or struct.unpack('<4sII', header) != (b'glTF', 2, count):
                    raise ValueError('invalid GLB response')
                if not self._active(task_id, stop):
                    return
                target = directory / 'model.glb'
                os.replace(partial, target)
                with self._lock:
                    self._jobs[task_id]['path'] = str(target)
                self.registry.update({'operation': 'finish', 'providerId': 'hunyuan3d', 'taskId': task_id,
                    'state': 'completed', 'progress': 1, 'statusText': '已生成并暂存',
                    'message': '未导入场景；请使用授权路径执行事务导入'})
        except Exception:
            if self._active(task_id, stop):
                self.registry.update({'operation': 'finish', 'providerId': 'hunyuan3d', 'taskId': task_id,
                    'state': 'failed', 'statusText': '本地生成失败',
                    'message': '请检查本地服务、网络或返回文件；远端可能仍在运行，不要自动重复提交'})
        finally:
            if partial is not None:
                partial.unlink(missing_ok=True)
            if directory is not None and not any(directory.iterdir()):
                directory.rmdir()

    def status(self, task_id):
        with self._lock:
            job = self._jobs.get(task_id)
            task = self.registry.status('hunyuan3d', task_id)
            if job is None or task is None:
                raise HarnessError('PROVIDER_RESULT_UNAVAILABLE', '本地任务不存在或进程已重启')
            status = {'completed': 'DONE', 'failed': 'FAIL', 'cancelled': 'CANCELLED'}.get(task['state'], 'RUN')
            return {'JobId': task_id, 'Status': status,
                    'path': job['path'] if status == 'DONE' else None, '_partmeTask': task}

    def close(self):
        with self._lock:
            self._closed = True
            for task_id, job in self._jobs.items():
                job['stop'].set()
                if self.registry.status('hunyuan3d', task_id) is not None:
                    self.registry.request_cancel('hunyuan3d', task_id)
