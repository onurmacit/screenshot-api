"""
Render Service

Handles screenshot and PDF rendering using Playwright.
"""

import asyncio
import io
from datetime import datetime, timezone
from typing import Any, Optional

from PIL import Image
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.config import settings
from app.utils.exceptions import RenderError, ValidationError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserPool:
    """
    Singleton browser pool for reusing browser contexts.

    Manages a pool of browser contexts for efficient rendering.
    """

    _instance: Optional["BrowserPool"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "BrowserPool":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self) -> None:
        """Initialize the browser pool."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info("Initializing browser pool")

            self._playwright = await async_playwright().start()
            self._browser: Browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-zygote",
                    "--single-process",
                    "--disable-extensions",
                ],
            )

            self._contexts: list[BrowserContext] = []
            self._available_contexts: asyncio.Queue[BrowserContext] = asyncio.Queue()
            self._render_counts: dict[BrowserContext, int] = {}

            # Create initial contexts
            for _ in range(settings.BROWSER_POOL_SIZE):
                context = await self._create_context()
                await self._available_contexts.put(context)

            self._initialized = True
            logger.info(
                "Browser pool initialized",
                pool_size=settings.BROWSER_POOL_SIZE,
            )

    async def _create_context(self) -> BrowserContext:
        """Create a new browser context."""
        context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
        )
        self._contexts.append(context)
        self._render_counts[context] = 0
        return context

    async def acquire_context(self) -> BrowserContext:
        """Acquire a browser context from the pool."""
        if not self._initialized:
            await self.initialize()

        context = await self._available_contexts.get()

        # Check if context needs refresh
        if self._render_counts[context] >= settings.BROWSER_MAX_RENDERS_PER_CONTEXT:
            await self._refresh_context(context)

        return context

    async def release_context(self, context: BrowserContext) -> None:
        """Release a browser context back to the pool."""
        self._render_counts[context] = self._render_counts.get(context, 0) + 1
        await self._available_contexts.put(context)

    async def _refresh_context(self, context: BrowserContext) -> None:
        """Refresh a context by closing and recreating it."""
        try:
            self._contexts.remove(context)
            del self._render_counts[context]
            await context.close()
        except Exception as e:
            logger.warning("Error closing context", error=str(e))

        new_context = await self._create_context()
        self._render_counts[new_context] = 0

    async def close(self) -> None:
        """Close all contexts and browser."""
        if not self._initialized:
            return

        logger.info("Closing browser pool")

        for context in self._contexts:
            try:
                await context.close()
            except Exception:
                pass

        try:
            await self._browser.close()
        except Exception:
            pass

        try:
            await self._playwright.stop()
        except Exception:
            pass

        self._initialized = False
        logger.info("Browser pool closed")


# Global browser pool instance
browser_pool = BrowserPool()


class RenderService:
    """Service for rendering screenshots and PDFs."""

    def __init__(self):
        self.pool = browser_pool

    async def capture_screenshot(
        self,
        url: str,
        options: dict[str, Any],
        user_plan: Optional[dict] = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Capture a screenshot of a URL.

        Args:
            url: Target URL
            options: Screenshot options
            user_plan: User's plan features

        Returns:
            Tuple of (image_bytes, metadata)

        Raises:
            RenderError: If screenshot capture fails
        """
        context = await self.pool.acquire_context()
        page: Optional[Page] = None
        start_time = datetime.now(timezone.utc)

        try:
            page = await context.new_page()

            # Set viewport
            width = options.get("width", 1920)
            height = options.get("height", 1080)
            await page.set_viewport_size({"width": width, "height": height})

            # Set user agent if provided
            if options.get("user_agent"):
                await page.set_extra_http_headers(
                    {"User-Agent": options["user_agent"]}
                )

            # Set extra headers
            if options.get("extra_http_headers"):
                await page.set_extra_http_headers(options["extra_http_headers"])

            # Set geolocation (pro+ only)
            if options.get("geolocation") and user_plan and user_plan.get("geolocation"):
                geo = options["geolocation"]
                await context.set_geolocation({
                    "latitude": geo["lat"],
                    "longitude": geo["lon"],
                })
                await context.grant_permissions(["geolocation"])

            # Navigate to URL
            timeout = options.get("timeout", settings.BROWSER_TIMEOUT_MS)
            wait_until = options.get("wait_until", "networkidle")

            try:
                await page.goto(
                    url,
                    timeout=timeout,
                    wait_until=wait_until,
                )
            except Exception as e:
                raise RenderError(
                    f"Failed to load URL: {str(e)}",
                    details={"url": url, "error": str(e)},
                )

            # Wait for delay
            delay = options.get("delay", 0)
            if delay > 0:
                await asyncio.sleep(delay / 1000)

            # Inject custom CSS (pro+ only)
            if options.get("custom_css") and user_plan and user_plan.get("custom_css"):
                await page.add_style_tag(content=options["custom_css"])

            # Remove elements
            if options.get("remove_elements"):
                for selector in options["remove_elements"]:
                    try:
                        await page.evaluate(f"""
                            document.querySelectorAll('{selector}')
                                .forEach(el => el.remove())
                        """)
                    except Exception:
                        pass

            # Screenshot options
            screenshot_options: dict[str, Any] = {
                "type": options.get("format", "png"),
                "full_page": options.get("full_page", False),
            }

            if screenshot_options["type"] == "jpeg":
                screenshot_options["quality"] = options.get("quality", 90)

            # Capture specific element or full page
            if options.get("element_selector") and user_plan and user_plan.get("element_selector"):
                try:
                    element = await page.query_selector(options["element_selector"])
                    if element:
                        screenshot_bytes = await element.screenshot(**screenshot_options)
                    else:
                        raise RenderError(
                            f"Element not found: {options['element_selector']}"
                        )
                except Exception as e:
                    raise RenderError(
                        f"Failed to capture element: {str(e)}"
                    )
            else:
                screenshot_bytes = await page.screenshot(**screenshot_options)

            # Calculate processing time
            end_time = datetime.now(timezone.utc)
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Get image dimensions
            img = Image.open(io.BytesIO(screenshot_bytes))
            img_width, img_height = img.size

            metadata = {
                "width": img_width,
                "height": img_height,
                "format": options.get("format", "png"),
                "file_size": len(screenshot_bytes),
                "processing_time_ms": processing_time_ms,
                "full_page": options.get("full_page", False),
            }

            logger.info(
                "Screenshot captured",
                url=url,
                width=img_width,
                height=img_height,
                size=len(screenshot_bytes),
                time_ms=processing_time_ms,
            )

            return screenshot_bytes, metadata

        except RenderError:
            raise
        except Exception as e:
            logger.exception("Screenshot capture failed", url=url, error=str(e))
            raise RenderError(
                f"Screenshot capture failed: {str(e)}",
                details={"url": url},
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await self.pool.release_context(context)

    async def generate_pdf(
        self,
        url: str,
        options: dict[str, Any],
        user_plan: Optional[dict] = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Generate a PDF from a URL.

        Args:
            url: Target URL
            options: PDF options
            user_plan: User's plan features

        Returns:
            Tuple of (pdf_bytes, metadata)

        Raises:
            RenderError: If PDF generation fails
        """
        context = await self.pool.acquire_context()
        page: Optional[Page] = None
        start_time = datetime.now(timezone.utc)

        try:
            page = await context.new_page()

            # Navigate to URL
            timeout = options.get("timeout", settings.BROWSER_TIMEOUT_MS)
            wait_until = options.get("wait_until", "networkidle")

            try:
                await page.goto(
                    url,
                    timeout=timeout,
                    wait_until=wait_until,
                )
            except Exception as e:
                raise RenderError(
                    f"Failed to load URL: {str(e)}",
                    details={"url": url, "error": str(e)},
                )

            # Wait for delay
            delay = options.get("delay", 0)
            if delay > 0:
                await asyncio.sleep(delay / 1000)

            # PDF options
            pdf_options: dict[str, Any] = {
                "format": options.get("format", "A4"),
                "landscape": options.get("landscape", False),
                "print_background": options.get("print_background", True),
                "prefer_css_page_size": options.get("prefer_css_page_size", False),
            }

            # Scale
            if options.get("scale"):
                pdf_options["scale"] = options["scale"]

            # Margins
            if options.get("margin"):
                pdf_options["margin"] = options["margin"]

            # Page ranges
            if options.get("page_ranges"):
                pdf_options["page_ranges"] = options["page_ranges"]

            # Header/Footer
            if options.get("header_template"):
                pdf_options["header_template"] = options["header_template"]
                pdf_options["display_header_footer"] = True

            if options.get("footer_template"):
                pdf_options["footer_template"] = options["footer_template"]
                pdf_options["display_header_footer"] = True

            # Generate PDF
            pdf_bytes = await page.pdf(**pdf_options)

            # Calculate processing time
            end_time = datetime.now(timezone.utc)
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Count pages (approximate)
            page_count = pdf_bytes.count(b"/Type /Page") - pdf_bytes.count(b"/Type /Pages")
            if page_count < 1:
                page_count = 1

            metadata = {
                "format": "pdf",
                "paper_format": options.get("format", "A4"),
                "file_size": len(pdf_bytes),
                "page_count": page_count,
                "processing_time_ms": processing_time_ms,
                "landscape": options.get("landscape", False),
            }

            logger.info(
                "PDF generated",
                url=url,
                pages=page_count,
                size=len(pdf_bytes),
                time_ms=processing_time_ms,
            )

            return pdf_bytes, metadata

        except RenderError:
            raise
        except Exception as e:
            logger.exception("PDF generation failed", url=url, error=str(e))
            raise RenderError(
                f"PDF generation failed: {str(e)}",
                details={"url": url},
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await self.pool.release_context(context)

    def inject_watermark(
        self,
        image_bytes: bytes,
        format: str = "png",
    ) -> bytes:
        """
        Inject watermark into image (for free tier).

        Args:
            image_bytes: Original image bytes
            format: Image format

        Returns:
            Image bytes with watermark
        """
        try:
            from PIL import ImageDraw, ImageFont

            img = Image.open(io.BytesIO(image_bytes))

            # Create transparent overlay
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Watermark text
            text = "Screenshot API - Free Tier"

            # Try to use a font, fall back to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except Exception:
                font = ImageFont.load_default()

            # Get text size
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Position at bottom right
            x = img.width - text_width - 20
            y = img.height - text_height - 20

            # Draw semi-transparent background
            padding = 10
            draw.rectangle(
                [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
                fill=(0, 0, 0, 128),
            )

            # Draw text
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 200))

            # Composite
            img = Image.alpha_composite(img, overlay)

            # Convert back to original format
            if format.lower() in ("jpeg", "jpg"):
                img = img.convert("RGB")

            # Save to bytes
            output = io.BytesIO()
            img.save(output, format=format.upper())
            return output.getvalue()

        except Exception as e:
            logger.warning("Failed to inject watermark", error=str(e))
            return image_bytes


# Create global render service instance
render_service = RenderService()

