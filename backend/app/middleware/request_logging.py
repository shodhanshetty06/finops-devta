"""
Structured request logging (Phase 7).

Every request gets a `request_id` (returned via the `X-Request-ID`
response header, so a client-reported issue can be grepped straight to its
server-side log line) and a single JSON-formatted log line on completion -
method, path, status, duration, client IP, and the request id. Logging the
message as a JSON string (rather than free-text/positional fields) is what
makes this "structured": any log aggregator (CloudWatch, Stackdriver, ELK)
can parse the message field directly instead of needing a regex.

Kept as one log line per request rather than two (request-received +
request-completed) since duration is only known at completion anyway, and
a single line is simpler to correlate.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.config import get_settings

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            if response is not None:
                response.headers[REQUEST_ID_HEADER] = request_id

            if get_settings().request_logging_enabled:
                request_logger.info(json.dumps({
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                }))
