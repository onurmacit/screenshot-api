"""
Helper utility functions
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def generate_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return f"req_{secrets.token_hex(16)}"


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(UTC)


def hash_string(value: str) -> str:
    """Create SHA256 hash of a string."""
    return hashlib.sha256(value.encode()).hexdigest()


def hash_url_options(url: str, options: dict[str, Any]) -> str:
    """
    Create a hash for URL + options combination (for caching).

    Args:
        url: The target URL
        options: Render options dictionary

    Returns:
        SHA256 hash string
    """
    import json

    # Sort options for consistent hashing
    sorted_options = json.dumps(options, sort_keys=True)
    combined = f"{url}:{sorted_options}"
    return hash_string(combined)


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(milliseconds: int) -> str:
    """
    Format duration in human-readable format.

    Args:
        milliseconds: Duration in milliseconds

    Returns:
        Formatted string (e.g., "1.5s")
    """
    if milliseconds < 1000:
        return f"{milliseconds}ms"
    elif milliseconds < 60000:
        return f"{milliseconds / 1000:.1f}s"
    else:
        minutes = milliseconds / 60000
        return f"{minutes:.1f}m"


def get_file_extension(format_type: str) -> str:
    """
    Get file extension for render format.

    Args:
        format_type: Render format (png, jpeg, webp, pdf)

    Returns:
        File extension string
    """
    extensions = {
        "png": "png",
        "jpeg": "jpg",
        "jpg": "jpg",
        "webp": "webp",
        "pdf": "pdf",
    }
    return extensions.get(format_type.lower(), "png")


def get_content_type(format_type: str) -> str:
    """
    Get MIME content type for render format.

    Args:
        format_type: Render format

    Returns:
        MIME content type string
    """
    content_types = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "webp": "image/webp",
        "pdf": "application/pdf",
    }
    return content_types.get(format_type.lower(), "application/octet-stream")


def mask_api_key(api_key: str) -> str:
    """
    Mask API key for logging (show only prefix).

    Args:
        api_key: Full API key

    Returns:
        Masked API key string
    """
    if len(api_key) > 16:
        return f"{api_key[:16]}...{api_key[-4:]}"
    return "***"


def mask_email(email: str) -> str:
    """
    Mask email for logging/display.

    Args:
        email: Full email address

    Returns:
        Masked email string
    """
    if "@" not in email:
        return "***"

    local, domain = email.split("@", 1)
    if len(local) > 2:
        masked_local = f"{local[0]}***{local[-1]}"
    else:
        masked_local = "***"

    return f"{masked_local}@{domain}"


def calculate_expiry_date(days: int) -> datetime:
    """
    Calculate expiry date from now.

    Args:
        days: Number of days until expiry

    Returns:
        Expiry datetime
    """
    from datetime import timedelta

    return utc_now() + timedelta(days=days)


def parse_page_ranges(ranges_str: str) -> list[tuple[int, int]]:
    """
    Parse page range string (e.g., "1-5,8-11").

    Args:
        ranges_str: Page range string

    Returns:
        List of (start, end) tuples
    """
    result = []
    parts = ranges_str.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            result.append((int(start.strip()), int(end.strip())))
        else:
            page = int(part)
            result.append((page, page))

    return result


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """
    Split list into chunks.

    Args:
        lst: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_dict_get(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to search
        *keys: Keys path
        default: Default value if not found

    Returns:
        Value at keys path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current

