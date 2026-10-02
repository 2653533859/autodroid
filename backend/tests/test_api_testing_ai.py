import copy
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from backend.api.deps import get_current_active_user
from backend.api_testing import ai_service, service
from backend.api_testing.ai_routes import router
from backend.api_testing.ai_schemas import ExplainFailureRequest, FeedbackRequest, SuggestAssertionsRequest
from backend.api_testing.schemas import Assertion, Parameter, Step, literal
from backend.database import get_session
from backend.models import ApiRun, ApiStepResult, Environment, GlobalVariable, SystemSetting, User


def suggestion(path, op="exists", expected=None):
    return {"assertion": {"path": path, "op": op, "expected": expected}, "reason": "建议检查这个字段"}


class ApiTestingAiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.user = User(username="ai-reviewer", hashed_password="unused")
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)
        self.user_id = self.user.id
        self.step = Step(id="first")
        self.step.snapshot.request.url = literal("https://business.example/orders")
        self.item = service.create_debug(self.user_id, "editor", None)
        self.prepare_debug([self.step])
        self.payload = SuggestAssertionsRequest(steps=[self.step], debug_session_id=self.item.id, editor_id="editor", step_id=self.step.id, draft_token="draft-1")
        ai_service._calls.clear()
        ai_service._active_users.clear()

    def tearDown(self):
        service.debug_sessions.clear()
        ai_service._calls.clear()
        ai_service._active_users.clear()
        self.session.close()
        self.engine.dispose()

    def prepare_debug(self, steps, env=None):
        service._sync_debug(self.item, steps, env or {})
        for step in steps:
            self.item.responses[step.id] = {"status_code": 200, "body": {"id": "dynamic-123", "count": 2, "active": True, "name": "some value"}, "headers": {"Authorization": "secret-header"}, "cookies": {"session": "secret-cookie"}}
            self.item.results[step.id] = {"status": "PASS", "detail": {"response": self.item.responses[step.id]}, "name": step.name}
            self.item.assertion_fingerprints[step.id] = json.dumps([a.model_dump() for a in step.effective().assertions], sort_keys=True)
        self.item.status = "PASS"

    def configure(self, **overrides):
        values = {"api_testing_ai_enabled": "true", "ai_api_key": "provider-secret", "ai_api_base": "https://model.example/v1", "ai_model": "configured-model", **overrides}
        for key, value in values.items():
            self.session.add(SystemSetting(key=key, value=value))
        self.session.commit()

    def model(self, items):
        return patch.object(ai_service, "call_model", AsyncMock(return_value=({"suggestions": items}, 123)))

    async def test_default_disabled_and_missing_model_never_call_model(self):
        self.assertEqual(ai_service.settings(self.session)[0]["available"], False)
        with self.model([]) as model:
            with self.assertRaises(HTTPException) as raised:
                await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
            self.assertEqual(raised.exception.status_code, 503)
            model.assert_not_called()
        self.configure(ai_model="")
        self.assertFalse(ai_service.settings(self.session)[0]["available"])

    async def test_suggestions_are_read_only_and_feedback_is_user_bound(self):
        self.configure()
        original = copy.deepcopy(self.item.results)
        with self.model([suggestion(["body", "count"], "type", "number")]) as model:
            result = await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
        self.assertEqual(result["draft_token"], "draft-1")
        self.assertEqual(result["suggestions"][0]["assertion"]["expected"]["value"], "number")
        self.assertEqual(original, self.item.results)
        self.assertEqual(result["usage"]["total_tokens"], 123)
        self.assertEqual(model.call_args.args[2]["fields"][0]["value"], 200)
        feedback = FeedbackRequest(call_id=result["call_id"], action="accepted", selected_count=1)
        self.assertEqual(ai_service.feedback(feedback, self.user_id), {"ok": True})
        with self.assertRaises(HTTPException) as raised:
            ai_service.feedback(feedback, self.user_id + 1)
        self.assertEqual(raised.exception.status_code, 404)
        ai_service._calls[result["call_id"]]["created"] -= 1801
        with self.assertRaises(HTTPException):
            ai_service.feedback(feedback, self.user_id)

    async def test_invalid_dynamic_typed_and_unknown_suggestions_are_filtered(self):
        self.configure()
        items = [suggestion(["body", "missing"]), suggestion(["body", "id"], "eq", "dynamic-123"), suggestion(["body", "count"], "eq", "2"), suggestion(["body", "count"], "type", "string"), suggestion(["body", "active"], "gt", 0), suggestion(["body", "count"], "exists"), {"code": "print('bad')"}]
        with self.model(items):
            result = await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
        self.assertEqual(len(result["suggestions"]), 1)
        self.assertEqual(len(result["warnings"]), 6)

    async def test_wrong_user_stale_request_and_environment_cannot_generate(self):
        self.configure()
        with self.model([]) as model:
            with self.assertRaises(HTTPException) as raised:
                await ai_service.suggest_assertions(self.payload, self.session, self.user_id + 1)
            self.assertEqual(raised.exception.status_code, 404)
            self.payload.steps[0].snapshot.request.url = literal("https://changed.example")
            with self.assertRaises(HTTPException) as raised:
                await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
            self.assertEqual(raised.exception.status_code, 409)
            model.assert_not_called()

    async def test_edited_predecessor_assertions_require_revalidation(self):
        self.configure()
        second = Step(id="second", snapshot=self.step.snapshot.model_copy(deep=True))
        self.prepare_debug([self.step, second])
        self.payload.steps = [self.step, second]
        self.payload.step_id = "second"
        self.payload.steps[0].snapshot.assertions.append(Assertion(path=["body", "count"], op="eq", expected=literal(3)))
        before = copy.deepcopy(self.item.results)
        with self.model([]) as model:
            with self.assertRaises(HTTPException) as raised:
                await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
            self.assertEqual(raised.exception.status_code, 409)
            model.assert_not_called()
        self.assertEqual(before, self.item.results)

    async def test_sanitizes_secrets_auth_cookies_and_personal_free_text_before_model(self):
        self.configure()
        env = Environment(name="test")
        self.session.add(env)
        self.session.commit()
        self.session.refresh(env)
        self.session.add(GlobalVariable(env_id=env.id, key="API_SECRET", value="environment-secret", is_secret=True))
        self.session.commit()
        self.payload.env_id = self.item.env_id = env.id
        self.step.snapshot.request.headers = [Parameter(name="Authorization", value=literal("header-literal-secret"))]
        # Revalidate through the ordinary contract before fingerprinting.
        self.step = Step.model_validate(self.step.model_dump())
        self.payload.steps = [self.step]
        self.prepare_debug([self.step], {"API_SECRET": "environment-secret"})
        self.item.responses[self.step.id]["body"].update({"token": "body-token-secret", "email": "someone@example.com", "message": "Call 13800138000"})
        secrets = ["environment-secret", "provider-secret", "header-literal-secret", "body-token-secret", "secret-header", "secret-cookie", "someone@example.com", "13800138000"]
        self.payload.goal = " ".join(secrets)
        with self.model([suggestion(["body", "count"])]) as model:
            await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
        serialized = json.dumps(model.call_args.args[2], ensure_ascii=False)
        for secret in secrets:
            self.assertNotIn(secret, serialized)
        self.assertNotIn('"headers"', serialized)
        self.assertNotIn('"cookies"', serialized)

    async def test_failure_facts_are_server_derived_and_unknown_evidence_is_filtered(self):
        self.configure()
        run = ApiRun(id="failed", scenario_name="test", status="FAIL", snapshot={})
        step = ApiStepResult(run_id=run.id, step_id="first", position=0, name="test", status="FAIL", detail={"response": {"status_code": 401, "body": {"token": "dont-send-this"}}, "assertions": [{"path": ["body", "count"], "passed": False, "actual": "dont-send-this", "expected": 2}]})
        self.session.add(run)
        self.session.add(step)
        self.session.commit()
        generated = {"possible_causes": [{"text": "可能鉴权未生效", "evidence_ids": ["F2"]}, {"text": "invented", "evidence_ids": ["F999"]}], "next_steps": [{"text": "检查测试环境中的凭据配置", "evidence_ids": ["F2"]}]}
        with patch.object(ai_service, "call_model", AsyncMock(return_value=(generated, 5))) as model:
            result = await ai_service.explain_failure(ExplainFailureRequest(run_id="failed"), self.session, self.user_id)
        self.assertEqual(result["facts"][1]["message"], "HTTP 状态码为 401")
        self.assertEqual(len(result["possible_causes"]), 1)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertNotIn("dont-send-this", json.dumps(model.call_args.args[2]))
        self.session.refresh(run)
        self.assertEqual(run.status, "FAIL")

    async def test_precheck_failure_uses_structured_context_without_raw_messages(self):
        self.configure()
        run = ApiRun(id="precheck", scenario_name="test", status="ERROR", snapshot={"precheck_errors": [{"section": "auth", "step_id": "first", "message": "环境变量 missing-secret 不存在"}]})
        self.session.add(run)
        self.session.commit()
        facts, context, _ = ai_service.failure_context(self.session, run.id, ai_service.settings(self.session)[1])
        self.assertIn("鉴权", facts[0]["message"])
        self.assertIn("环境变量", facts[0]["message"])
        self.assertNotIn("missing-secret", json.dumps(context, ensure_ascii=False))

    async def test_model_error_does_not_fabricate_success_and_releases_slot(self):
        self.configure()
        with patch.object(ai_service, "call_model", AsyncMock(side_effect=HTTPException(504, "timeout"))):
            with self.assertRaises(HTTPException) as raised:
                await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
        self.assertEqual(raised.exception.status_code, 504)
        self.assertFalse(ai_service._active_users)
        self.assertFalse(ai_service._calls)

    async def test_current_unchecked_response_can_receive_suggestions_but_not_predecessor(self):
        self.configure()
        self.item.results[self.step.id]["status"] = "UNCHECKED"
        with self.model([suggestion(["body", "count"])]):
            result = await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
        self.assertEqual(len(result["suggestions"]), 1)
        second = Step(id="second", snapshot=self.step.snapshot.model_copy(deep=True))
        self.prepare_debug([self.step, second])
        self.item.results[self.step.id]["status"] = "UNCHECKED"
        self.payload.steps = [self.step, second]
        self.payload.step_id = second.id
        with self.model([]) as model:
            with self.assertRaises(HTTPException) as raised:
                await ai_service.suggest_assertions(self.payload, self.session, self.user_id)
            self.assertEqual(raised.exception.status_code, 409)
            model.assert_not_called()

    async def test_provider_schema_fallback_only_for_explicit_unsupported(self):
        config = {"base": "https://model.example/v1", "key": "key", "model": "model"}
        for message, expected_calls in (("response_format json_schema not supported", 2), ("schema properties invalid", 1)):
            requests = []
            def handler(request):
                requests.append(json.loads(request.content))
                if len(requests) == 1:
                    return httpx.Response(400, json={"error": {"message": message, "param": "response_format"}})
                return httpx.Response(200, json={"choices": [{"message": {"content": '{"suggestions":[]}'}}], "usage": {"total_tokens": 3}})
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch.object(ai_service.httpx, "AsyncClient", return_value=client) as factory:
                if expected_calls == 2:
                    result, usage = await ai_service.call_model(config, "assertions", {}, ai_service.suggestion_schema())
                    self.assertEqual(result, {"suggestions": []})
                    self.assertEqual(usage, 3)
                    self.assertNotIn("response_format", requests[1])
                else:
                    with self.assertRaises(HTTPException) as raised:
                        await ai_service.call_model(config, "assertions", {}, ai_service.suggestion_schema())
                    self.assertEqual(raised.exception.status_code, 502)
                self.assertFalse(factory.call_args.kwargs["trust_env"])
            self.assertEqual(len(requests), expected_calls)

    async def test_provider_timeout_is_504_and_errors_do_not_expose_raw_text(self):
        config = {"base": "https://model.example/v1", "key": "provider-secret", "model": "model"}
        for timeout in (True, False):
            def handler(request):
                if timeout:
                    raise httpx.ReadTimeout("raw-secret-in-error", request=request)
                return httpx.Response(500, text="raw-secret-in-error")
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch.object(ai_service.httpx, "AsyncClient", return_value=client):
                with self.assertRaises(HTTPException) as raised:
                    await ai_service.call_model(config, "assertions", {}, ai_service.suggestion_schema())
            self.assertEqual(raised.exception.status_code, 504 if timeout else 502)
            self.assertNotIn("raw-secret", raised.exception.detail)

    async def test_malformed_or_refused_model_result_is_not_a_success(self):
        config = {"base": "https://model.example/v1", "key": "provider-secret", "model": "model"}
        for message in ({"content": "```json bad```"}, {"content": "{}", "refusal": "unable"}):
            client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": message}]})))
            with patch.object(ai_service.httpx, "AsyncClient", return_value=client):
                with self.assertRaises(HTTPException) as raised:
                    await ai_service.call_model(config, "assertions", {}, ai_service.suggestion_schema())
            self.assertEqual(raised.exception.status_code, 502)

    async def test_routes_require_auth_and_status_never_returns_credentials(self):
        self.configure()
        app = FastAPI()
        app.include_router(router, prefix="/api/api-testing")
        app.dependency_overrides[get_session] = lambda: self.session
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/api-testing/ai/status").status_code, 401)
            app.dependency_overrides[get_current_active_user] = lambda: self.user
            response = client.get("/api/api-testing/ai/status")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["available"])
            self.assertNotIn("provider-secret", response.text)


if __name__ == "__main__":
    unittest.main()
