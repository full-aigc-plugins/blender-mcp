"""RNA 枚举集合必须返回 JSON 可编码的默认值，不读取单选 default。"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


class RnaFlagTests(unittest.TestCase):
    def test_flag_default_does_not_read_single_enum_default(self):
        path = Path(__file__).parents[1] / 'addon/partme_blender_mcp/provider_engine.py'
        cls = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body
                   if isinstance(n, ast.ClassDef) and n.name == 'ProviderEngine')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == '_describe_property')
        method.decorator_list = []
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
        class Flag:
            type = 'ENUM'
            is_enum_flag = True
            identifier = name = 'refresh'
            description = ''
            enum_items = [SimpleNamespace(identifier='DATA')]
            default_flag = set()
            @property
            def default(self):
                raise AssertionError('single-choice default must not be read')
        result = namespace['_describe_property'](Flag())
        self.assertEqual(result['default'], [])
        json.dumps(result)
