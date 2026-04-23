
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from auditmind.logger import get_logger

logger = get_logger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        logger.info(
            f"→ [{request_id}] {request.method} {request.url.path}"
        )
        response = await call_next(request)
        elapsed = round((time.time() - start) * 1000, 1)
        logger.info(
            f"← [{request_id}] {response.status_code} ({elapsed}ms)"
        )
        response.headers["X-Request-ID"] = request_id
        return response