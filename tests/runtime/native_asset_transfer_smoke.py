"""真实 Blender 中验证素材下载后台化与本地终止；不访问公网。"""
# ruff: noqa: E402 -- Blender 必须先启用 Add-on，才能导入其运行时模块。

import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

import bpy


config = os.environ.get('BLENDER_USER_CONFIG')
assert config and Path(config).is_dir()
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == Path(config).resolve()
asset_root = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
asset_root.mkdir(parents=True, exist_ok=True)

bpy.ops.preferences.addon_enable(module='partme_blender_mcp')
from partme_blender_mcp.harness.commands.asset import AssetCommands
from partme_blender_mcp.harness.path_policy import PathPolicy
from partme_blender_mcp.harness.provider_tasks import get_provider_task_registry


class Response:
    def __init__(self, entered, release):
        self.entered = entered
        self.release = release
        self.headers = {'Content-Length': '10'}
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        self.reads += 1
        if self.reads == 1:
            self.entered.set()
            return b'first'
        self.release.wait(3)
        return b'second' if self.reads == 2 else b''


commands = AssetCommands(bpy, asset_policy=PathPolicy([asset_root]))
tasks = get_provider_task_registry()
entered, release = threading.Event(), threading.Event()
original = urllib.request.urlopen
worker_ids = []


def urlopen(*_args, **_kwargs):
    worker_ids.append(threading.get_ident())
    return Response(entered, release)


urllib.request.urlopen = urlopen
try:
    accepted = commands.fetch_url_async({
        'url': 'https://dl.polyhaven.org/file/cancel.glb',
    })['result']
    task_id = accepted['operationId']
    assert accepted['task']['state'] == 'downloading'
    assert entered.wait(1)
    bpy.context.scene.frame_set(19)
    assert bpy.context.scene.frame_current == 19
    tasks.request_cancel('polyhaven', task_id)
    release.set()
    commands.transfers.join('polyhaven', task_id, timeout=3)
    assert commands.operation_result({
        'providerId': 'polyhaven', 'taskId': task_id,
    })['result']['state'] == 'cancelled'
    assert not (asset_root / 'polyhaven' / 'cancel.glb.part').exists()
    assert not (asset_root / 'polyhaven' / 'cancel.glb').exists()
    assert worker_ids and all(value != threading.get_ident() for value in worker_ids)
    print('NATIVE_ASSET_TRANSFER=' + json.dumps({
        'passed': True, 'mainThreadResponsive': True,
        'cancelledWithoutArtifact': True, 'networkCalls': 0,
    }))
finally:
    release.set()
    urllib.request.urlopen = original
    commands.close()
    bpy.ops.preferences.addon_disable(module='partme_blender_mcp')
