"""
Request Signature Utilities

HMAC-SHA256 based request signing for secure frontend usage.
Allows screenshot URLs to be used client-side without exposing API keys.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode, parse_qs, urlparse

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Signature expiry time (default: 1 hour)
DEFAULT_SIGNATURE_EXPIRY = 3600


def generate_signature(
    access_key: str,
    params: dict,
    secret_key: str,
    expires_in: int = DEFAULT_SIGNATURE_EXPIRY,
) -> dict:
    """
    Generate a signed request with HMAC-SHA256.
    
    Args:
        access_key: Public access key (included in params for lookup)
        params: Request parameters to sign
        secret_key: Private secret key for HMAC signing
        expires_in: Signature validity in seconds
        
    Returns:
        dict with original params + access_key + signature + expires
    """
    signing_key = secret_key
    
    # Add expiry timestamp
    expires = int(time.time()) + expires_in
    
    # Create signable string from sorted params
    sign_params = {**params, "expires": expires}
    
    # Sort and encode params
    sorted_params = sorted(sign_params.items())
    sign_string = urlencode(sorted_params)
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        signing_key.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    return {
        **params,
        "expires": expires,
        "signature": signature,
    }


def verify_signature(
    params: dict,
    signature: str,
    secret_key: str,
) -> tuple[bool, str | None]:
    """
    Verify a signed request using HMAC-SHA256.
    
    SECURITY: Always use the private secret_key, never the public access_key!
    
    Args:
        params: Request parameters (including expires, excluding signature)
        signature: The signature to verify
        secret_key: Private secret key for HMAC verification
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    signing_key = secret_key
    
    # Check expiry
    expires = params.get("expires")
    if not expires:
        return False, "Missing expiry timestamp"
    
    try:
        expires_int = int(expires)
    except (ValueError, TypeError):
        return False, "Invalid expiry timestamp"
    
    if time.time() > expires_int:
        return False, "Signature has expired"
    
    # Recreate signable string
    sign_params = {k: v for k, v in params.items() if k != "signature"}
    sorted_params = sorted(sign_params.items())
    sign_string = urlencode(sorted_params)
    
    # Generate expected signature
    expected_signature = hmac.new(
        signing_key.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    if hmac.compare_digest(signature, expected_signature):
        return True, None
    
    return False, "Invalid signature"


def extract_signature_params(query_string: str) -> tuple[dict, str | None]:
    """
    Extract parameters and signature from a query string.
    
    Args:
        query_string: URL query string
        
    Returns:
        Tuple of (params_dict, signature)
    """
    parsed = parse_qs(query_string, keep_blank_values=True)
    
    # Flatten single-value lists
    params = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    
    signature = params.pop("signature", None)
    
    return params, signature
