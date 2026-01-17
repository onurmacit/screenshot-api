package dto

import "time"

// API Key DTOs
type APIKeyResponse struct {
	ID             string     `json:"key_id"`
	Name           string     `json:"name"`
	KeyPrefix      string     `json:"key_prefix"`
	AccessKey      string     `json:"access_key,omitempty"` // For listing with access key
	SecretKey      *string    `json:"secret_key,omitempty"` // For listing exposed secrets
	Scopes         []string   `json:"scopes"`
	EnforceSigning bool       `json:"enforce_signing"`
	IsActive       bool       `json:"is_active"`
	LastUsedAt     *time.Time `json:"last_used_at"`
	CreatedAt      time.Time  `json:"created_at"`
	ExpiresAt      *time.Time `json:"expires_at"`
}

type APIKeyCreateRequest struct {
	Name           string     `json:"name" validate:"required"`
	Scopes         []string   `json:"scopes"`
	ExpiresAt      *time.Time `json:"expires_at,omitempty"`
	EnforceSigning bool       `json:"enforce_signing"`
}

type APIKeyCreateResponse struct {
	ID             string     `json:"key_id"`
	AccessKey      string     `json:"access_key"`
	SecretKey      string     `json:"secret_key"`
	Name           string     `json:"name"`
	Scopes         []string   `json:"scopes"`
	EnforceSigning bool       `json:"enforce_signing"`
	CreatedAt      time.Time  `json:"created_at"`
	ExpiresAt      *time.Time `json:"expires_at"`
}

// Auth DTOs
type LoginRequest struct {
	Email    string `json:"email" validate:"required,email"`
	Password string `json:"password" validate:"required"`
}

type LoginResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
}

type RegisterRequest struct {
	Email    string `json:"email" validate:"required,email"`
	Password string `json:"password" validate:"required,min=8"`
	FullName string `json:"full_name"`
}

type RegisterResponse struct {
	UserID       string `json:"user_id"`
	Email        string `json:"email"`
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
}

type RefreshTokenRequest struct {
	RefreshToken string `json:"refresh_token" validate:"required"`
}

type APIKeyEnforceSigningRequest struct {
	Enforce bool `json:"enforce"`
}

// Social Login DTOs
type SocialLoginRequest struct {
	Provider string `json:"provider" validate:"required"` // "google" or "github"
	Token    string `json:"token" validate:"required"`
	FullName string `json:"full_name,omitempty"`
}
