"""
Screenshot and PDF rendering endpoints
"""

from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    DBSession,
    RateLimitedUser,
    check_rate_limit,
    get_current_user_from_api_key,
)
from app.models import RenderJob
from app.workers.render_tasks import process_screenshot, process_pdf
from app.schemas.render import (
    PDFRequest,
    RenderJobAsyncResponse,
    RenderJobResponse,
    RenderJobsListResponse,
    ScreenshotRequest,
    SizeInfo,
)
from app.services.rate_limit_service import rate_limit_service
from app.services.render_service import render_service
from app.services.storage_service import storage_service
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.helpers import utc_now
from app.utils.validators import validate_url

router = APIRouter()


@router.post(
    "/screenshot",
    response_model=Union[RenderJobResponse, RenderJobAsyncResponse],
    status_code=status.HTTP_200_OK,
    summary="Create screenshot",
    description="Capture a screenshot of a URL.",
)
async def create_screenshot(
    request: ScreenshotRequest,
    current_user: RateLimitedUser,
    db: DBSession,
) -> Union[RenderJobResponse, RenderJobAsyncResponse]:
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
    # Validate URL
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

    # Build options dict
    options = {
        "width": request.width,
        "height": request.height,
        "format": request.format,
        "quality": request.quality,
        "full_page": request.full_page,
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
    }

    # Create render job record
    render_job = RenderJob(
        user_id=current_user.user_id,
        api_key_id=current_user.api_key_id,
        type="screenshot",
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
            check_url=f"/api/v1/render/jobs/{render_job.id}",
        )

    # Sync mode - process immediately
    try:
        render_job.status = "processing"
        render_job.started_at = utc_now()
        await db.commit()

        # Capture screenshot
        image_bytes, metadata = await render_service.capture_screenshot(
            url=request.url,
            options=options,
            user_plan=current_user.plan_features,
        )

        # Apply watermark for free tier
        if current_user.plan_features.get("watermark", True):
            image_bytes = render_service.inject_watermark(
                image_bytes,
                format=options.get("format", "png"),
            )

        # Upload to S3
        upload_result = await storage_service.upload_render(
            file_bytes=image_bytes,
            user_id=str(current_user.user_id),
            job_id=str(render_job.id),
            file_type=options.get("format", "png"),
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
            type="screenshot",
            status="completed",
            url=download_url,
            format=options.get("format", "png"),
            size=SizeInfo(width=metadata["width"], height=metadata["height"]),
            file_size=upload_result["file_size"],
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
) -> Union[RenderJobResponse, RenderJobAsyncResponse]:
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
            check_url=f"/api/v1/render/jobs/{render_job.id}",
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
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, description="Filter by type (screenshot/pdf)"),
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
