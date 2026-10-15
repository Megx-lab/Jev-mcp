"""Regression tests: unauthorized requests never reach the credit-using app."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx

SPEC = importlib.util.spec_from_file_location("jev_server_under_test", Path(__file__).parents[1] / "server.py")
server = importlib.util.module_from_spec(SPEC)
with patch.dict(os.environ, {"SERVER_PASSWORD": "test-password-only"}):
    SPEC.loader.exec_module(server)


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.forwarded = []

        async def downstream(scope, receive, send):
            self.forwarded.append(scope)
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.protect(downstream)),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_missing_or_wrong_credentials_never_reach_app(self):
        for method in ("GET", "POST", "DELETE", "OPTIONS"):
            for path in ("/mcp", "/mcp/", "/wrong/mcp", "/test-password-onlyx/mcp"):
                for auth in (None, "Bearer wrong", "Basic dGVzdA==", "Bearer", "Bearer wrong extra"):
                    with self.subTest(method=method, path=path, auth=auth):
                        headers = {} if auth is None else {"Authorization": auth}
                        response = await self.client.request(method, path, headers=headers)
                        self.assertEqual(response.status_code, 401)
                        self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.assertEqual(self.forwarded, [])

    async def test_secret_url_rewrites_path(self):
        response = await self.client.post("/test-password-only/mcp?example=1")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.forwarded[0]["path"], "/mcp")
        self.assertEqual(self.forwarded[0]["raw_path"], b"/mcp")
        self.assertEqual(self.forwarded[0]["query_string"], b"example=1")

    async def test_bearer_uses_same_password(self):
        for scheme in ("Bearer", "bearer"):
            response = await self.client.post("/mcp", headers={"Authorization": f"{scheme} test-password-only"})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(self.forwarded[-1]["path"], "/mcp")

    async def test_health_check_does_not_reach_app(self):
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")
        self.assertEqual(self.forwarded, [])

    def test_missing_password_fails_closed(self):
        with patch.object(server, "PASSWORD", ""):
            with self.assertRaisesRegex(RuntimeError, "SERVER_PASSWORD"):
                server.protect(None)

    async def test_exported_app_rejects_unauthenticated_tool_call(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://testserver") as client:
            response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "jev_yes_no", "arguments": {"text": "test", "question": "test?"}}})
            self.assertEqual(response.status_code, 401)

    async def test_both_authenticated_routes_reach_real_mcp(self):
        async with server.mcp.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://testserver") as client:
                for path, auth in (("/test-password-only/mcp", {}), ("/mcp", {"Authorization": "Bearer test-password-only"})):
                    response = await client.post(path, headers={"Accept": "application/json, text/event-stream", **auth}, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
                    self.assertEqual(response.status_code, 200, response.text)
                    for name in ("jev_yes_no", "jev_choice", "jev_score"):
                        self.assertIn(name, response.text)


if __name__ == "__main__":
    unittest.main()
