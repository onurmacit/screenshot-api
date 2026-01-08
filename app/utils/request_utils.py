"""
Request utility functions for handling HTTP requests.
"""

from fastapi import Request

# Common browser User-Agent identifiers
BROWSER_USER_AGENTS = frozenset([
    "mozilla",
    "chrome",
    "safari",
    "firefox",
    "edge",
    "opera",
    "webkit",
])


def is_browser_request(request: Request) -> bool:
    """
    Detect if the request is from a web browser.

    Detection logic:
    1. If Accept header contains text/html but not application/json -> browser
    2. If Accept header is empty or */* and User-Agent matches browser patterns -> browser

    Args:
        request: FastAPI Request object

    Returns:
        True if request is from a browser, False otherwise
    """
    accept_header = request.headers.get("Accept", "").lower()
    user_agent = request.headers.get("User-Agent", "").lower()

    # Parse accept header
    accepts_html = "text/html" in accept_header
    accepts_json = "application/json" in accept_header
    accepts_any = not accept_header or accept_header == "*/*" or "*/*" in accept_header

    # Rule 1: Explicitly accepts HTML but not JSON
    if accepts_html and not accepts_json:
        return True

    # Rule 2: No specific preference, check User-Agent
    if accepts_any and _has_browser_user_agent(user_agent):
        return True

    return False


def _has_browser_user_agent(user_agent: str) -> bool:
    """
    Check if User-Agent string indicates a browser.

    Args:
        user_agent: Lowercase User-Agent string

    Returns:
        True if User-Agent matches known browser patterns
    """
    return any(browser in user_agent for browser in BROWSER_USER_AGENTS)


def get_client_ip(request: Request) -> str:
    """
    Get the real client IP address from request.

    Handles common proxy headers (X-Forwarded-For, X-Real-IP).

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For first (may contain multiple IPs)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct connection
    if request.client:
        return request.client.host

    return "unknown"

