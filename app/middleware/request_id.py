"""Request ID tracking middleware and context variable."""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

REQUEST_ID_CTX_VAR: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="",
)


def get_request_id() -> str:
    """Return the current request ID from context storage.

    Returns:
        The active request ID string, or an empty string if unset.
    """
    return REQUEST_ID_CTX_VAR.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts or generates a unique request ID per HTTP request.

    The request ID is retrieved from the incoming ``X-Request-ID`` header or generated
    as a new UUID4. It is stored in ``REQUEST_ID_CTX_VAR`` for the duration of the request
    and returned in the response headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the request ID middleware.

        Args:
            app: The ASGI application instance.
        """
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process incoming request, bind request ID to context, and attach header to response.

        Args:
            request: The incoming HTTP request.
            call_next: Next request processing callable in the ASGI chain.

        Returns:
            The HTTP response containing the X-Request-ID header.
        """
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = REQUEST_ID_CTX_VAR.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            REQUEST_ID_CTX_VAR.reset(token)
