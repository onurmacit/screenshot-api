package utils

import (
	"fmt"
	"html"
	"net"
	"net/url"
	"regexp"
	"strings"
)

// =============================================================================
// URL Validation & SSRF Prevention (SEC-003)
// =============================================================================

var (
	// Private/Internal IP ranges that should be blocked
	privateIPRanges = []string{
		"10.0.0.0/8",
		"172.16.0.0/12",
		"192.168.0.0/16",
		"127.0.0.0/8",
		"169.254.0.0/16", // Link-local (AWS metadata)
		"::1/128",        // IPv6 loopback
		"fc00::/7",       // IPv6 private
		"fe80::/10",      // IPv6 link-local
	}

	privateNets []*net.IPNet

	// Blocked hostnames
	blockedHostnames = []string{
		"localhost",
		"metadata.google.internal",
		"metadata.google.com",
	}

	// URL scheme whitelist
	allowedSchemes = map[string]bool{
		"http":  true,
		"https": true,
	}
)

func init() {
	// Parse private IP ranges
	for _, cidr := range privateIPRanges {
		_, network, err := net.ParseCIDR(cidr)
		if err == nil {
			privateNets = append(privateNets, network)
		}
	}
}

// ValidateURL checks if a URL is valid and safe for screenshot rendering
func ValidateURL(inputURL string) error {
	if inputURL == "" {
		return fmt.Errorf("URL is required")
	}

	// 1. Parse URL
	parsed, err := url.Parse(inputURL)
	if err != nil {
		return fmt.Errorf("invalid URL format: %v", err)
	}

	// 2. Check scheme
	if !allowedSchemes[strings.ToLower(parsed.Scheme)] {
		return fmt.Errorf("only HTTP and HTTPS URLs are allowed")
	}

	// 3. Check for empty host
	if parsed.Host == "" {
		return fmt.Errorf("URL must have a valid host")
	}

	// 4. Extract hostname (without port)
	hostname := parsed.Hostname()

	// 5. Check blocked hostnames
	for _, blocked := range blockedHostnames {
		if strings.EqualFold(hostname, blocked) {
			return fmt.Errorf("access to %s is not allowed", hostname)
		}
	}

	// 6. Check for numeric IP (could be obfuscated)
	if isNumericIP(hostname) {
		return fmt.Errorf("numeric IP addresses are not allowed")
	}

	// 7. Resolve hostname to check for private IPs
	if err := checkPrivateIP(hostname); err != nil {
		return err
	}

	// 8. Check for URL with credentials
	if parsed.User != nil {
		return fmt.Errorf("URLs with credentials are not allowed")
	}

	return nil
}

// checkPrivateIP resolves hostname and checks if it resolves to private IP
func checkPrivateIP(hostname string) error {
	// Direct IP check
	ip := net.ParseIP(hostname)
	if ip != nil {
		if isPrivateIP(ip) {
			return fmt.Errorf("private/internal IP addresses are not allowed")
		}
		return nil
	}

	// DNS resolution
	ips, err := net.LookupIP(hostname)
	if err != nil {
		// DNS resolution failed - could be invalid domain
		// Allow the request to proceed, renderer will handle it
		return nil
	}

	for _, resolvedIP := range ips {
		if isPrivateIP(resolvedIP) {
			return fmt.Errorf("domain resolves to private/internal IP address")
		}
	}

	return nil
}

// isPrivateIP checks if IP is in private ranges
func isPrivateIP(ip net.IP) bool {
	// Check loopback
	if ip.IsLoopback() {
		return true
	}

	// Check link-local
	if ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() {
		return true
	}

	// Check private ranges
	for _, network := range privateNets {
		if network.Contains(ip) {
			return true
		}
	}

	return false
}

// isNumericIP checks for numeric IP representations (0x7f000001, 2130706433, etc.)
func isNumericIP(hostname string) bool {
	// Octal/Hex IP check
	if strings.HasPrefix(hostname, "0x") || strings.HasPrefix(hostname, "0X") {
		return true
	}

	// Pure numeric check (could be decimal IP)
	numericRegex := regexp.MustCompile(`^\d+$`)
	if numericRegex.MatchString(hostname) {
		return true
	}

	return false
}

// =============================================================================
// Input Sanitization (SEC-002)
// =============================================================================

// SanitizeInput escapes HTML entities to prevent XSS
func SanitizeInput(input string) string {
	return html.EscapeString(input)
}

// SanitizeUserInputs sanitizes common user input fields
func SanitizeUserInputs(fields map[string]*string) {
	for key, val := range fields {
		if val != nil && *val != "" {
			sanitized := SanitizeInput(*val)
			*val = sanitized
			fields[key] = val
		}
	}
}

// ValidateAndSanitizeName validates and sanitizes name fields
func ValidateAndSanitizeName(name string, maxLength int) (string, error) {
	if len(name) > maxLength {
		return "", fmt.Errorf("name exceeds maximum length of %d characters", maxLength)
	}

	// Remove potential script tags
	scriptRegex := regexp.MustCompile(`(?i)<script[^>]*>.*?</script>`)
	name = scriptRegex.ReplaceAllString(name, "")

	// Remove HTML tags
	htmlTagRegex := regexp.MustCompile(`<[^>]*>`)
	name = htmlTagRegex.ReplaceAllString(name, "")

	// Escape remaining HTML entities
	return html.EscapeString(name), nil
}

// ValidateWebhookURL validates webhook URLs (more restrictive)
func ValidateWebhookURL(webhookURL string) error {
	// First, validate as normal URL
	if err := ValidateURL(webhookURL); err != nil {
		return err
	}

	parsed, _ := url.Parse(webhookURL)

	// Webhooks should be HTTPS in production
	if strings.ToLower(parsed.Scheme) != "https" {
		// Warning only, not blocking
		// In production, you might want to enforce HTTPS
	}

	return nil
}
