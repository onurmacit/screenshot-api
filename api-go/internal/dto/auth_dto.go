package dto

// API Key DTOs
type APIKeyResponse struct {
	ID        string   `json:"id"`
	Name      string   `json:"name"`
	KeyPrefix string   `json:"key_prefix"`
	Scopes    []string `json:"scopes"`
	CreatedAt string   `json:"created_at"`
}

type APIKeyCreateRequest struct {
	Name      string   `json:"name" validate:"required"`
	Scopes    []string `json:"scopes"`
	ExpiresAt string   `json:"expires_at,omitempty"`
}

type APIKeyCreateResponse struct {
	ID        string `json:"id"`
	AccessKey string `json:"access_key"`
	SecretKey string `json:"secret_key"`
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
