"""TokenHub CLI 授权适配器契约。"""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


SOURCE = Path(__file__).parents[1] / "addon/partme_blender_mcp/tokenhub_auth.py"


class TokenHubAuthTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("partme_tokenhub_auth_test", SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_status_uses_documented_cli_and_exit_code(self):
        runner = Mock(return_value=SimpleNamespace(
            returncode=0, stdout='{"Profile":"studio","Site":"cn","SecretKey":"masked"}', stderr=""))
        status = self.module.inspect_status("/usr/local/bin/thcli", profile="studio", site="cn", runner=runner)
        self.assertEqual(status, {"state": "authorized", "statusText": "TokenHub OAuth 已授权",
                                  "profile": "studio", "site": "cn"})
        self.assertEqual(runner.call_args.args[0], [
            "/usr/local/bin/thcli", "--profile", "studio", "--site", "cn",
            "--json", "auth", "status",
        ])
        self.assertNotIn("SecretKey", repr(status))

    def test_nonzero_status_never_leaks_cli_output(self):
        runner = Mock(return_value=SimpleNamespace(
            returncode=1, stdout="access-token-secret", stderr="refresh-token-secret"))
        status = self.module.inspect_status("/bin/thcli", runner=runner)
        self.assertEqual(status["state"], "not_authorized")
        self.assertNotIn("secret", repr(status).lower())

    def test_missing_cli_is_a_distinct_state(self):
        with patch.object(self.module.shutil, "which", return_value=None):
            self.assertIsNone(self.module.find_thcli())
        self.assertEqual(self.module.inspect_status(None)["state"], "missing")

    def test_login_uses_no_shell_and_private_log(self):
        process = SimpleNamespace(poll=lambda: None)
        popen = Mock(return_value=process)
        with tempfile.TemporaryDirectory() as directory:
            result, log_path = self.module.start_authorization(
                "/bin/thcli", profile="studio", site="cn", directory=Path(directory), popen=popen)
            self.assertIs(result, process)
            self.assertEqual(popen.call_args.args[0], [
                "/bin/thcli", "--profile", "studio", "--site", "cn", "auth", "login",
            ])
            self.assertFalse(popen.call_args.kwargs["shell"])
            if os.name == "posix":
                self.assertEqual(Path(log_path).stat().st_mode & 0o777, 0o600)
            else:
                self.assertTrue(Path(log_path).is_file())
            self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
