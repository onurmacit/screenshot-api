"""
Go Render Client

HTTP client for communicating with the Go rendering microservice.
Replaces local Playwright rendering with Go renderer calls.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from PIL import Image
import io

from app.core.config import settings
from app.utils.exceptions import RenderError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GoRenderClient:
    """
    HTTP client for the Go rendering microservice.
    
    Replaces the Playwright-based RenderService with HTTP calls to the Go renderer.
    """

    def __init__(self):
        self.base_url = settings.GO_RENDERER_URL
        self.timeout = settings.GO_RENDERER_TIMEOUT

    async def capture_screenshot(
        self,
        url: str,
        options: dict[str, Any],
        user_plan: dict | None = None,
        _retry_count: int = 0,
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Capture a screenshot by calling the Go renderer microservice.

        Args:
            url: Target URL
            options: Screenshot options
            user_plan: User's plan features (used for watermark decision)
            _retry_count: Internal retry counter

        Returns:
            Tuple of (image_bytes, metadata)

        Raises:
            RenderError: If screenshot capture fails
        """
        start_time = datetime.now(UTC)
        
        # Build request payload
        payload = {
            "url": url,
            "width": options.get("width", 1920),
            "height": options.get("height", 1080),
            "format": options.get("format", "jpeg"),
            "quality": options.get("quality", 80),
            "full_page": options.get("full_page", False),
            "delay": options.get("delay", 0),
            "device_scale_factor": options.get("device_scale_factor", 1.0),
            "block_ads": options.get("block_ads", True),
            "block_trackers": options.get("block_trackers", True),
            "block_cookie_banners": options.get("block_cookie_banners", True),
            "user_agent": options.get("user_agent", ""),
            "selector": options.get("selector", ""),
            "scroll_into_view": options.get("scroll_into_view", ""),
            "scroll_adjust_top": options.get("scroll_adjust_top", 0),
            "html": options.get("html", ""),
            "markdown": options.get("markdown", ""),
            "timeout": options.get("timeout", 30000),
            "return_base64": False,  # Get binary for efficiency
        }

        try:
            timeout_config = httpx.Timeout(float(self.timeout), connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(
                    f"{self.base_url}/render/screenshot",
                    json=payload,
                )

                if response.status_code != 200:
                    error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                    raise RenderError(
                        f"Go renderer returned {response.status_code}: {error_data.get('message', 'Unknown error')}",
                        details=error_data,
                    )

                image_bytes = response.content
                
                # Get metadata from headers
                processing_time_ms = int(response.headers.get("X-Processing-Time-Ms", "0") or "0")
                
                # Calculate actual dimensions from image
                width = payload["width"]
                height = payload["height"]
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    width, height = img.size
                except Exception:
                    pass

                elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                metadata = {
                    "width": width,
                    "height": height,
                    "processing_time_ms": processing_time_ms or elapsed_ms,
                    "format": payload["format"],
                    "source": "go-renderer",
                }

                logger.info(
                    "Screenshot captured via Go renderer",
                    url=url[:50] if url else "[HTML]",
                    processing_time_ms=metadata["processing_time_ms"],
                    size=len(image_bytes),
                )

                return image_bytes, metadata

        except httpx.TimeoutException as e:
            logger.error("Go renderer timeout", url=url[:50] if url else "[HTML]", error=str(e))
            raise RenderError(f"Go renderer timeout: {str(e)}")
        except httpx.RequestError as e:
            logger.error("Go renderer connection error", url=url[:50] if url else "[HTML]", error=str(e))
            
            # Retry logic
            if _retry_count < 2:
                logger.warning("Retrying Go renderer request", retry=_retry_count + 1)
                await asyncio.sleep(1)
                return await self.capture_screenshot(url, options, user_plan, _retry_count + 1)
            
            raise RenderError(f"Go renderer connection failed: {str(e)}")
        except Exception as e:
            logger.exception("Go renderer error", url=url[:50] if url else "[HTML]", error=str(e))
            raise RenderError(f"Go renderer error: {str(e)}")

    async def generate_pdf(
        self,
        url: str,
        options: dict[str, Any],
        user_plan: dict | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Generate a PDF by calling the Go renderer microservice.

        Args:
            url: Target URL
            options: PDF options
            user_plan: User's plan features

        Returns:
            Tuple of (pdf_bytes, metadata)

        Raises:
            RenderError: If PDF generation fails
        """
        start_time = datetime.now(UTC)

        # Build request payload
        payload = {
            "url": url,
            "format": options.get("format", "A4"),
            "landscape": options.get("landscape", False),
            "print_background": options.get("print_background", True),
            "scale": options.get("scale", 1.0),
            "delay": options.get("delay", 0),
            "timeout": options.get("timeout", 30000),
            "return_base64": False,
        }

        try:
            timeout_config = httpx.Timeout(float(self.timeout), connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(
                    f"{self.base_url}/render/pdf",
                    json=payload,
                )

                if response.status_code != 200:
                    error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                    raise RenderError(
                        f"Go renderer returned {response.status_code}: {error_data.get('message', 'Unknown error')}",
                        details=error_data,
                    )

                pdf_bytes = response.content
                
                processing_time_ms = int(response.headers.get("X-Processing-Time-Ms", "0") or "0")
                page_count = int(response.headers.get("X-Page-Count", "1") or "1")
                
                elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                metadata = {
                    "page_count": page_count,
                    "processing_time_ms": processing_time_ms or elapsed_ms,
                    "format": payload["format"],
                    "source": "go-renderer",
                }

                logger.info(
                    "PDF generated via Go renderer",
                    url=url[:50],
                    processing_time_ms=metadata["processing_time_ms"],
                    size=len(pdf_bytes),
                )

                return pdf_bytes, metadata

        except httpx.TimeoutException as e:
            logger.error("Go renderer PDF timeout", url=url[:50], error=str(e))
            raise RenderError(f"Go renderer timeout: {str(e)}")
        except httpx.RequestError as e:
            logger.error("Go renderer PDF connection error", url=url[:50], error=str(e))
            raise RenderError(f"Go renderer connection failed: {str(e)}")
        except Exception as e:
            logger.exception("Go renderer PDF error", url=url[:50], error=str(e))
            raise RenderError(f"Go renderer error: {str(e)}")

    def inject_watermark(
        self,
        image_bytes: bytes,
        format: str = "png",
    ) -> bytes:
        """
        Inject a watermark into the image for free tier users.
        
        This runs locally in Python since it's a lightweight operation.

        Args:
            image_bytes: Original image bytes
            format: Image format (png, jpeg, webp)

        Returns:
            Image bytes with watermark
        """
        try:
            # Open image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Create watermark text
            from PIL import ImageDraw, ImageFont
            
            draw = ImageDraw.Draw(img)
            
            # Try to get a font, fallback to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except Exception:
                try:
                    font = ImageFont.truetype("arial.ttf", 24)
                except Exception:
                    font = ImageFont.load_default()
            
            text = "ScreenshotBeam.com"
            
            # Get text size
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Position at bottom-right with padding
            x = img.width - text_width - 20
            y = img.height - text_height - 20
            
            # Draw shadow
            draw.text((x + 2, y + 2), text, fill=(0, 0, 0, 128), font=font)
            # Draw text
            draw.text((x, y), text, fill=(255, 255, 255, 200), font=font)
            
            # Save to bytes
            output = io.BytesIO()
            save_format = format.upper()
            if save_format == "JPEG":
                img = img.convert("RGB")  # Remove alpha for JPEG
            img.save(output, format=save_format if save_format != "WEBP" else "WebP", quality=90)
            
            return output.getvalue()
            
        except Exception as e:
            logger.warning("Watermark injection failed, returning original", error=str(e))
            return image_bytes


# Global instance
go_render_client = GoRenderClient()
