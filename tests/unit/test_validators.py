"""
Unit Tests - Validators Module
===============================
Tests for URL, email, password, and render options validation.
"""

import pytest

from app.utils.validators import (
    is_valid_email,
    is_valid_password,
    is_valid_url,
    sanitize_url,
    validate_render_options,
    validate_screenshot_options,
    validate_pdf_options,
)


class TestURLValidation:
    """Tests for URL validation."""

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert is_valid_url("http://example.com") is True

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        assert is_valid_url("https://example.com") is True

    def test_valid_url_with_path(self):
        """Test valid URL with path."""
        assert is_valid_url("https://example.com/path/to/page") is True

    def test_valid_url_with_query(self):
        """Test valid URL with query parameters."""
        assert is_valid_url("https://example.com/page?param=value") is True

    def test_valid_url_with_port(self):
        """Test valid URL with port."""
        assert is_valid_url("https://example.com:8080/page") is True

    def test_invalid_url_no_scheme(self):
        """Test invalid URL without scheme."""
        assert is_valid_url("example.com") is False

    def test_invalid_url_ftp_scheme(self):
        """Test invalid FTP URL."""
        assert is_valid_url("ftp://example.com") is False

    def test_invalid_url_javascript(self):
        """Test invalid JavaScript URL."""
        assert is_valid_url("javascript:alert(1)") is False

    def test_invalid_url_data(self):
        """Test invalid data URL."""
        assert is_valid_url("data:text/html,<script>alert(1)</script>") is False

    def test_invalid_url_localhost_blocked(self):
        """Test localhost URL is blocked by default."""
        assert is_valid_url("http://localhost") is False
        assert is_valid_url("http://127.0.0.1") is False

    def test_localhost_allowed_when_enabled(self):
        """Test localhost URL allowed when explicitly enabled."""
        assert is_valid_url("http://localhost", allow_localhost=True) is True

    def test_invalid_url_private_ip(self):
        """Test private IP addresses are blocked."""
        assert is_valid_url("http://192.168.1.1") is False
        assert is_valid_url("http://10.0.0.1") is False
        assert is_valid_url("http://172.16.0.1") is False

    def test_sanitize_url(self):
        """Test URL sanitization."""
        assert sanitize_url("  https://example.com  ") == "https://example.com"
        assert sanitize_url("HTTPS://EXAMPLE.COM") == "https://example.com"


class TestEmailValidation:
    """Tests for email validation."""

    def test_valid_email(self):
        """Test valid email addresses."""
        assert is_valid_email("user@example.com") is True
        assert is_valid_email("user.name@example.com") is True
        assert is_valid_email("user+tag@example.com") is True
        assert is_valid_email("user@subdomain.example.com") is True

    def test_invalid_email_no_at(self):
        """Test invalid email without @ symbol."""
        assert is_valid_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        assert is_valid_email("user@") is False

    def test_invalid_email_no_local(self):
        """Test invalid email without local part."""
        assert is_valid_email("@example.com") is False

    def test_invalid_email_spaces(self):
        """Test invalid email with spaces."""
        assert is_valid_email("user @example.com") is False

    def test_invalid_email_multiple_at(self):
        """Test invalid email with multiple @ symbols."""
        assert is_valid_email("user@@example.com") is False


class TestPasswordValidation:
    """Tests for password validation."""

    def test_valid_password(self):
        """Test valid password."""
        valid, errors = is_valid_password("SecurePass123!")
        assert valid is True
        assert len(errors) == 0

    def test_password_too_short(self):
        """Test password that is too short."""
        valid, errors = is_valid_password("Short1!")
        assert valid is False
        assert any("8 characters" in e for e in errors)

    def test_password_no_uppercase(self):
        """Test password without uppercase."""
        valid, errors = is_valid_password("lowercase123!")
        assert valid is False
        assert any("uppercase" in e for e in errors)

    def test_password_no_lowercase(self):
        """Test password without lowercase."""
        valid, errors = is_valid_password("UPPERCASE123!")
        assert valid is False
        assert any("lowercase" in e for e in errors)

    def test_password_no_digit(self):
        """Test password without digit."""
        valid, errors = is_valid_password("NoDigitsHere!")
        assert valid is False
        assert any("digit" in e for e in errors)

    def test_password_no_special(self):
        """Test password without special character."""
        valid, errors = is_valid_password("NoSpecial123")
        assert valid is False
        assert any("special" in e for e in errors)

    def test_password_multiple_issues(self):
        """Test password with multiple issues."""
        valid, errors = is_valid_password("weak")
        assert valid is False
        assert len(errors) > 1


class TestRenderOptionsValidation:
    """Tests for render options validation."""

    def test_valid_screenshot_options(self):
        """Test valid screenshot options."""
        options = {
            "width": 1280,
            "height": 720,
            "format": "png",
            "full_page": False,
            "delay": 1000,
        }
        valid, errors = validate_screenshot_options(options)
        assert valid is True
        assert len(errors) == 0

    def test_invalid_screenshot_width_too_small(self):
        """Test invalid screenshot width (too small)."""
        options = {"width": 50, "height": 720, "format": "png"}
        valid, errors = validate_screenshot_options(options)
        assert valid is False
        assert any("width" in e.lower() for e in errors)

    def test_invalid_screenshot_width_too_large(self):
        """Test invalid screenshot width (too large)."""
        options = {"width": 10000, "height": 720, "format": "png"}
        valid, errors = validate_screenshot_options(options)
        assert valid is False
        assert any("width" in e.lower() for e in errors)

    def test_invalid_screenshot_format(self):
        """Test invalid screenshot format."""
        options = {"width": 1280, "height": 720, "format": "bmp"}
        valid, errors = validate_screenshot_options(options)
        assert valid is False
        assert any("format" in e.lower() for e in errors)

    def test_valid_pdf_options(self):
        """Test valid PDF options."""
        options = {
            "format": "A4",
            "landscape": False,
            "print_background": True,
            "margin": {"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
        }
        valid, errors = validate_pdf_options(options)
        assert valid is True
        assert len(errors) == 0

    def test_invalid_pdf_format(self):
        """Test invalid PDF format."""
        options = {"format": "B5"}  # Invalid format
        valid, errors = validate_pdf_options(options)
        assert valid is False
        assert any("format" in e.lower() for e in errors)

    def test_default_screenshot_options(self):
        """Test that missing options get defaults."""
        options = {}
        valid, errors = validate_screenshot_options(options, apply_defaults=True)
        assert valid is True
        assert options.get("width") is not None
        assert options.get("height") is not None
        assert options.get("format") is not None

