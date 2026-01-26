package utils

import (
	"testing"
)

func TestSignatureVerification(t *testing.T) {
	secretKey := "test-secret-key"

	// Case 1: Simple parameters
	params1 := map[string]string{
		"url":    "https://example.com",
		"width":  "1920",
		"height": "1080",
	}

	sig1 := GenerateSignature(params1, secretKey)
	if !VerifySignature(params1, secretKey, sig1) {
		t.Errorf("Signature verification failed for simple parameters")
	}

	// Case 2: Parameters with special characters (the problematic case)
	// If the frontend sends encoded URL, and backend decodes it into params,
	// GenerateSignature(params, secretKey) should work on RAW values.
	params2 := map[string]string{
		"url":    "https://example.com/path?foo=bar&baz=qux",
		"width":  "1920",
		"height": "1080",
	}

	sig2 := GenerateSignature(params2, secretKey)
	if !VerifySignature(params2, secretKey, sig2) {
		t.Errorf("Signature verification failed for parameters with special characters")
	}

	// Case 3: Verify sorting
	params3 := map[string]string{
		"z": "1",
		"a": "2",
		"m": "3",
	}
	sig3 := GenerateSignature(params3, secretKey)
	if !VerifySignature(params3, secretKey, sig3) {
		t.Errorf("Signature verification failed for unsorted parameters")
	}
}
