import asyncio
import base64
import json
import time
from urllib.parse import quote, urlencode

import httpx

from .security import PRIVATE_HTTP_LOGS
from .values import ExecutionError, assertion_outcome, evaluate_assertions, field_tree, request_issues, resolve, scalar_text

MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class RunCancelled(Exception):
    pass


async def cancellable(awaitable, cancel, timeout=None):
    async def watch():
        while not cancel.is_set():
            await asyncio.sleep(0.05)
        raise RunCancelled()

    operation = asyncio.ensure_future(awaitable)
    watcher = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait({operation, watcher}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise ExecutionError("请求超过总超时时间", category="connection")
        if cancel.is_set():
            raise RunCancelled()
        return await operation
    finally:
        operation.cancel()
        watcher.cancel()
        await asyncio.gather(operation, watcher, return_exceptions=True)


def make_request(spec, env, outputs, refs):
    issues = request_issues(spec, env, outputs)
    if issues:
        raise ExecutionError(issues[0]["message"], location=issues[0]["location"])

    def text(value):
        return scalar_text(resolve(value, env, outputs, refs))

    url = text(spec.url)
    for param in spec.path_params:
        if param.enabled:
            url = url.replace("{" + param.name + "}", quote(text(param.value), safe=""))
    if "{" in url or "}" in url:
        raise ExecutionError("URL 存在未解析的路径参数")
    try:
        target = httpx.URL(url)
    except httpx.InvalidURL:
        raise ExecutionError("请求 URL 无效") from None
    if target.scheme not in {"http", "https"} or not target.host or target.userinfo:
        raise ExecutionError("仅支持不含用户凭证的 HTTP/HTTPS URL")
    headers = [(p.name, text(p.value)) for p in spec.headers if p.enabled]
    if any(name.lower() in {"host", "content-length", "transfer-encoding", "connection"} for name, _ in headers):
        raise ExecutionError("Host/Content-Length/Transfer-Encoding/Connection 由执行器管理")
    params = [(p.name, text(p.value)) for p in spec.query if p.enabled]
    auth = spec.auth
    if auth.kind == "bearer":
        token = text(auth.token)
        headers = [(k, v) for k, v in headers if k.lower() != "authorization"] + [("Authorization", "Bearer " + token)]
    elif auth.kind == "basic":
        user, password = text(auth.username), text(auth.password)
        credential = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers = [(k, v) for k, v in headers if k.lower() != "authorization"] + [
            ("Authorization", "Basic " + credential)
        ]
    elif auth.kind == "api_key":
        if not auth.key_name:
            raise ExecutionError("API Key 名称不能为空")
        token = text(auth.token)
        if auth.location == "header":
            headers = [(k, v) for k, v in headers if k.lower() != auth.key_name.lower()] + [(auth.key_name, token)]
        else:
            params = [(k, v) for k, v in params if k != auth.key_name] + [(auth.key_name, token)]
    target = target.copy_merge_params(params)
    body, kwargs = None, {}
    if spec.body_type == "json":
        body = resolve(spec.body, env, outputs, refs)
        # Explicit encoding also supports JSON null (httpx json=None means no body).
        kwargs["content"] = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if not any(k.lower() == "content-type" for k, _ in headers):
            headers.append(("Content-Type", "application/json"))
    elif spec.body_type == "text":
        body = text(spec.body)
        kwargs["content"] = body.encode("utf-8")
    elif spec.body_type == "form":
        pairs = [(p.name, text(p.value)) for p in spec.form if p.enabled]
        body = [{"name": k, "value": v} for k, v in pairs]
        kwargs["content"] = urlencode(pairs).encode("utf-8")
        if not any(k.lower() == "content-type" for k, _ in headers):
            headers.append(("Content-Type", "application/x-www-form-urlencoded"))
    display = {"method": spec.method, "url": str(target), "headers": dict(headers), "body": body}
    return target, headers, kwargs, display


async def execute_step(step, client, env, outputs, cancel):
    started = time.monotonic()
    log_token = PRIVATE_HTTP_LOGS.set(True)
    detail = {"references": [], "assertions": [], "error": None, "error_category": None}
    status, response = "PASS", None
    try:
        if cancel.is_set():
            raise RunCancelled()
        if step.kind == "wait":
            await cancellable(asyncio.sleep(step.seconds), cancel)
        else:
            config = step.effective()
            target, headers, kwargs, request = make_request(
                config.request, env, outputs, detail["references"]
            )
            detail["request"] = request

            async def send():
                async with client.stream(
                    config.request.method, target, headers=headers, timeout=config.request.timeout_seconds, **kwargs
                ) as res:
                    detail["request"]["headers"] = dict(res.request.headers)
                    data = bytearray()
                    async for chunk in res.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE_BYTES:
                            raise ExecutionError("响应体超过 5 MiB 上限，未解析截断数据", category="http")
                    text = bytes(data).decode(res.encoding or "utf-8", errors="replace")
                    parsed, json_valid = None, False
                    if text:
                        try:
                            parsed = json.loads(text)
                            json_valid = True
                        except (ValueError, RecursionError):
                            pass
                    body = {
                        "status_code": res.status_code,
                        "headers": dict(res.headers),
                        "cookies": {cookie.name: cookie.value for cookie in res.cookies.jar},
                        "text": text,
                        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                    }
                    # Missing body differs from an actual JSON null response.
                    if json_valid:
                        body["body"] = parsed
                    detail["json_valid"] = json_valid
                    return body

            response = await cancellable(send(), cancel, config.request.timeout_seconds)
            detail["response"] = response
            detail["fields"] = field_tree(response)[0]["children"]
            detail["request_references"] = list(detail["references"])
            detail["assertions"] = evaluate_assertions(config.assertions, response, env, outputs, detail["references"])
            status, detail["error"], detail["error_category"] = assertion_outcome(detail["assertions"])
    except RunCancelled:
        status, detail["error"] = "ABORTED", "用户已中止；已发送的请求可能已经生效"
        detail["error_category"] = "cancelled"
    except (ExecutionError, httpx.HTTPError, ValueError, TypeError) as exc:
        status = "ERROR"
        # Never expose raw client exceptions, which may contain resolved URLs.
        if isinstance(exc, ExecutionError):
            detail["error"], detail["error_category"] = str(exc), exc.category
            if exc.location:
                detail["error_location"] = exc.location
        elif isinstance(exc, httpx.TimeoutException):
            detail["error"], detail["error_category"] = "请求超时，请检查目标服务和超时设置", "connection"
        elif isinstance(exc, (httpx.ConnectError, httpx.NetworkError, httpx.ProxyError)):
            detail["error"], detail["error_category"] = "无法连接目标服务，请检查地址、网络和证书", "connection"
        elif isinstance(exc, httpx.HTTPError):
            detail["error"], detail["error_category"] = "HTTP 通信异常，请检查服务响应和连接状态", "http"
        else:
            detail["error"], detail["error_category"] = "请求配置无效，请检查参数类型和内容", "configuration"
    finally:
        PRIVATE_HTTP_LOGS.reset(log_token)
    return {
        "step_id": step.id,
        "name": step.name,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "detail": detail,
    }, response


def make_client(cookies=None, transport=None):
    return httpx.AsyncClient(
        transport=transport or httpx.AsyncHTTPTransport(verify=True, retries=0, trust_env=False), cookies=cookies, follow_redirects=False, trust_env=False
    )
