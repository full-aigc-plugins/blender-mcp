"""Sketchfab OAuth 协议与凭证边界。"""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "sketchfab_auth_fixture",
    Path(__file__).parents[1] / "addon/partme_blender_mcp/sketchfab_auth.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
authorization_url = module.authorization_url
apply_token_response = module.apply_token_response
refresh_access_token = module.refresh_access_token
validate_redirect_uri = module.validate_redirect_uri


class SketchfabAuthTests(unittest.TestCase):
    def test_authorization_url_contains_registered_redirect_and_state(self):
        url = authorization_url("client-id", "http://127.0.0.1:9879/oauth/sketchfab/callback", "state-value")
        self.assertIn("client_id=client-id", url)
        self.assertIn("response_type=code", url)
        self.assertIn("state=state-value", url)
        self.assertIn("redirect_uri=http%3A%2F%2F127.0.0.1%3A9879%2Foauth%2Fsketchfab%2Fcallback", url)

    def test_redirect_must_be_loopback_http_with_explicit_port(self):
        self.assertEqual(validate_redirect_uri("http://127.0.0.1:9879/callback")[1], 9879)
        for value in ("https://example.com/callback", "http://0.0.0.0:9879/callback", "http://localhost/callback"):
            with self.assertRaises(ValueError):
                validate_redirect_uri(value)

    def test_token_response_is_applied_without_echoing_secret(self):
        preferences = SimpleNamespace(sketchfab_access_token="", sketchfab_refresh_token="",
                                      sketchfab_token_expires_at=0.0, sketchfab_oauth_status="NOT_AUTHORIZED")
        apply_token_response(preferences, {
            "access_token": "access-secret", "refresh_token": "refresh-secret",
            "expires_in": 3600, "token_type": "Bearer",
        }, now=1000)
        self.assertEqual(preferences.sketchfab_access_token, "access-secret")
        self.assertEqual(preferences.sketchfab_refresh_token, "refresh-secret")
        self.assertEqual(preferences.sketchfab_token_expires_at, 4600)
        self.assertEqual(preferences.sketchfab_oauth_status, "AUTHORIZED")

    def test_refresh_uses_refresh_token_grant(self):
        preferences = SimpleNamespace(
            sketchfab_client_id="client", sketchfab_client_secret="secret",
            sketchfab_refresh_token="refresh", sketchfab_access_token="old",
            sketchfab_token_expires_at=1.0, sketchfab_oauth_status="AUTHORIZED")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"access_token": "new", "expires_in": 7200, "token_type": "Bearer"}
        http = Mock(post=Mock(return_value=response))
        token = refresh_access_token(preferences, http=http, now=1000)
        self.assertEqual(token, "new")
        kwargs = http.post.call_args.kwargs
        self.assertEqual(kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(kwargs["data"]["refresh_token"], "refresh")


if __name__ == "__main__":
    unittest.main()
