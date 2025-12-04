"""
Global error handling middleware
"""

import traceback
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.utils.exceptions import APIError
from app.utils.logger import logger


async def error_handler_middleware(
    request: Request,
    call_next: Callable,
) -> Response:
    """
    Global error handling middleware.

    Catches unhandled exceptions and returns appropriate JSON responses.
    """
    try:
        response = await call_next(request)
        return response

    except APIError as exc:
        # Handle custom API errors
        logger.warning(
            "API error",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    except Exception as exc:
        # Handle unexpected errors
        logger.exception(
            "Unhandled exception in request",
            error=str(exc),
            path=request.url.path,
            method=request.method,
        )

        if settings.DEBUG:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )

