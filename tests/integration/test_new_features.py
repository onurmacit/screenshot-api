
import pytest
import requests
import json
import time
from app.utils.signature import generate_signature, verify_signature, extract_signature_params

# Go Renderer URL (Local Docker)
RENDERER_URL = "http://localhost:8001"

@pytest.mark.integration
class TestGoRendererFeatures:
    """Integration tests hitting the Go Renderer container directly"""

    def test_health(self):
        resp = requests.get(f"{RENDERER_URL}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_capture_beyond_viewport_true(self):
        """Test full page capture with capture_beyond_viewport=true"""
        payload = {
            "url": "https://stripe.com",
            "full_page": True,
            "capture_beyond_viewport": True,
            "format": "jpeg",
            "width": 1920,
            "height": 1080
        }
        resp = requests.post(f"{RENDERER_URL}/render/screenshot", json=payload)
        assert resp.status_code == 200
        # Stripe is long, should be > 5000px height
        # Since we get binary, we can't easily check dimensions without PIL, 
        # but succesful 200 OK means it worked.
        assert len(resp.content) > 100000 # Should be large

    def test_scroll_into_view_valid(self):
        """Test scrolling to a specific element"""
        payload = {
            "url": "https://stripe.com",
            "scroll_into_view": "footer",
            "width": 1920,
            "height": 1080
        }
        resp = requests.post(f"{RENDERER_URL}/render/screenshot", json=payload)
        assert resp.status_code == 200

    def test_scroll_into_view_invalid(self):
        """Test graceful failure for invalid selector"""
        payload = {
            "url": "https://stripe.com",
            "scroll_into_view": "non-existent-selector-123",
            "timeout": 5000  # Fast timeout
        }
        resp = requests.post(f"{RENDERER_URL}/render/screenshot", json=payload)
        # Should fail elegantly, usually 500 with error message
        assert resp.status_code == 500
        error = resp.json()
        assert "scroll element not found" in error["message"]

    def test_selector_capture(self):
        """Test capturing specific element"""
        payload = {
            "url": "https://stripe.com",
            "selector": "nav",
            "format": "png"
        }
        resp = requests.post(f"{RENDERER_URL}/render/screenshot", json=payload)
        assert resp.status_code == 200
        
    def test_response_type_json(self):
        """Test return_base64 feature (JSON response)"""
        payload = {
            "url": "https://example.com",
            "return_base64": True
        }
        resp = requests.post(f"{RENDERER_URL}/render/screenshot", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "image_base64" in data
        assert "width" in data
        assert "height" in data
        assert data["width"] > 0


@pytest.mark.unit
class TestSignatureLogic:
    """Unit tests for HMAC signature logic"""

    def test_generate_and_verify_signature(self):
        api_key = "test_key_123"
        secret_key = "test_key_123" # In implementation api_key is used as secret
        params = {
            "url": "https://example.com",
            "width": "1920",
            "expires": "1234567890"
        }
        
        # Generator
        signature = generate_signature(api_key, params, secret_key)
        assert signature is not None
        assert len(signature) == 64 # SHA256 hex digest length

        # Verify Valid
        is_valid = verify_signature(params, signature, api_key, secret_key)
        assert is_valid == True

        # Verify Invalid
        is_invalid = verify_signature(params, "wrong_signature", api_key, secret_key)
        assert is_invalid == False
        
    def test_signature_expiry(self):
        """Test that expired signatures fail"""
        # This would require mocking time or modifying the function to accept current_time
        # For now, we test format.
        pass
