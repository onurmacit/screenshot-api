"""
Screenshot and PDF rendering endpoints
"""

from datetime import datetime
from typing import Union
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.dependencies import (
    DBSession,
    RateLimitedUser,
)
from app.core.config import settings
from app.models import RenderJob
from app.schemas.render import (
    PDFRequest,
    RenderJobAsyncResponse,
    RenderJobResponse,
    RenderJobsListResponse,
    ScreenshotRequest,
    ScreenshotResponse,
    SizeInfo,
)
from app.services.cache_service import cache_service
from app.services.rate_limit_service import rate_limit_service
from app.services.storage_service import storage_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.helpers import utc_now
from app.utils.validators import validate_url
from app.utils.signature import generate_signature, verify_signature

# Import render service based on configuration
if settings.USE_GO_RENDERER:
    from app.services.go_render_client import go_render_client as render_service
else:
    from app.services.render_service import render_service

# Only import Celery tasks if not using Go renderer (for async mode)
if not settings.USE_GO_RENDERER:
    from app.workers.render_tasks import process_pdf, process_screenshot

router = APIRouter()


# =============================================================================
# PUBLIC DEMO ENDPOINT - No authentication required, IP rate-limited
# =============================================================================

@router.get(
    "/demo",
    summary="Demo screenshot (public, rate-limited)",
    description="Public demo endpoint for testing. No API key required. Limited to 5 requests per minute per IP.",
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/jpeg": {},
                "image/webp": {},
            },
            "description": "Screenshot image",
        },
        429: {
            "description": "Rate limit exceeded (5 req/min per IP)",
        },
    },
    tags=["demo"],
)
async def demo_screenshot(
    request: Request,
    url: str = Query(..., description="URL to capture", max_length=500),
    format: str = Query("jpeg", description="Output format (jpeg, png, webp)"),
    width: int = Query(1280, ge=320, le=1920, description="Viewport width (max 1920 for demo)"),
    height: int = Query(800, ge=240, le=1080, description="Viewport height (max 1080 for demo)"),
) -> Response:
    """
    Public demo endpoint for the landing page.

    **No API key required** - perfect for trying out the service.

    **Rate limits:**
    - 5 requests per minute per IP
    - Maximum viewport: 1920x1080
    - Always includes watermark

    **Example:**
    ```
    GET /api/v1/renders/demo?url=https://stripe.com
    ```
    """
    import time
    start_time = time.perf_counter()

    # Get client IP for rate limiting (Cloudflare chain: CF-Connecting-IP → X-Real-IP → host)
    client_ip = (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Real-IP") or
        (request.client.host if request.client else "unknown")
    )

    # Check IP-based rate limit (5 per minute)
    is_limited = await rate_limit_service.check_demo_rate_limit(client_ip)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Demo rate limit exceeded. Maximum 5 requests per minute.",
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )

    # Validate URL
    is_valid, error_message = validate_url(url, require_https=False)
    if not is_valid:
        raise ValidationError(error_message or "Invalid URL")

    # Clamp dimensions for demo
    width = min(width, 1920)
    height = min(height, 1080)

    # Build options (limited for demo)
    options = {
        "width": width,
        "height": height,
        "format": format if format in ("jpeg", "png", "webp") else "jpeg",
        "quality": 80,
        "full_page": False,  # Demo limited to viewport
        "delay": 0,
        "device_scale_factor": 1.0,
        "block_ads": True,
        "block_trackers": True,
        "block_cookie_banners": True,
    }

    # DEMO: No cache - always fresh render to show real performance
    # Render screenshot
    image_bytes, metadata = await render_service.capture_screenshot(
        url=url,
        options=options,
        user_plan={"watermark": True},  # Always apply watermark for demo
    )

    # Always apply watermark for demo
    image_bytes = render_service.inject_watermark(
        image_bytes,
        format=format,
    )

    # Increment demo usage counter
    await rate_limit_service.increment_demo_usage(client_ip)

    # Calculate elapsed time
    elapsed = time.perf_counter() - start_time

    # Log demo capture for analytics/admin dashboard
    try:
        await cache_service.log_demo_capture(
            ip=client_ip,
            url=url,
            render_time_ms=elapsed * 1000,
            metadata=metadata,
            user_agent=request.headers.get("User-Agent"),
            country=request.headers.get("CF-IPCountry"),
            referer=request.headers.get("Referer"),
        )
    except Exception as e:
        logger.warning("Failed to log demo capture", error=str(e))

    logger.info(
        "Demo screenshot rendered",
        url=url[:50],
        ip=client_ip,
        elapsed=f"{elapsed:.3f}s",
        size=len(image_bytes),
    )

    content_types = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }
    content_type = content_types.get(format, "image/jpeg")

    return Response(
        content=image_bytes,
        media_type=content_type,
        headers={
            "Content-Length": str(len(image_bytes)),
            "Cache-Control": "no-cache",  # Demo: no cache
            "X-Cache": "BYPASS",  # Demo bypasses cache
            "X-Render-Time": f"{elapsed:.3f}s",
            "X-Demo": "true",
        },
    )


# =============================================================================
# SIGNED URL ENDPOINTS - Frontend-safe screenshot URLs
# =============================================================================

@router.post(
    "/sign",
    summary="Generate signed URL",
    description="Generate a signed screenshot URL that can be used client-side without exposing API key.",
)
async def sign_screenshot_url(
    current_user: RateLimitedUser,
    url: str = Query(..., description="URL to capture"),
    width: int = Query(1920, ge=320, le=3840),
    height: int = Query(1080, ge=240, le=2160),
    format: str = Query("jpeg", description="Output format"),
    full_page: bool = Query(False),
    expires_in: int = Query(3600, ge=60, le=86400, description="Signature validity in seconds"),
) -> dict:
    """
    Generate a signed URL for frontend use.
    
    The generated URL can be used directly in img tags or fetch calls
    without needing to send the API key.
    """
    params = {
        "url": url,
        "width": width,
        "height": height,
        "format": format,
        "full_page": str(full_page).lower(),
        "api_key_id": str(current_user.api_key_id),
    }
    
    # Use API key as the signing secret
    signed_params = generate_signature(
        api_key=current_user.api_key,
        params=params,
        expires_in=expires_in,
    )
    
    # Build the signed URL
    base_url = f"{settings.API_BASE_URL}/api/v1/renders/signed"
    query_string = "&".join(f"{k}={v}" for k, v in signed_params.items())
    signed_url = f"{base_url}?{query_string}"
    
    return {
        "signed_url": signed_url,
        "expires_in": expires_in,
        "params": signed_params,
    }


@router.get(
    "/signed",
    summary="Signed screenshot (no API key required)",
    description="Capture a screenshot using a signed URL. No API key header needed.",
    responses={
        200: {"content": {"image/png": {}, "image/jpeg": {}, "image/webp": {}}},
    },
)
async def signed_screenshot(
    request: Request,
    db: DBSession,
    url: str = Query(..., description="URL to capture"),
    width: int = Query(1920, ge=320, le=3840),
    height: int = Query(1080, ge=240, le=2160),
    format: str = Query("jpeg"),
    full_page: str = Query("false"),
    api_key_id: str = Query(..., description="API key ID for verification"),
    expires: int = Query(..., description="Expiry timestamp"),
    signature: str = Query(..., description="HMAC signature"),
):
    """
    Take a screenshot using a signed URL.
    
    This endpoint doesn't require X-API-Key header - authentication
    is done via the signature parameter.
    """
    import time
    
    # Look up the API key by ID
    from app.models import APIKey
    api_key_record = await db.scalar(
        select(APIKey).where(APIKey.id == api_key_id)
    )
    
    if not api_key_record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not api_key_record.is_active:
        raise HTTPException(status_code=401, detail="API key is inactive")
    
    # Verify the signature
    params = {
        "url": url,
        "width": width,
        "height": height,
        "format": format,
        "full_page": full_page,
        "api_key_id": api_key_id,
        "expires": expires,
    }
    
    is_valid, error = verify_signature(
        params=params,
        signature=signature,
        api_key=api_key_record.key,
    )
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=f"Signature verification failed: {error}")
    
    # Process the screenshot
    start_time = time.perf_counter()
    
    options = {
        "width": width,
        "height": height,
        "format": format,
        "quality": 80,
        "full_page": full_page.lower() == "true",
        "device_scale_factor": 1.0,
        "delay": 0,
    }
    
    try:
        image_bytes, metadata = await render_service.capture_screenshot(
            url=url,
            options=options,
            user_plan=None,  # Signed requests use basic settings
        )
        
        # Apply watermark (signed URLs always get watermark unless pro)
        image_bytes = render_service.inject_watermark(
            image_bytes,
            format=format,
        )
        
        elapsed = time.perf_counter() - start_time
        logger.info(
            "Signed screenshot completed",
            url=url[:50],
            elapsed=f"{elapsed:.3f}s",
        )
        
        media_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }.get(format, "image/png")
        
        return Response(
            content=image_bytes,
            media_type=media_type,
            headers={
                "X-Processing-Time-Ms": str(metadata["processing_time_ms"]),
                "X-Signed-Request": "true",
            },
        )
        
    except Exception as e:
        logger.error("Signed screenshot failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FAST ENDPOINT - Returns image directly (like ScreenshotOne)
# =============================================================================

@router.get(
    "/take",
    summary="Take screenshot (direct image response)",
    description="Capture a screenshot and return the image directly. Fastest option.",
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/jpeg": {},
                "image/webp": {},
            },
            "description": "Screenshot image",
        }
    },
)
async def take_screenshot(
    request: Request,
    db: DBSession,
    # Source options (only one required)
    url: str | None = Query(None, description="URL to capture"),
    html: str | None = Query(None, description="HTML content to render"),
    markdown: str | None = Query(None, description="Markdown content to render"),
    # Viewport options
    format: str = Query("jpeg", description="Output format (png, jpeg, webp)"),
    width: int = Query(1920, ge=320, le=3840, description="Viewport width"),
    height: int = Query(1080, ge=240, le=2160, description="Viewport height"),
    quality: int = Query(80, ge=1, le=100, description="Image quality (jpeg/webp)"),
    response_type: str = Query("binary", description="Response type: 'binary' or 'json'"),
    full_page: bool = Query(False, description="Capture full page"),
    capture_beyond_viewport: bool = Query(True, description="Capture content beyond viewport"),
    delay: int = Query(0, ge=0, le=10000, description="Delay before capture (ms)"),
    # Selector options
    selector: str | None = Query(None, description="CSS selector to capture specific element"),
    scroll_into_view: str | None = Query(None, description="CSS selector to scroll into view"),
    scroll_adjust_top: int = Query(0, ge=-1000, le=1000, description="Pixel offset after scroll"),
    # Blocking options
    block_ads: bool = Query(True, description="Block ads"),
    block_trackers: bool = Query(True, description="Block trackers"),
    block_cookie_banners: bool = Query(True, description="Block cookie banners"),
    # Auth options - multiple methods supported
    access_key: str | None = Query(None, description="API key (alternative to X-API-Key header)"),
    signature: str | None = Query(None, description="Request signature (for signed URLs)"),
    expires: int | None = Query(None, description="Signature expiry timestamp"),
) -> Response:
    """
    Take a screenshot and return the image directly.

    **This is the fastest endpoint** - no S3 upload, no JSON response.
    Just pure image data returned directly.

    **Authentication (choose one):**
    - Header: `X-API-Key: sk_live_xxx`
    - Query: `?access_key=sk_live_xxx`
    - Signed: `?signature=xxx&expires=123` (no API key needed)

    **Source options (one required):**
    - `url`: URL to capture
    - `html`: HTML content to render directly
    - `markdown`: Markdown content to render

    **Selector options:**
    - `selector`: CSS selector to capture specific element
    - `scroll_into_view`: Scroll to this element before capture
    - `scroll_adjust_top`: Pixel offset after scrolling

    **Example:**
    ```
    GET /api/v1/renders/take?url=https://stripe.com&format=jpeg&quality=80
    GET /api/v1/renders/take?access_key=sk_xxx&url=https://stripe.com
    GET /api/v1/renders/take?url=https://stripe.com&signature=abc&expires=123
    ```

    Returns: Binary image data with appropriate Content-Type header.
    """
    import time
    from app.models import APIKey
    from app.utils.exceptions import RenderError
    
    start_time = time.perf_counter()
    
    # =========================================================================
    # AUTHENTICATION - Dual-Key System (ScreenshotOne Parity)
    # =========================================================================
    from app.utils.signature import verify_signature
    from app.services.api_key_service import get_secret_key
    
    api_key_record = None
    user_plan = None
    user_id = None
    
    # Method 1: X-API-Key header (legacy single-key or new secret key for server-to-server)
    header_key = request.headers.get("X-API-Key")
    
    # Method 2: access_key query param (new dual-key public identifier)
    query_key = access_key
    
    # Determine which key we have
    key_to_lookup = header_key or query_key
    
    if key_to_lookup:
        # Try new dual-key system first (access_key lookup)
        # Supports both old "ak_xxx" prefix and new prefix-less format
        api_key_record = await db.scalar(
            select(APIKey).where(
                APIKey.access_key == key_to_lookup,
                APIKey.is_active == True,
            )
        )
        
        if api_key_record:
            
            # Check signature enforcement
            if api_key_record.enforce_signing:
                if not signature:
                    raise HTTPException(
                        status_code=403,
                        detail="Signature required. This key has signing enforcement enabled."
                    )
                
                # Verify signature using secret key
                try:
                    secret = await get_secret_key(api_key_record)
                    params_to_verify = {
                        "access_key": key_to_lookup,
                        "url": url or "",
                        "width": width,
                        "height": height,
                        "format": format,
                        "full_page": str(full_page).lower(),
                        "expires": expires,
                    }
                    is_valid, error = verify_signature(params_to_verify, signature, secret)
                    if not is_valid:
                        raise HTTPException(status_code=401, detail=f"Invalid signature: {error}")
                except ValueError as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            elif signature and expires:
                # Optional signature verification (not enforced but provided)
                try:
                    secret = await get_secret_key(api_key_record)
                    params_to_verify = {
                        "access_key": key_to_lookup,
                        "url": url or "",
                        "width": width,
                        "height": height,
                        "format": format,
                        "full_page": str(full_page).lower(),
                        "expires": expires,
                    }
                    is_valid, error = verify_signature(params_to_verify, signature, secret)
                    if not is_valid:
                        logger.warning("Optional signature verification failed", error=error)
                except Exception as e:
                    logger.warning("Optional signature verification error", error=str(e))
        
        # If not found by access_key, try legacy key_hash lookup
        if not api_key_record:
            import hashlib
            key_hash = hashlib.sha256(key_to_lookup.encode()).hexdigest()
            api_key_record = await db.scalar(
                select(APIKey).where(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == True,
                )
            )
            
            if api_key_record:
                logger.warning("Legacy API key used", key_prefix=key_to_lookup[:12] if len(key_to_lookup) > 12 else key_to_lookup)
        
        # If still not found, raise error
        if not api_key_record:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if not api_key_record.is_active:
            raise HTTPException(status_code=401, detail="API key is inactive")
        
        user_id = api_key_record.user_id
        user_plan = api_key_record.user.plan_features if hasattr(api_key_record, 'user') and api_key_record.user else {}
        
        # Update last used timestamp (fire and forget)
        api_key_record.last_used_at = datetime.utcnow()
        
    else:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use X-API-Key header or access_key param."
        )

    # Validate source - at least one required
    sources = [url, html, markdown]
    provided = [s for s in sources if s is not None]
    if len(provided) == 0:
        raise ValidationError("At least one source required: url, html, or markdown")
    if len(provided) > 1:
        raise ValidationError("Only one source allowed: url, html, or markdown")

    # Validate URL if provided
    if url:
        is_valid, error_message = validate_url(url, require_https=False)
        if not is_valid:
            raise ValidationError(error_message or "Invalid URL")

    # Build options
    options = {
        "width": width,
        "height": height,
        "format": format,
        "quality": quality,
        "full_page": full_page,
        "delay": delay,
        "device_scale_factor": 1.0,  # Fast mode
        "block_ads": block_ads,
        "block_trackers": block_trackers,
        "block_cookie_banners": block_cookie_banners,
        # New Essentials options
        "html": html or "",
        "markdown": markdown or "",
        "selector": selector or "",
        "scroll_into_view": scroll_into_view or "",
        "scroll_adjust_top": scroll_adjust_top,
        "capture_beyond_viewport": capture_beyond_viewport,
    }

    # =========================================================================
    # CACHE CHECK - Return instantly if cached
    # =========================================================================
    try:
        cached = await cache_service.get_screenshot_cache(url, options)
        if cached:
            image_bytes, metadata = cached
            elapsed = time.perf_counter() - start_time
            logger.info(
                "Screenshot served from cache",
                url=url[:50],
                elapsed=f"{elapsed:.3f}s",
                size=len(image_bytes),
            )

            # Determine content type
            content_types = {
                "png": "image/png",
                "jpeg": "image/jpeg",
                "webp": "image/webp",
            }
            content_type = content_types.get(format, "image/png")

            return Response(
                content=image_bytes,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "X-Cache": "HIT",
                    "X-Render-Time": f"{elapsed:.3f}s",
                },
            )
    except Exception as e:
        logger.warning("Cache check failed", error=str(e))

    # =========================================================================
    # RENDER - Capture new screenshot
    # =========================================================================
    try:
        image_bytes, metadata = await render_service.capture_screenshot(
            url=url,
            options=options,
            user_plan=user_plan,
        )
    except RenderError as e:
        logger.warning("Render failed", url=url, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected render error", url=url, error=str(e))
        raise HTTPException(status_code=500, detail="Internal Render Error")

    # Apply watermark for free tier
    if user_plan.get("watermark", True) if user_plan else True:
        image_bytes = render_service.inject_watermark(
            image_bytes,
            format=format,
        )

    # =========================================================================
    # CACHE SET - Store for future requests
    # =========================================================================
    try:
        await cache_service.set_screenshot_cache(
            url=url,
            options=options,
            image_bytes=image_bytes,
            metadata=metadata,
            ttl=3600,  # 1 hour cache
        )
    except Exception as e:
        logger.warning("Cache set failed", error=str(e))

    # Increment usage
    if user_id:
        await rate_limit_service.increment_usage(user_id)

    elapsed = time.perf_counter() - start_time
    logger.info(
        "Screenshot rendered",
        url=url[:50],
        elapsed=f"{elapsed:.3f}s",
        size=len(image_bytes),
    )

    # =========================================================================
    # RESPONSE HANDLING - Binary vs JSON
    # =========================================================================
    
    # 1. Binary mode (Default) - Return image directly
    if response_type == "binary":
        # Determine content type
        content_types = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "webp": "image/webp",
        }
        content_type = content_types.get(format, "image/png")

        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={
                "Content-Length": str(len(image_bytes)),
                "Cache-Control": "public, max-age=3600",
                "X-Cache": "MISS",
                "X-Render-Time": f"{elapsed:.3f}s",
                "X-Processing-Time-Ms": str(metadata.get("processing_time_ms", 0)),
                "X-Image-Width": str(metadata.get("width", 0)),
                "X-Image-Height": str(metadata.get("height", 0)),
            },
        )
        
    # 2. JSON mode - Upload to S3 and return metadata
    try:
        # Generate temporary job ID for upload path (even though we don't save to DB)
        temp_job_id = str(uuid4())
        
        # Upload to S3
        upload_result = await storage_service.upload_render(
            file_bytes=image_bytes,
            user_id=str(user_id) if user_id else "anonymous",
            job_id=temp_job_id,
            file_type=options.get("format", "png"),
        )
        
        # Cache the result (optional, but good practice)
        if url:
            try:
                await cache_service.set_render_cache(
                    url=url,
                    options=options,
                    data={
                        "s3_key": upload_result["s3_key"],
                        "s3_url": upload_result["s3_url"],
                        "file_size": upload_result["file_size"],
                        "metadata": metadata,
                    },
                    ttl=3600,
                )
            except Exception as e:
                logger.warning("Cache set (JSON) failed", error=str(e))

        return {
            "url": upload_result["s3_url"],
            "screenshot_url": upload_result["s3_url"], # Alias for compatibility
            "width": metadata.get("width", 0),
            "height": metadata.get("height", 0),
            "format": options.get("format", "png"),
            "size": upload_result["file_size"],
            "processing_time_ms": metadata.get("processing_time_ms", 0),
            "captured_at": metadata.get("captured_at"),
            "status": "completed"
        }
        
    except Exception as e:
        logger.error("JSON response generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate JSON response: {str(e)}")


@router.post(
    "/screenshot",
    response_model=Union[ScreenshotResponse, RenderJobAsyncResponse],
    status_code=status.HTTP_200_OK,
    summary="Create screenshot",
    description="Capture a screenshot of a URL.",
)
async def create_screenshot(
    request: ScreenshotRequest,
    current_user: RateLimitedUser,
    db: DBSession,
) -> ScreenshotResponse | RenderJobAsyncResponse:
    """
    Create a screenshot.

    **Requires API key authentication (X-API-Key header).**

    - **url**: URL to capture (HTTPS recommended)
    - **async**: Process asynchronously (default: false)
    - **width/height**: Viewport dimensions
    - **format**: Output format (png, jpeg, webp)
    - **full_page**: Capture full scrollable page
    - **delay**: Wait time before capture (ms)
    """
    # Validate source - URL only if provided
    if request.url:
        is_valid, error_message = validate_url(request.url, require_https=False)
        if not is_valid:
            raise ValidationError(error_message or "Invalid URL")

    # Check feature availability based on plan
    if request.custom_css and not current_user.has_feature("custom_css"):
        raise ValidationError(
            "Custom CSS is not available in your plan",
            details={"feature": "custom_css", "requires": "pro"},
        )

    if request.element_selector and not current_user.has_feature("element_selector"):
        raise ValidationError(
            "Element selector is not available in your plan",
            details={"feature": "element_selector", "requires": "pro"},
        )

    if request.geolocation and not current_user.has_feature("geolocation"):
        raise ValidationError(
            "Geolocation is not available in your plan",
            details={"feature": "geolocation", "requires": "pro"},
        )

    if request.full_page and not current_user.has_feature("full_page"):
        raise ValidationError(
            "Full page capture is not available in your plan",
            details={"feature": "full_page", "requires": "starter"},
        )

    # Build options dict with Essentials features
    options = {
        "width": request.width,
        "height": request.height,
        "format": request.format,
        "quality": request.quality,
        "full_page": request.full_page,
        "device_scale_factor": request.device_scale_factor,
        "delay": request.delay,
        "wait_until": request.wait_until,
        "custom_css": request.custom_css,
        "element_selector": request.element_selector,
        "remove_elements": request.remove_elements,
        "geolocation": request.geolocation,
        "user_agent": request.user_agent,
        "extra_http_headers": request.extra_http_headers,
        "authentication": request.authentication,
        "device": request.device,
        # Essentials features
        "html": request.html,
        "markdown": request.markdown,
        "selector": request.selector,
        "scroll_into_view": request.scroll_into_view,
        "scroll_adjust_top": request.scroll_adjust_top,
        "response_type": request.response_type,
    }

    # Determine source label for job record
    source_label = request.url or (
        "[HTML]" if request.html else ("[Markdown]" if request.markdown else "[Unknown]")
    )

    # Create render job record
    render_job = RenderJob(
        user_id=current_user.user_id,
        api_key_id=current_user.api_key_id,
        type="screenshot",
        status="pending",
        url=source_label,
        options=options,
        webhook_url=request.webhook_url,
        priority=_get_priority(current_user.plan_name),
        expires_at=storage_service.calculate_expiry_date(),
    )

    db.add(render_job)
    await db.commit()
    await db.refresh(render_job)

    # Async mode - queue job and return immediately
    if request.async_mode:
        # Queue the job to Celery
        queue = "high_priority" if _get_priority(current_user.plan_name) >= 3 else "default"
        process_screenshot.apply_async(
            args=[str(render_job.id)],
            queue=queue,
        )

        return RenderJobAsyncResponse(
            job_id=render_job.id,
            status="pending",
            message="Job queued successfully",
            webhook_url=request.webhook_url,
            check_url=f"/api/v1/renders/jobs/{render_job.id}",
        )

    # Sync mode - process immediately
    import time
    start_time = time.perf_counter()

    try:
        render_job.status = "processing"
        render_job.started_at = utc_now()
        await db.commit()

        # =====================================================================
        # CACHE CHECK - Return cached result if available
        # =====================================================================
        cache_options = {
            "width": options["width"],
            "height": options["height"],
            "format": options["format"],
            "quality": options["quality"],
            "full_page": options["full_page"],
            "device_scale_factor": options["device_scale_factor"],
        }

        try:
            # Only check cache for URL-based requests
            cached_result = None
            if request.url:
                cached_result = await cache_service.get_render_cache(request.url, cache_options)
            if cached_result:
                elapsed = time.perf_counter() - start_time
                logger.info(
                    "Screenshot served from S3 cache",
                    url=source_label[:50],
                    elapsed=f"{elapsed:.3f}s",
                )

                # Update job with cached data
                render_job.status = "completed"
                render_job.completed_at = utc_now()
                render_job.s3_key = cached_result["s3_key"]
                render_job.s3_url = cached_result["s3_url"]
                render_job.file_size_bytes = cached_result["file_size"]
                render_job.processing_time_ms = int(elapsed * 1000)
                render_job.result = cached_result.get("metadata", {})
                await db.commit()

                return ScreenshotResponse(
                    url=cached_result["s3_url"],
                    screenshot_url=cached_result["s3_url"],
                    width=cached_result.get("metadata", {}).get("width", options["width"]),
                    height=cached_result.get("metadata", {}).get("height", options["height"]),
                    format=options.get("format", "png"),
                    file_size=cached_result["file_size"],
                    processing_time_ms=int(elapsed * 1000),
                    status="completed",
                )
        except Exception as e:
            logger.warning("Cache check failed", error=str(e))

        # =====================================================================
        # RENDER - Capture new screenshot
        # =====================================================================
        image_bytes, metadata = await render_service.capture_screenshot(
            url=request.url or "",  # Empty string if HTML/Markdown
            options=options,
            user_plan=current_user.plan_features,
        )

        # Apply watermark for free tier
        if current_user.plan_features.get("watermark", True):
            image_bytes = render_service.inject_watermark(
                image_bytes,
                format=options.get("format", "png"),
            )

        # =====================================================================
        # BINARY RESPONSE MODE - Return raw image bytes directly
        # =====================================================================
        if request.response_type == "binary":
            # Return image directly without S3 upload
            media_type = {
                "png": "image/png",
                "jpeg": "image/jpeg",
                "jpg": "image/jpeg",
                "webp": "image/webp",
            }.get(options.get("format", "png"), "image/png")

            # Update job as completed (for tracking)
            render_job.status = "completed"
            render_job.completed_at = utc_now()
            render_job.file_size_bytes = len(image_bytes)
            render_job.processing_time_ms = metadata["processing_time_ms"]
            render_job.result = metadata
            await db.commit()

            # Increment usage
            await rate_limit_service.increment_usage(current_user.user_id)

            elapsed = time.perf_counter() - start_time
            logger.info(
                "Screenshot endpoint completed (binary)",
                url=source_label[:50],
                elapsed=f"{elapsed:.3f}s",
                size=len(image_bytes),
            )

            return Response(
                content=image_bytes,
                media_type=media_type,
                headers={
                    "X-Processing-Time-Ms": str(metadata["processing_time_ms"]),
                    "X-Image-Width": str(metadata["width"]),
                    "X-Image-Height": str(metadata["height"]),
                    "Content-Length": str(len(image_bytes)),
                },
            )

        # Upload to S3
        upload_result = await storage_service.upload_render(
            file_bytes=image_bytes,
            user_id=str(current_user.user_id),
            job_id=str(render_job.id),
            file_type=options.get("format", "png"),
        )

        # Use direct S3 URL (files are public-read)
        download_url = upload_result["s3_url"]

        # =====================================================================
        # CACHE SET - Store for future requests
        # =====================================================================
        try:
            # Only cache URL-based requests
            if request.url:
                await cache_service.set_render_cache(
                    url=request.url,
                    options=cache_options,
                data={
                    "s3_key": upload_result["s3_key"],
                    "s3_url": upload_result["s3_url"],
                    "file_size": upload_result["file_size"],
                    "metadata": metadata,
                },
                ttl=3600,  # 1 hour cache
            )
        except Exception as e:
            logger.warning("Cache set failed", error=str(e))

        # Update job
        render_job.status = "completed"
        render_job.completed_at = utc_now()
        render_job.s3_key = upload_result["s3_key"]
        render_job.s3_url = upload_result["s3_url"]
        render_job.file_size_bytes = upload_result["file_size"]
        render_job.processing_time_ms = metadata["processing_time_ms"]
        render_job.result = metadata

        await db.commit()

        # Increment usage
        await rate_limit_service.increment_usage(current_user.user_id)

        elapsed = time.perf_counter() - start_time
        logger.info(
            "Screenshot endpoint completed",
            url=source_label[:50],
            elapsed=f"{elapsed:.3f}s",
            size=upload_result["file_size"],
        )

        # Return minimal developer-friendly response (ScreenshotOne compatible)
        return ScreenshotResponse(
            url=download_url,
            screenshot_url=download_url,  # Alias for ScreenshotOne compatibility
            width=metadata["width"],
            height=metadata["height"],
            format=options.get("format", "png"),
            file_size=upload_result["file_size"],
            processing_time_ms=metadata["processing_time_ms"],
            status="completed",
        )

    except Exception as e:
        render_job.status = "failed"
        render_job.error_message = str(e)
        render_job.completed_at = utc_now()
        await db.commit()
        raise


@router.post(
    "/pdf",
    response_model=Union[RenderJobResponse, RenderJobAsyncResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate PDF",
    description="Generate a PDF from a URL.",
)
async def create_pdf(
    request: PDFRequest,
    current_user: RateLimitedUser,
    db: DBSession,
) -> RenderJobResponse | RenderJobAsyncResponse:
    """
    Generate a PDF.

    **Requires API key authentication (X-API-Key header).**

    - **url**: URL to render
    - **async**: Process asynchronously (default: false)
    - **format**: Page format (A4, Letter, Legal, Tabloid)
    - **landscape**: Landscape orientation
    - **print_background**: Print background graphics
    """
    # Validate URL
    is_valid, error_message = validate_url(request.url, require_https=False)
    if not is_valid:
        raise ValidationError(error_message or "Invalid URL")

    # Build options dict
    options = {
        "format": request.format,
        "landscape": request.landscape,
        "print_background": request.print_background,
        "scale": request.scale,
        "margin": request.margin,
        "page_ranges": request.page_ranges,
        "header_template": request.header_template,
        "footer_template": request.footer_template,
        "prefer_css_page_size": request.prefer_css_page_size,
        "delay": request.delay,
        "wait_until": request.wait_until,
    }

    # Create render job record
    render_job = RenderJob(
        user_id=current_user.user_id,
        api_key_id=current_user.api_key_id,
        type="pdf",
        status="pending",
        url=request.url,
        options=options,
        webhook_url=request.webhook_url,
        priority=_get_priority(current_user.plan_name),
        expires_at=storage_service.calculate_expiry_date(),
    )

    db.add(render_job)
    await db.commit()
    await db.refresh(render_job)

    # Async mode
    if request.async_mode:
        # Queue the job to Celery
        queue = "high_priority" if _get_priority(current_user.plan_name) >= 3 else "default"
        process_pdf.apply_async(
            args=[str(render_job.id)],
            queue=queue,
        )

        return RenderJobAsyncResponse(
            job_id=render_job.id,
            status="pending",
            message="Job queued successfully",
            webhook_url=request.webhook_url,
            check_url=f"/api/v1/renders/jobs/{render_job.id}",
        )

    # Sync mode
    try:
        render_job.status = "processing"
        render_job.started_at = utc_now()
        await db.commit()

        # Generate PDF
        pdf_bytes, metadata = await render_service.generate_pdf(
            url=request.url,
            options=options,
            user_plan=current_user.plan_features,
        )

        # Upload to S3
        upload_result = await storage_service.upload_render(
            file_bytes=pdf_bytes,
            user_id=str(current_user.user_id),
            job_id=str(render_job.id),
            file_type="pdf",
        )

        # Generate presigned URL
        download_url = await storage_service.generate_download_url(
            upload_result["s3_key"]
        )

        # Update job
        render_job.status = "completed"
        render_job.completed_at = utc_now()
        render_job.s3_key = upload_result["s3_key"]
        render_job.s3_url = upload_result["s3_url"]
        render_job.file_size_bytes = upload_result["file_size"]
        render_job.processing_time_ms = metadata["processing_time_ms"]
        render_job.result = metadata

        await db.commit()

        # Increment usage
        await rate_limit_service.increment_usage(current_user.user_id)

        return RenderJobResponse(
            job_id=render_job.id,
            type="pdf",
            status="completed",
            url=download_url,
            format="pdf",
            file_size=upload_result["file_size"],
            page_count=metadata.get("page_count"),
            processing_time_ms=metadata["processing_time_ms"],
            cached=False,
            created_at=render_job.created_at,
            started_at=render_job.started_at,
            completed_at=render_job.completed_at,
            expires_at=render_job.expires_at,
        )

    except Exception as e:
        render_job.status = "failed"
        render_job.error_message = str(e)
        render_job.completed_at = utc_now()
        await db.commit()
        raise


@router.get(
    "/jobs/{job_id}",
    response_model=RenderJobResponse,
    summary="Get job status",
    description="Get the status and details of a render job.",
)
async def get_job(
    job_id: UUID,
    current_user: RateLimitedUser,
    db: DBSession,
) -> RenderJobResponse:
    """
    Get render job status.

    **Requires API key authentication.**

    - **job_id**: UUID of the render job
    """
    result = await db.execute(
        select(RenderJob).where(
            RenderJob.id == job_id,
            RenderJob.user_id == current_user.user_id,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(
            "Job not found",
            resource_type="render_job",
            resource_id=str(job_id),
        )

    # Generate presigned URL if completed
    download_url = None
    if job.status == "completed" and job.s3_key:
        download_url = await storage_service.generate_download_url(job.s3_key)

    # Build size info
    size_info = None
    if job.result and job.type == "screenshot":
        size_info = SizeInfo(
            width=job.result.get("width", 0),
            height=job.result.get("height", 0),
        )

    return RenderJobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status,
        url=download_url,
        format=job.options.get("format"),
        size=size_info,
        file_size=job.file_size_bytes,
        page_count=job.result.get("page_count") if job.result else None,
        processing_time_ms=job.processing_time_ms,
        error_message=job.error_message,
        options=job.options,
        result=job.result,
        webhook_url=job.webhook_url,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        expires_at=job.expires_at,
    )


@router.get(
    "/jobs",
    response_model=RenderJobsListResponse,
    summary="List jobs",
    description="List render jobs for the authenticated user.",
)
async def list_jobs(
    current_user: RateLimitedUser,
    db: DBSession,
    status: str | None = Query(None, description="Filter by status"),
    type: str | None = Query(None, description="Filter by type (screenshot/pdf)"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
) -> RenderJobsListResponse:
    """
    List render jobs.

    **Requires API key authentication.**

    Supports filtering and pagination.
    """
    # Build query
    query = select(RenderJob).where(RenderJob.user_id == current_user.user_id)

    if status:
        query = query.where(RenderJob.status == status)

    if type:
        query = query.where(RenderJob.type == type)

    # Count total
    count_query = select(func.count(RenderJob.id)).where(
        RenderJob.user_id == current_user.user_id
    )
    if status:
        count_query = count_query.where(RenderJob.status == status)
    if type:
        count_query = count_query.where(RenderJob.type == type)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(RenderJob, sort, RenderJob.created_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Apply pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Build response
    job_responses = []
    for job in jobs:
        download_url = None
        if job.status == "completed" and job.s3_key:
            download_url = await storage_service.generate_download_url(job.s3_key)

        size_info = None
        if job.result and job.type == "screenshot":
            size_info = SizeInfo(
                width=job.result.get("width", 0),
                height=job.result.get("height", 0),
            )

        job_responses.append(
            RenderJobResponse(
                job_id=job.id,
                type=job.type,
                status=job.status,
                url=download_url,
                format=job.options.get("format"),
                size=size_info,
                file_size=job.file_size_bytes,
                page_count=job.result.get("page_count") if job.result else None,
                processing_time_ms=job.processing_time_ms,
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                expires_at=job.expires_at,
            )
        )

    return RenderJobsListResponse(
        jobs=job_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete job",
    description="Delete a render job and its associated file.",
)
async def delete_job(
    job_id: UUID,
    current_user: RateLimitedUser,
    db: DBSession,
) -> None:
    """
    Delete a render job.

    **Requires API key authentication.**

    Cancels pending jobs and deletes completed job files from S3.
    """
    result = await db.execute(
        select(RenderJob).where(
            RenderJob.id == job_id,
            RenderJob.user_id == current_user.user_id,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(
            "Job not found",
            resource_type="render_job",
            resource_id=str(job_id),
        )

    # Delete S3 file if exists
    if job.s3_key:
        await storage_service.delete_file(job.s3_key)

    # Delete job record
    await db.delete(job)
    await db.commit()


def _get_priority(plan_name: str) -> int:
    """Get job priority based on plan."""
    priorities = {
        "business": 10,
        "pro": 8,
        "starter": 5,
        "free": 1,
    }
    return priorities.get(plan_name, 1)
