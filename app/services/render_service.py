"""
Render Service

Handles screenshot and PDF rendering using Playwright.
Thread-safe browser pool with automatic context refresh and proper cleanup.
"""

import asyncio
import io
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Optional

from PIL import Image
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.config import settings
from app.utils.exceptions import RenderError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserPool:
    """
    Thread-safe browser pool for reusing browser contexts.

    Manages a pool of browser contexts for efficient rendering.
    Uses threading.Lock for thread safety across Celery workers.
    """

    _instance: Optional["BrowserPool"] = None
    _creation_lock = threading.Lock()

    def __new__(cls) -> "BrowserPool":
        if cls._instance is None:
            with cls._creation_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, "_init_done") and self._init_done:
            return

        # Thread-safe locks
        self._init_lock = threading.Lock()
        self._context_lock = threading.Lock()

        # State
        self._initialized = False
        self._playwright = None
        self._browser: Browser | None = None
        self._contexts: list[BrowserContext] = []
        self._available_contexts: asyncio.Queue | None = None
        self._render_counts: dict[int, int] = {}  # Use id() as key
        self._context_map: dict[int, BrowserContext] = {}  # id -> context mapping

        self._init_done = True

    async def initialize(self) -> None:
        """Initialize the browser pool."""
        with self._init_lock:
            if self._initialized:
                return

            logger.info("Initializing browser pool")

            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
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
                        "--disable-background-networking",
                        "--disable-default-apps",
                        "--disable-sync",
                        "--disable-translate",
                        "--metrics-recording-only",
                        "--mute-audio",
                        "--no-default-browser-check",
                        "--safebrowsing-disable-auto-update",
                    ],
                )

                self._available_contexts = asyncio.Queue()

                # Create initial contexts
                for _ in range(settings.BROWSER_POOL_SIZE):
                    context = await self._create_context()
                    await self._available_contexts.put(context)

                self._initialized = True
                logger.info(
                    "Browser pool initialized",
                    pool_size=settings.BROWSER_POOL_SIZE,
                )
            except Exception as e:
                logger.error("Failed to initialize browser pool", error=str(e))
                await self._cleanup_on_error()
                raise

    async def _cleanup_on_error(self) -> None:
        """Clean up resources on initialization error."""
        for context in self._contexts:
            try:
                await asyncio.wait_for(context.close(), timeout=5.0)
            except Exception:
                pass

        if self._browser:
            try:
                await asyncio.wait_for(self._browser.close(), timeout=5.0)
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._contexts = []
        self._render_counts = {}
        self._context_map = {}

    async def _create_context(self) -> BrowserContext:
        """Create a new browser context."""
        if not self._browser:
            raise RenderError("Browser not initialized")

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

        context_id = id(context)

        with self._context_lock:
            self._contexts.append(context)
            self._render_counts[context_id] = 0
            self._context_map[context_id] = context

        return context

    async def acquire_context(self) -> BrowserContext:
        """
        Acquire a browser context from the pool.
        
        Returns:
            Available browser context
            
        Raises:
            RenderError: If pool is not initialized
        """
        if not self._initialized:
            await self.initialize()

        if self._available_contexts is None:
            raise RenderError("Browser pool not properly initialized")

        # Try to get a valid context, refresh if needed
        max_attempts = 3
        for attempt in range(max_attempts):
            context = await self._available_contexts.get()
            context_id = id(context)

            # Check if context is still valid (not closed)
            try:
                # Try to check if browser is connected
                if self._browser and not self._browser.is_connected():
                    logger.warning("Browser disconnected, reinitializing pool")
                    await self._reinitialize_pool()
                    context = await self._available_contexts.get()
                    context_id = id(context)
            except Exception as e:
                logger.warning("Error checking browser connection", error=str(e))

            # Check if context needs refresh based on render count
            with self._context_lock:
                render_count = self._render_counts.get(context_id, 0)

            if render_count >= settings.BROWSER_MAX_RENDERS_PER_CONTEXT:
                logger.info(
                    "Context reached max renders, refreshing",
                    context_id=context_id,
                    render_count=render_count,
                )
                try:
                    context = await self._refresh_context(context)
                except Exception as e:
                    logger.warning("Failed to refresh context, creating new one", error=str(e))
                    context = await self._create_context()

            # Validate context by trying to create a test page
            try:
                # Quick validation - just check if we can create a page
                test_page = await asyncio.wait_for(context.new_page(), timeout=5.0)
                await test_page.close()
                return context
            except Exception as e:
                logger.warning(
                    f"Context validation failed (attempt {attempt + 1}/{max_attempts})",
                    error=str(e),
                )
                # Remove invalid context from tracking
                with self._context_lock:
                    if context in self._contexts:
                        self._contexts.remove(context)
                    self._render_counts.pop(context_id, None)
                    self._context_map.pop(context_id, None)
                
                # Create a fresh context
                try:
                    context = await self._create_context()
                    return context
                except Exception as create_error:
                    logger.error("Failed to create new context", error=str(create_error))
                    if attempt == max_attempts - 1:
                        raise RenderError(f"Failed to acquire valid browser context: {str(e)}")

        raise RenderError("Failed to acquire valid browser context after max attempts")
    
    async def _reinitialize_pool(self) -> None:
        """Reinitialize the browser pool if browser is disconnected."""
        logger.info("Reinitializing browser pool")
        
        # Close existing resources
        await self._cleanup_on_error()
        
        # Reset state
        self._initialized = False
        self._playwright = None
        self._browser = None
        self._contexts = []
        self._available_contexts = None
        self._render_counts = {}
        self._context_map = {}
        
        # Reinitialize
        await self.initialize()

    async def release_context(self, context: BrowserContext) -> None:
        """
        Release a browser context back to the pool.
        
        Args:
            context: Browser context to release
        """
        if self._available_contexts is None:
            return

        context_id = id(context)

        with self._context_lock:
            if context_id in self._render_counts:
                self._render_counts[context_id] += 1

        await self._available_contexts.put(context)

    async def _refresh_context(self, old_context: BrowserContext) -> BrowserContext:
        """
        Refresh a context by closing and recreating it.
        
        Args:
            old_context: Context to refresh
            
        Returns:
            New browser context
        """
        old_context_id = id(old_context)

        # Remove old context from tracking
        with self._context_lock:
            if old_context in self._contexts:
                self._contexts.remove(old_context)
            self._render_counts.pop(old_context_id, None)
            self._context_map.pop(old_context_id, None)

        # Close old context with timeout
        try:
            await asyncio.wait_for(old_context.close(), timeout=5.0)
        except TimeoutError:
            logger.warning("Context close timed out", context_id=old_context_id)
        except Exception as e:
            logger.warning("Error closing context", error=str(e))

        # Create and return new context
        new_context = await self._create_context()
        return new_context

    async def force_refresh_context(self, context: BrowserContext) -> None:
        """
        Force refresh a problematic context and return it to pool.
        
        Args:
            context: Problematic context to refresh
        """
        try:
            new_context = await self._refresh_context(context)
            if self._available_contexts:
                await self._available_contexts.put(new_context)
        except Exception as e:
            logger.error("Failed to force refresh context", error=str(e))

    async def close(self) -> None:
        """Close all contexts and browser."""
        with self._init_lock:
            if not self._initialized:
                return

            logger.info("Closing browser pool")

            # Close all contexts
            with self._context_lock:
                contexts_to_close = list(self._contexts)
                self._contexts = []
                self._render_counts = {}
                self._context_map = {}

            for context in contexts_to_close:
                try:
                    await asyncio.wait_for(context.close(), timeout=5.0)
                except TimeoutError:
                    logger.warning("Context close timed out during shutdown")
                except Exception as e:
                    logger.warning("Error closing context", error=str(e))

            # Close browser
            if self._browser:
                try:
                    await asyncio.wait_for(self._browser.close(), timeout=10.0)
                except TimeoutError:
                    logger.warning("Browser close timed out")
                except Exception as e:
                    logger.warning("Error closing browser", error=str(e))
                self._browser = None

            # Stop playwright
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning("Error stopping playwright", error=str(e))
                self._playwright = None

            self._available_contexts = None
            self._initialized = False
            logger.info("Browser pool closed")

    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized."""
        return self._initialized

    @property
    def pool_size(self) -> int:
        """Get current pool size."""
        with self._context_lock:
            return len(self._contexts)


# Global browser pool instance
browser_pool = BrowserPool()


class RenderService:
    """Service for rendering screenshots and PDFs."""

    def __init__(self):
        self.pool = browser_pool

    @asynccontextmanager
    async def _get_page(self, context: BrowserContext):
        """
        Context manager for page lifecycle.
        
        Ensures page is properly closed even on errors.
        
        Args:
            context: Browser context
            
        Yields:
            New page instance
        """
        page: Page | None = None
        try:
            page = await context.new_page()
            yield page
        finally:
            if page:
                try:
                    await asyncio.wait_for(page.close(), timeout=5.0)
                except TimeoutError:
                    logger.warning("Page close timed out")
                except Exception as e:
                    logger.warning("Error closing page", error=str(e))

    async def capture_screenshot(
        self,
        url: str,
        options: dict[str, Any],
        user_plan: dict | None = None,
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
        start_time = datetime.now(UTC)
        screenshot_bytes: bytes | None = None

        try:
            async with self._get_page(context) as page:
                # Set viewport with device scale factor for HD quality
                width = options.get("width", 1920)
                height = options.get("height", 1080)
                device_scale_factor = options.get("device_scale_factor", 2)  # Default 2x for HD
                await page.set_viewport_size({
                    "width": width,
                    "height": height,
                    "device_scale_factor": device_scale_factor,
                })

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

                # Screenshot options with high quality settings
                screenshot_options: dict[str, Any] = {
                    "type": options.get("format", "png"),
                    "full_page": options.get("full_page", False),
                }

                # For PNG, ensure lossless quality
                if screenshot_options["type"] == "png":
                    # PNG is always lossless, but we can ensure no compression
                    screenshot_options["omit_background"] = False
                
                if screenshot_options["type"] == "jpeg":
                    screenshot_options["quality"] = options.get("quality", 100)  # Default 100 for HD
                
                # WebP is not natively supported by Playwright, capture as PNG and convert
                convert_to_webp = False
                webp_quality = options.get("quality", 100)
                if screenshot_options["type"] == "webp":
                    screenshot_options["type"] = "png"  # Capture as PNG first
                    convert_to_webp = True

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
                    except RenderError:
                        raise
                    except Exception as e:
                        raise RenderError(
                            f"Failed to capture element: {str(e)}"
                        )
                else:
                    screenshot_bytes = await page.screenshot(**screenshot_options)
                
                # Convert to WebP if requested
                if convert_to_webp:
                    screenshot_bytes = self._convert_to_webp(screenshot_bytes, webp_quality)

            # Calculate processing time
            end_time = datetime.now(UTC)
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Get image dimensions - properly close PIL Image
            img_width, img_height = self._get_image_dimensions(screenshot_bytes)

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
            await self.pool.release_context(context)

    async def generate_pdf(
        self,
        url: str,
        options: dict[str, Any],
        user_plan: dict | None = None,
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
        start_time = datetime.now(UTC)
        pdf_bytes: bytes | None = None

        try:
            async with self._get_page(context) as page:
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
            end_time = datetime.now(UTC)
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
            await self.pool.release_context(context)

    def _convert_to_webp(self, image_bytes: bytes, quality: int = 100) -> bytes:
        """
        Convert PNG image bytes to WebP format.
        
        Args:
            image_bytes: PNG image data
            quality: WebP quality (1-100)
            
        Returns:
            WebP image bytes
        """
        img = None
        output = None
        try:
            img = Image.open(io.BytesIO(image_bytes))
            output = io.BytesIO()
            
            # Convert to RGB if necessary (WebP doesn't support all modes)
            if img.mode in ('RGBA', 'LA', 'P'):
                # For transparency support
                img.save(output, format='WEBP', quality=quality, lossless=(quality == 100))
            else:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(output, format='WEBP', quality=quality, lossless=(quality == 100))
            
            return output.getvalue()
        except Exception as e:
            logger.warning("Failed to convert to WebP, returning original", error=str(e))
            return image_bytes
        finally:
            if img:
                img.close()
            if output:
                output.close()

    def _get_image_dimensions(self, image_bytes: bytes) -> tuple[int, int]:
        """
        Get image dimensions from bytes.
        
        Properly closes PIL Image to prevent memory leaks.
        
        Args:
            image_bytes: Image data
            
        Returns:
            Tuple of (width, height)
        """
        img = None
        try:
            img = Image.open(io.BytesIO(image_bytes))
            return img.size
        finally:
            if img:
                img.close()

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
        img = None
        overlay = None
        output = None

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
            result_img = Image.alpha_composite(img, overlay)

            # Convert back to original format
            if format.lower() in ("jpeg", "jpg"):
                result_img = result_img.convert("RGB")

            # Save to bytes
            output = io.BytesIO()
            result_img.save(output, format=format.upper())
            result = output.getvalue()

            # Close result_img
            result_img.close()

            return result

        except Exception as e:
            logger.warning("Failed to inject watermark", error=str(e))
            return image_bytes
        finally:
            # Clean up PIL objects
            if img:
                img.close()
            if overlay:
                overlay.close()
            if output:
                output.close()


# Create global render service instance
render_service = RenderService()
