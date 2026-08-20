"""
Catches any exception a route raises that isn't a `FinOpsError` (i.e. a real
bug, not an expected domain error) and turns it into a normal 500 response.

This has to be `app.add_middleware`, not `@app.exception_handler(Exception)`:
FastAPI/Starlette special-cases a handler registered for the base
`Exception` class (or status 500) by installing it on `ServerErrorMiddleware`
instead of `ExceptionMiddleware` - and `ServerErrorMiddleware` is the
outermost layer in the stack, wrapping every middleware added via
`app.add_middleware` (including `CORSMiddleware`). A response built there
never passes back out through CORSMiddleware, so it carries no
Access-Control-Allow-Origin header and the browser drops it silently -
callers see a bare "Network Error" with no indication a 500 ever happened.
Catching the exception in ordinary middleware instead means the resulting
JSONResponse is just a normal response flowing back out through whatever
middleware wraps this one, CORS included.
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("app.unhandled")


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "An unexpected error occurred. Please try again."},
            )
