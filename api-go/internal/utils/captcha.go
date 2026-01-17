package utils

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"time"
)

type TurnstileResponse struct {
	Success bool     `json:"success"`
	Errors  []string `json:"error-codes"`
}

var TurnstileURL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

func VerifyTurnstile(token string, secret string, ip string) bool {
	client := &http.Client{Timeout: 10 * time.Second}

	data := url.Values{}
	data.Set("secret", secret)
	data.Set("response", token)
	if ip != "" {
		data.Set("remoteip", ip)
	}

	resp, err := client.PostForm(TurnstileURL, data)
	if err != nil {
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return false
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return false
	}

	var result TurnstileResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return false
	}

	return result.Success
}
