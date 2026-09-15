"""Unix socket path budget: macOS caps sun_path at 104 bytes.

The per-user temp directory already consumes about half of that budget, so a readable
session id cannot be used verbatim as the socket file name: doing so made the Add-on fail
to start a session with a bare ``OSError: AF_UNIX path too long``.
"""

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from partme_blender_mcp.harness.transport import (  # noqa: E402
    SOCKET_PATH_LIMIT,
    choose_endpoint,
    unix_socket_path,
)


class SocketPathTests(unittest.TestCase):
    def test_default_runtime_directory_fits_the_budget(self):
        default = Path(tempfile.gettempdir()) / "partme-blender"
        endpoint = choose_endpoint("darwin", session_id="partme-" + "a" * 16, runtime_dir=str(default))
        self.assertEqual(endpoint.kind, "unix")
        self.assertLessEqual(len(endpoint.address.encode("utf-8")), SOCKET_PATH_LIMIT)

    def test_long_session_ids_do_not_lengthen_the_socket_path(self):
        short = unix_socket_path("/tmp/run", "partme-0123456789abcdef")
        long = unix_socket_path("/tmp/run", "partme-" + "0123456789abcdef" * 6)
        self.assertEqual(len(str(short)), len(str(long)))
        self.assertLessEqual(len(str(long)), SOCKET_PATH_LIMIT - len("/tmp/run"))

    def test_distinct_sessions_get_distinct_sockets(self):
        first = unix_socket_path("/tmp/run", "session-a")
        second = unix_socket_path("/tmp/run", "session-b")
        self.assertNotEqual(first, second)
        # Deterministic, so a reconnecting client resolves the same socket.
        self.assertEqual(first, unix_socket_path("/tmp/run", "session-a"))

    def test_over_long_directory_reports_the_setting_to_change(self):
        with self.assertRaises(ValueError) as context:
            choose_endpoint("darwin", session_id="s", runtime_dir="/tmp/" + "d" * 120)
        message = str(context.exception)
        self.assertIn("PARTME_BLENDER_RUNTIME_DIR", message)
        self.assertIn("too long", message)

    def test_other_platforms_are_unaffected(self):
        self.assertEqual(choose_endpoint("win32", session_id="s-1", runtime_dir="/tmp").kind, "pipe")
        self.assertEqual(choose_endpoint("linux", session_id="s-1", runtime_dir="/tmp").kind, "tcp")


if __name__ == "__main__":
    unittest.main()
