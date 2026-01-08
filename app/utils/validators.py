"""
Screenshot API - Validators
============================
Validation utilities for URLs, emails, passwords, and render options.
"""

import re
from ipaddress import ip_address, ip_network
from typing import Any
from urllib.parse import urlparse

# Email regex pattern
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Private IP ranges
PRIVATE_IP_RANGES = [
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("127.0.0.0/8"),
    ip_network("169.254.0.0/16"),
    ip_network("::1/128"),
    ip_network("fc00::/7"),
    ip_network("fe80::/10"),
]

# Valid screenshot formats
VALID_SCREENSHOT_FORMATS = ["png", "jpeg", "jpg", "webp"]

# Valid PDF formats
VALID_PDF_PAGE_FORMATS = ["A4", "A3", "Letter", "Legal", "Tabloid"]

# Screenshot dimension limits
MIN_WIDTH = 100
MAX_WIDTH = 3840
MIN_HEIGHT = 100
MAX_HEIGHT = 2160

# Default screenshot options
DEFAULT_SCREENSHOT_OPTIONS = {
    "width": 1280,
    "height": 720,
    "format": "png",
    "full_page": False,
    "delay": 0,
    "quality": 90,
}

# Default PDF options
DEFAULT_PDF_OPTIONS = {
    "format": "A4",
    "landscape": False,
    "print_background": True,
    "margin": {
        "top": "10mm",
        "right": "10mm",
        "bottom": "10mm",
        "left": "10mm",
    },
}


def is_valid_url(
    url: str,
    allow_localhost: bool = False,
    allow_private_ip: bool = False,
) -> bool:
    """
    Validate URL for screenshot/PDF rendering.

    Args:
        url: URL to validate
        allow_localhost: Whether to allow localhost URLs
        allow_private_ip: Whether to allow private IP addresses

    Returns:
        True if URL is valid, False otherwise
    """
    # Cloud metadata endpoints - SSRF targets
    BLOCKED_HOSTNAMES = {
        # AWS metadata
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.gke-metadata-server.svc.cluster.local",
        # Azure metadata
        # DigitalOcean metadata
        # Kubernetes
        "kubernetes.default.svc",
        "kubernetes.default",
        # Other dangerous
        "0.0.0.0",
        "0",
        "[::0]",
        "[::]",
    }

    # Dangerous hostname patterns
    DANGEROUS_PATTERNS = [
        "metadata",
        "internal",
        ".local",
        ".internal",
        ".svc",
    ]

    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ("http", "https"):
            return False

        # Check hostname exists
        if not parsed.netloc:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()

        # Block known dangerous hostnames (cloud metadata, etc.)
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False

        # Block dangerous patterns (metadata, internal, etc.)
        for pattern in DANGEROUS_PATTERNS:
            if pattern in hostname_lower:
                return False

        # Check for localhost
        if not allow_localhost:
            if hostname_lower in ("localhost", "127.0.0.1", "::1"):
                return False
            if hostname_lower.endswith(".localhost"):
                return False

        # Check for private IPs
        if not allow_private_ip:
            try:
                ip = ip_address(hostname)
                for private_range in PRIVATE_IP_RANGES:
                    if ip in private_range:
                        return False
            except ValueError:
                # Not an IP address, continue
                pass

        # Check for dangerous schemes in URL
        dangerous_patterns = [
            "javascript:",
            "data:",
            "vbscript:",
            "file:",
        ]
        for pattern in dangerous_patterns:
            if pattern in url.lower():
                return False

        return True

    except Exception:
        return False


def validate_url(
    url: str,
    allow_localhost: bool = False,
    require_https: bool = False,
) -> tuple[bool, str | None]:
    """
    Validate a URL and return validation result with error message.

    Args:
        url: URL to validate
        allow_localhost: Whether to allow localhost URLs
        require_https: Whether to require HTTPS (default: False)

    Returns:
        Tuple of (is_valid, error_message or None)
    """
    if not url:
        return False, "URL is required"

    # Check HTTPS requirement
    if require_https and not url.lower().startswith("https://"):
        return False, "HTTPS is required"

    if not is_valid_url(url, allow_localhost=allow_localhost):
        if "localhost" in url.lower() or "127.0.0.1" in url:
            return False, "Localhost URLs are not allowed"
        if any(ip in url for ip in ["192.168.", "10.", "172.16."]):
            return False, "Private IP addresses are not allowed"
        return False, "Invalid URL format. Must be http:// or https://"

    return True, None


def sanitize_url(url: str) -> str:
    """
    Sanitize and normalize URL.

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL
    """
    # Strip whitespace
    url = url.strip()

    # Lowercase the scheme and host
    parsed = urlparse(url)
    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
    ).geturl()


def is_valid_email(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if email is valid, False otherwise
    """
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_PATTERN.match(email))


def is_valid_password(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    special_chars = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
    if not any(c in special_chars for c in password):
        errors.append("Password must contain at least one special character")

    return len(errors) == 0, errors


def validate_screenshot_options(
    options: dict[str, Any],
    max_width: int = MAX_WIDTH,
    max_height: int = MAX_HEIGHT,
    apply_defaults: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate screenshot options.

    Args:
        options: Screenshot options to validate
        max_width: Maximum allowed width
        max_height: Maximum allowed height
        apply_defaults: Whether to apply default values for missing options

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Apply defaults if requested
    if apply_defaults:
        for key, value in DEFAULT_SCREENSHOT_OPTIONS.items():
            if key not in options:
                options[key] = value

    # Validate width
    width = options.get("width")
    if width is not None:
        if not isinstance(width, int) or width < MIN_WIDTH or width > max_width:
            errors.append(f"Width must be between {MIN_WIDTH} and {max_width}")

    # Validate height
    height = options.get("height")
    if height is not None:
        if not isinstance(height, int) or height < MIN_HEIGHT or height > max_height:
            errors.append(f"Height must be between {MIN_HEIGHT} and {max_height}")

    # Validate format
    format_ = options.get("format")
    if format_ is not None:
        if format_.lower() not in VALID_SCREENSHOT_FORMATS:
            errors.append(f"Format must be one of: {', '.join(VALID_SCREENSHOT_FORMATS)}")

    # Validate quality (for JPEG/WebP)
    quality = options.get("quality")
    if quality is not None:
        if not isinstance(quality, int) or quality < 1 or quality > 100:
            errors.append("Quality must be between 1 and 100")

    # Validate delay
    delay = options.get("delay")
    if delay is not None:
        if not isinstance(delay, int) or delay < 0 or delay > 30000:
            errors.append("Delay must be between 0 and 30000 milliseconds")

    return len(errors) == 0, errors


def validate_pdf_options(
    options: dict[str, Any],
    apply_defaults: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate PDF generation options.

    Args:
        options: PDF options to validate
        apply_defaults: Whether to apply default values for missing options

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Apply defaults if requested
    if apply_defaults:
        for key, value in DEFAULT_PDF_OPTIONS.items():
            if key not in options:
                options[key] = value

    # Validate format
    format_ = options.get("format")
    if format_ is not None:
        if format_ not in VALID_PDF_PAGE_FORMATS:
            errors.append(f"PDF format must be one of: {', '.join(VALID_PDF_PAGE_FORMATS)}")

    # Validate margins
    margin = options.get("margin")
    if margin is not None:
        if not isinstance(margin, dict):
            errors.append("Margin must be an object with top, right, bottom, left")
        else:
            for side in ["top", "right", "bottom", "left"]:
                value = margin.get(side)
                if value is not None and not isinstance(value, str):
                    errors.append(f"Margin {side} must be a string (e.g., '10mm', '1in')")

    # Validate scale
    scale = options.get("scale")
    if scale is not None:
        if not isinstance(scale, (int, float)) or scale < 0.1 or scale > 2:
            errors.append("Scale must be between 0.1 and 2")

    return len(errors) == 0, errors


def validate_render_options(
    render_type: str,
    options: dict[str, Any],
    max_width: int = MAX_WIDTH,
    max_height: int = MAX_HEIGHT,
    apply_defaults: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate render options based on type.

    Args:
        render_type: Type of render ('screenshot' or 'pdf')
        options: Options to validate
        max_width: Maximum width (for screenshots)
        max_height: Maximum height (for screenshots)
        apply_defaults: Whether to apply defaults

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    if render_type.lower() == "screenshot":
        return validate_screenshot_options(
            options,
            max_width=max_width,
            max_height=max_height,
            apply_defaults=apply_defaults,
        )
    elif render_type.lower() == "pdf":
        return validate_pdf_options(options, apply_defaults=apply_defaults)
    else:
        return False, [f"Unknown render type: {render_type}"]
