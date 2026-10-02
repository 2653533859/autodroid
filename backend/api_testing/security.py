import logging
from contextvars import ContextVar

# Only used to recognize legacy masked samples.
MASK = "••••••"
PRIVATE_HTTP_LOGS = ContextVar("api_testing_private_http_logs", default=False)


class _PrivateHttpFilter(logging.Filter):
    def filter(self, record):
        return not PRIVATE_HTTP_LOGS.get()


# HTTPX logs entire request URLs at INFO and httpcore may log response headers
# at DEBUG. Suppress those only inside this executor, preserving other features.
for _logger_name in (
    "httpx",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
):
    logging.getLogger(_logger_name).addFilter(_PrivateHttpFilter())
