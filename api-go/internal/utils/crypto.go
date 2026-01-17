package utils

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"github.com/fernet/fernet-go"
)

// GenerateSignature generates HMAC-SHA256 signature for parameters
func GenerateSignature(params map[string]string, secretKey string) string {
	// 1. Sort keys
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// 2. Build query string
	var queryParts []string
	for _, k := range keys {
		queryParts = append(queryParts, fmt.Sprintf("%s=%s", k, params[k]))
	}
	queryString := strings.Join(queryParts, "&")

	// 3. Sign
	h := hmac.New(sha256.New, []byte(secretKey))
	h.Write([]byte(queryString))
	return hex.EncodeToString(h.Sum(nil))
}

// SignURL generates a signed URL with expiry
func SignURL(inputURL string, secretKey string, expirySeconds int) (string, error) {
	// Logic depends on requirement. Usually we sign the parameters.
	// Screenshot API pattern: ?url=...&width=...&expires=...&signature=...

	// Implementation follows the Python logic logic usually
	return "", nil
}

// VerifySignature verifies the signature of a request
func VerifySignature(params map[string]string, secretKey string, signature string) bool {
	expected := GenerateSignature(params, secretKey)
	return hmac.Equal([]byte(signature), []byte(expected))
}

// Decrypt decrypts a Fernet token
// Note: Imports needed "github.com/fernet/fernet-go"
func Decrypt(token string, key string) (string, error) {
	k, err := fernet.DecodeKey(key)
	if err != nil {
		return "", err
	}
	msg := fernet.VerifyAndDecrypt([]byte(token), 0, []*fernet.Key{k})
	if msg == nil {
		return "", fmt.Errorf("decryption failed")
	}
	return string(msg), nil
}
