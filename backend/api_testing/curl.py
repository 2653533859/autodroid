import json
import shlex
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .schemas import RequestSpec, Parameter, from_json, literal
from .values import ExecutionError


def parse_curl(command):
    # This is deliberately not a shell, even for apparently harmless snippets.
    if any(part in command for part in ("$(", "`", "${", "\x00")):
        raise ExecutionError("cURL 不允许命令替换或 shell 变量")
    try:
        args = shlex.split(command.replace("\\\n", " "))
    except ValueError as exc:
        raise ExecutionError(f"cURL 引号不完整: {exc}") from None
    if not args or args.pop(0) != "curl":
        raise ExecutionError("请粘贴以 curl 开头的单条请求")
    spec, urls, body_parts, encoded = RequestSpec(), [], [], False
    explicit_method = False
    takes_value = {
        "-X",
        "--request",
        "-H",
        "--header",
        "-b",
        "--cookie",
        "-d",
        "--data",
        "--data-raw",
        "--data-binary",
        "--data-urlencode",
        "--url",
        "-u",
        "--user",
    }
    while args:
        arg = args.pop(0)
        if arg in {";", "&&", "|", "||", ">", "<"}:
            raise ExecutionError("不允许 shell 操作符")
        if arg in {"--compressed", "-s", "--silent", "-S", "--show-error"}:
            continue
        if arg in {"-I", "--head"}:
            spec.method, explicit_method = "HEAD", True
            continue
        value = None
        if arg.startswith("--") and "=" in arg:
            arg, value = arg.split("=", 1)
        elif len(arg) > 2 and arg[:2] in {"-X", "-H", "-b", "-d", "-u"}:
            arg, value = arg[:2], arg[2:]
        if arg in takes_value:
            if value is None:
                if not args:
                    raise ExecutionError(f"缺少参数值: {arg}")
                value = args.pop(0)
            if arg in {"--url"}:
                urls.append(value)
            elif arg in {"-X", "--request"}:
                spec.method, explicit_method = value.upper(), True
            elif arg in {"-H", "--header"}:
                if value.startswith("@") or ":" not in value:
                    raise ExecutionError("不支持文件请求头或无效请求头")
                name, text = value.split(":", 1)
                spec.headers.append(Parameter(name=name.strip(), value=literal(text.strip())))
            elif arg in {"-b", "--cookie"}:
                if "=" not in value or value.startswith("@"):
                    raise ExecutionError("Cookie 必须直接填写键值，不支持文件")
                spec.headers.append(Parameter(name="Cookie", value=literal(value)))
            elif arg in {"-u", "--user"}:
                if ":" not in value:
                    raise ExecutionError("Basic 鉴权需要 username:password")
                username, password = value.split(":", 1)
                spec.auth.kind, spec.auth.username, spec.auth.password = "basic", literal(username), literal(password)
            else:
                if value.startswith("@") and arg != "--data-raw":
                    raise ExecutionError("不支持读取本地文件")
                if arg == "--data-urlencode":
                    if "@" in value or "=" not in value:
                        raise ExecutionError("data-urlencode 仅支持 name=value")
                    encoded = True
                    key, val = value.split("=", 1)
                    value = urlencode({key: val})
                body_parts.append(value)
        elif arg.startswith("-"):
            raise ExecutionError(f"尚不支持的 cURL 参数: {arg}")
        else:
            urls.append(arg)
    if len(urls) != 1 or urlsplit(urls[0]).scheme not in {"http", "https"}:
        raise ExecutionError("只能导入一个 HTTP/HTTPS URL")
    parsed = urlsplit(urls[0])
    spec.url = literal(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")))
    spec.query = [Parameter(name=k, value=literal(v)) for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
    if body_parts:
        if not explicit_method:
            spec.method = "POST"
        body = "&".join(body_parts)
        content_type = next((h.value.value for h in spec.headers if h.name.lower() == "content-type"), "")
        if "json" in content_type:
            try:
                spec.body_type, spec.body = "json", from_json(json.loads(body))
            except ValueError:
                raise ExecutionError("声明了 JSON Content-Type，但请求体不是有效 JSON") from None
        elif encoded or not content_type or "x-www-form-urlencoded" in content_type:
            spec.body_type = "form"
            spec.form = [Parameter(name=k, value=literal(v)) for k, v in parse_qsl(body, keep_blank_values=True)]
        else:
            spec.body_type, spec.body = "text", literal(body)
    return RequestSpec.model_validate(spec.model_dump())
