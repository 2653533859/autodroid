import asyncio
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpx

from backend.api_testing.engine import execute_step, make_client
from backend.api_testing.schemas import Assertion, Parameter, Step, Value, from_json, literal


class ApiEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_socket_transport_keeps_host_and_reads_json(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(self.headers.get("Host"))
                payload = b'{"ok":true,"id":42}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            step = self.step("/")
            step.snapshot.request.url = literal(f"http://127.0.0.1:{server.server_port}/")
            async with make_client() as client:
                result, response = await execute_step(step, client, {}, {}, threading.Event())
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(response["body"]["id"], 42)
            self.assertEqual(observed, [f"127.0.0.1:{server.server_port}"])
        finally:
            await asyncio.to_thread(server.shutdown)
            server.server_close()
            thread.join(timeout=2)

    def step(self, path, method="GET"):
        step = Step(id=path, name=path)
        step.snapshot.request.url = literal("https://api.example.com" + path)
        step.snapshot.request.method = method
        return step

    async def test_login_create_query_cookie_reference_journey(self):
        received = []

        def handler(request):
            received.append(request)
            if request.url.path == "/login":
                return httpx.Response(200, json={"token": "fresh-token"}, headers={"Set-Cookie": "session=abc; Path=/"})
            self.assertEqual(request.headers["authorization"], "Bearer fresh-token")
            self.assertIn("session=abc", request.headers["cookie"])
            if request.url.path == "/orders":
                self.assertEqual(json.loads(request.content), {"quantity": 2, "enabled": False})
                return httpx.Response(201, json={"id": 42})
            self.assertEqual(request.url.path, "/orders/42")
            return httpx.Response(200, json={"id": 42, "paid": False})

        login, create, query = self.step("/login", "POST"), self.step("/orders", "POST"), self.step("/orders/{id}")
        for step in (create, query):
            step.snapshot.request.auth.kind = "bearer"
            step.snapshot.request.auth.token = Value(kind="ref", step_id=login.id, path=["body", "token"])
        create.snapshot.request.body_type = "json"
        create.snapshot.request.body = from_json({"quantity": 2, "enabled": False})
        query.snapshot.request.path_params = [
            Parameter(name="id", value=Value(kind="ref", step_id=create.id, path=["body", "id"]))
        ]
        query.snapshot.assertions.append(
            Assertion(path=["body", "id"], op="eq", expected=Value(kind="ref", step_id=create.id, path=["body", "id"]))
        )
        outputs = {}
        async with make_client(transport=httpx.MockTransport(handler)) as client:
            for step in (login, create, query):
                result, response = await execute_step(step, client, {}, outputs, threading.Event())
                self.assertEqual(result["status"], "PASS", result)
                if step.id == login.id:
                    self.assertEqual(result["detail"]["response"]["body"]["token"], "fresh-token")
                    self.assertEqual(result["detail"]["response"]["cookies"], {"session": "abc"})
                    self.assertEqual(result["detail"]["response"]["headers"]["set-cookie"], "session=abc; Path=/")
                else:
                    self.assertEqual(result["detail"]["request"]["headers"]["authorization"], "Bearer fresh-token")
                    self.assertIn("session=abc", result["detail"]["request"]["headers"]["cookie"])
                outputs[step.id] = response
        self.assertEqual(len(received), 3)
        self.assertIs(type(outputs[create.id]["body"]["id"]), int)

    async def test_non_json_empty_invalid_json_and_negative_status(self):
        for response in [
            httpx.Response(204),
            httpx.Response(200, text="plain"),
            httpx.Response(200, text="{bad", headers={"content-type": "application/json"}),
        ]:
            async with make_client(transport=httpx.MockTransport(lambda _: response)) as client:
                result, output = await execute_step(self.step("/"), client, {}, {}, threading.Event())
                self.assertEqual(result["status"], "PASS")
                self.assertNotIn("body", output)
        step = self.step("/")
        step.snapshot.assertions = [Assertion(path=["status_code"], op="eq", expected=literal(400))]
        async with make_client(transport=httpx.MockTransport(lambda _: httpx.Response(400, json={}))) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
            self.assertEqual(result["status"], "PASS")

    async def test_missing_reference_never_sends_request(self):
        calls = []
        step = self.step("/")
        step.snapshot.request.body_type = "json"
        step.snapshot.request.body = Value(kind="ref", step_id="missing", path=["body"])
        async with make_client(
            transport=httpx.MockTransport(lambda r: (calls.append(r), httpx.Response(200))[1])
        ) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
        self.assertEqual(result["status"], "ERROR")
        self.assertFalse(calls)

    async def test_timeout_size_and_abort(self):
        async def slow(_):
            await asyncio.sleep(2)
            return httpx.Response(200)

        step = self.step("/")
        step.snapshot.request.timeout_seconds = 0.03
        async with make_client(transport=httpx.MockTransport(slow)) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
            self.assertEqual(result["status"], "ERROR")
        with patch("backend.api_testing.engine.MAX_RESPONSE_BYTES", 8):
            async with make_client(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, text="x" * 9))
            ) as client:
                result, output = await execute_step(self.step("/"), client, {}, {}, threading.Event())
                self.assertEqual(result["status"], "ERROR")
                self.assertIsNone(output)
        cancel = threading.Event()
        async with make_client(transport=httpx.MockTransport(slow)) as client:
            asyncio.get_running_loop().call_later(0.03, cancel.set)
            result, _ = await execute_step(self.step("/"), client, {}, {}, cancel)
            self.assertEqual(result["status"], "ABORTED")

    async def test_form_repeated_keys_and_no_redirect(self):
        def handler(request):
            self.assertEqual(request.content.decode(), "x=1&x=2")
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/"})

        step = self.step("/", "POST")
        step.snapshot.request.body_type = "form"
        step.snapshot.request.form = [Parameter(name="x", value=literal("1")), Parameter(name="x", value=literal("2"))]
        async with make_client(transport=httpx.MockTransport(handler)) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
            self.assertEqual(result["status"], "FAIL")

    async def test_zero_assertions_are_unchecked_for_success_and_error_responses(self):
        step = self.step("/")
        step.snapshot.assertions = []
        for code in (200, 500):
            async with make_client(transport=httpx.MockTransport(lambda _: httpx.Response(code, json={"id": 42}))) as client:
                result, response = await execute_step(step, client, {}, {}, threading.Event())
            self.assertEqual(result["status"], "UNCHECKED")
            self.assertEqual(result["detail"]["error_category"], "unchecked")
            self.assertEqual(response["body"], {"id": 42})
        wait = Step(kind="wait", seconds=0)
        wait.snapshot.assertions = []
        async with make_client(transport=httpx.MockTransport(lambda _: self.fail("wait sent HTTP"))) as client:
            result, _ = await execute_step(wait, client, {}, {}, threading.Event())
        self.assertEqual(result["status"], "PASS")

    async def test_errors_have_categories_and_runtime_auth_is_validated_before_http(self):
        step = self.step("/")
        step.snapshot.request.auth.kind = "bearer"
        step.snapshot.request.auth.token = Value(kind="ref", step_id="login", path=["body", "token"])
        async with make_client(transport=httpx.MockTransport(lambda _: self.fail("invalid token sent HTTP"))) as client:
            result, _ = await execute_step(step, client, {}, {"login": {"body": {"token": ""}}}, threading.Event())
        self.assertEqual(result["detail"]["error_category"], "configuration")
        self.assertEqual(result["detail"]["error_location"], ["request", "auth", "token"])

        step.snapshot.request.auth.kind = "none"
        def disconnected(_):
            raise httpx.ConnectError("private URL must not leak")
        async with make_client(transport=httpx.MockTransport(disconnected)) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
        self.assertEqual(result["detail"]["error_category"], "connection")
        self.assertNotIn("private URL", result["detail"]["error"])
        async with make_client(transport=httpx.MockTransport(lambda _: httpx.Response(500, json={"id": 42}))) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
        self.assertEqual(result["detail"]["error_category"], "http")
        step.snapshot.assertions = [Assertion(path=["body", "id"], op="eq", expected=literal(7))]
        async with make_client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": 42}))) as client:
            result, _ = await execute_step(step, client, {}, {}, threading.Event())
        self.assertEqual(result["detail"]["error_category"], "assertion")


if __name__ == "__main__":
    unittest.main()
