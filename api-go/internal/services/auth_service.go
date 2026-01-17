package services

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/lib/pq"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"gorm.io/gorm"
)

type AuthService struct {
	db    *gorm.DB
	cache *CacheService
	cfg   *config.Config
}

func NewAuthService(db *gorm.DB, cfg *config.Config) *AuthService {
	return &AuthService{
		db:    db,
		cache: NewCacheService(cfg),
		cfg:   cfg,
	}
}

// === Authentication ===

func (s *AuthService) Register(req dto.RegisterRequest, ip, userAgent string) (*dto.RegisterResponse, error) {
	// 1. Check duplicate email
	var exists bool
	s.db.Model(&models.User{}).Select("count(*) > 0").Where("email = ?", req.Email).Find(&exists)
	if exists {
		return nil, &utils.AppError{Code: 409, Message: "Email already exists"}
	}

	// 2. Hash Password
	hashed, err := utils.HashPassword(req.Password)
	if err != nil {
		return nil, &utils.AppError{Code: 500, Message: "Failed to hash password"}
	}

	// 3. Create User
	user := models.User{
		Email:        req.Email,
		PasswordHash: &hashed,
		FullName:     &req.FullName,
		IsActive:     true,
		PlanID:       1, // Default Plan
	}

	if err := s.db.Create(&user).Error; err != nil {
		return nil, &utils.AppError{Code: 500, Message: "Failed to create user"}
	}

	// 4. Generate Tokens
	accessToken, refreshToken, err := s.generateTokens(user.ID, user.Email, ip, userAgent)
	if err != nil {
		return nil, err
	}

	return &dto.RegisterResponse{
		UserID:       user.ID.String(),
		Email:        user.Email,
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
	}, nil
}

func (s *AuthService) Login(req dto.LoginRequest, ip, userAgent string) (*dto.LoginResponse, error) {
	var user models.User
	if err := s.db.Where("email = ?", req.Email).First(&user).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, &utils.AppError{Code: 401, Message: "Invalid credentials"}
		}
		return nil, err
	}

	if user.PasswordHash == nil || !utils.CheckPasswordHash(req.Password, *user.PasswordHash) {
		return nil, &utils.AppError{Code: 401, Message: "Invalid credentials"}
	}

	if !user.IsActive {
		return nil, &utils.AppError{Code: 403, Message: "Account inactive"}
	}

	accessToken, refreshToken, err := s.generateTokens(user.ID, user.Email, ip, userAgent)
	if err != nil {
		return nil, err
	}

	return &dto.LoginResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		TokenType:    "bearer",
		ExpiresIn:    s.cfg.JWTAccessTokenExpiry * 60,
	}, nil
}

// SocialLogin handles Google/GitHub OAuth authentication
func (s *AuthService) SocialLogin(req dto.SocialLoginRequest, ip, userAgent string) (*dto.LoginResponse, error) {
	var email string
	var fullName string

	// Verify token with provider
	switch req.Provider {
	case "google":
		// Verify Google ID token
		resp, err := utils.HTTPGet(fmt.Sprintf("https://oauth2.googleapis.com/tokeninfo?id_token=%s", req.Token))
		if err != nil {
			return nil, &utils.AppError{Code: 401, Message: "Failed to verify Google token"}
		}
		email = resp["email"].(string)
		if name, ok := resp["name"].(string); ok {
			fullName = name
		}
	case "github":
		// Verify GitHub access token
		resp, err := utils.HTTPGetWithAuth("https://api.github.com/user", req.Token)
		if err != nil {
			return nil, &utils.AppError{Code: 401, Message: "Failed to verify GitHub token"}
		}
		if e, ok := resp["email"].(string); ok && e != "" {
			email = e
		} else {
			// Fetch emails if not in public profile
			emailsResp, err := utils.HTTPGetWithAuthArray("https://api.github.com/user/emails", req.Token)
			if err == nil && len(emailsResp) > 0 {
				for _, e := range emailsResp {
					if emailMap, ok := e.(map[string]interface{}); ok {
						if primary, ok := emailMap["primary"].(bool); ok && primary {
							email = emailMap["email"].(string)
							break
						}
					}
				}
				if email == "" && len(emailsResp) > 0 {
					if emailMap, ok := emailsResp[0].(map[string]interface{}); ok {
						email = emailMap["email"].(string)
					}
				}
			}
		}
		if name, ok := resp["name"].(string); ok {
			fullName = name
		}
	default:
		return nil, &utils.AppError{Code: 400, Message: "Unsupported provider"}
	}

	if email == "" {
		return nil, &utils.AppError{Code: 401, Message: "Could not retrieve email from provider"}
	}

	// Find or create user
	var user models.User
	if err := s.db.Where("email = ?", email).First(&user).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			// Create new user
			socialPwdPlaceholder := "social_auth_no_password"
			if req.FullName != "" {
				fullName = req.FullName
			}
			user = models.User{
				Email:        email,
				PasswordHash: &socialPwdPlaceholder,
				FullName:     &fullName,
				IsActive:     true,
				PlanID:       1, // Free plan
			}
			if err := s.db.Create(&user).Error; err != nil {
				return nil, &utils.AppError{Code: 500, Message: "Failed to create user"}
			}
			// Create default API key for new social user
			s.createDefaultAPIKey(user.ID)
		} else {
			return nil, err
		}
	}

	if !user.IsActive {
		return nil, &utils.AppError{Code: 403, Message: "Account inactive"}
	}

	// Generate tokens
	accessToken, refreshToken, err := s.generateTokens(user.ID, user.Email, ip, userAgent)
	if err != nil {
		return nil, err
	}

	return &dto.LoginResponse{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		TokenType:    "bearer",
		ExpiresIn:    s.cfg.JWTAccessTokenExpiry * 60,
	}, nil
}

func (s *AuthService) RefreshToken(ctx context.Context, refreshToken, ip, userAgent string) (*dto.LoginResponse, error) {
	// 1. Validate Token Signature
	_, err := utils.ValidateToken(refreshToken, s.cfg.JWTSecretKey)
	if err != nil {
		return nil, &utils.AppError{Code: 401, Message: "Invalid refresh token"}
	}

	// 2. Validate against DB (Stateful)
	tokenHashBytes := sha256.Sum256([]byte(refreshToken))
	tokenHash := hex.EncodeToString(tokenHashBytes[:])

	var rtModel models.RefreshToken
	if err := s.db.Preload("User").Where("token_hash = ?", tokenHash).First(&rtModel).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			// Token not found -> possibly revoked or never existed (reuse detection?)
			return nil, &utils.AppError{Code: 401, Message: "Invalid or revoked refresh token"}
		}
		return nil, err
	}

	if rtModel.IsRevoked {
		// potential reuse attack
		return nil, &utils.AppError{Code: 401, Message: "Token revoked"}
	}

	// Check expiry
	if time.Now().After(rtModel.ExpiresAt) {
		return nil, &utils.AppError{Code: 401, Message: "Token expired"}
	}

	user := rtModel.User
	if !user.IsActive {
		return nil, &utils.AppError{Code: 403, Message: "Account inactive"}
	}

	// 3. Rotate Token (Revoke old, Issue new)
	// Security best practice: Revoke used refresh token
	rtModel.IsRevoked = true
	s.db.Save(&rtModel)

	// Issue new
	accessToken, newRefreshToken, err := s.generateTokens(user.ID, user.Email, ip, userAgent)
	if err != nil {
		return nil, err
	}

	return &dto.LoginResponse{
		AccessToken:  accessToken,
		RefreshToken: newRefreshToken,
		TokenType:    "bearer",
		ExpiresIn:    s.cfg.JWTAccessTokenExpiry * 60,
	}, nil
}

func (s *AuthService) Logout(ctx context.Context, refreshToken string) error {
	// 1. Validate (Optional just hash it)
	tokenHashBytes := sha256.Sum256([]byte(refreshToken))
	tokenHash := hex.EncodeToString(tokenHashBytes[:])

	// 2. Revoke in DB
	// We don't verify signature necessarily, just find by hash and revoke.
	// But validating signature prevents DoS on DB?
	// Hash lookup is fast index.

	if err := s.db.Model(&models.RefreshToken{}).Where("token_hash = ?", tokenHash).Update("is_revoked", true).Error; err != nil {
		return err
	}
	return nil
}

func (s *AuthService) generateTokens(userID uuid.UUID, email, ip, userAgent string) (string, string, error) {
	// Access Token
	accessClaims := utils.JWTClaims{
		UserID: userID.String(),
		Email:  email,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Duration(s.cfg.JWTAccessTokenExpiry) * time.Minute)),
			Issuer:    "screenshot-api",
		},
	}
	accessToken, err := utils.GenerateToken(accessClaims, s.cfg.JWTSecretKey)
	if err != nil {
		return "", "", err
	}

	// Refresh Token
	refreshExpiry := time.Now().Add(time.Duration(s.cfg.JWTRefreshTokenExpiry) * 24 * time.Hour)
	refreshClaims := utils.JWTClaims{
		UserID: userID.String(),
		Email:  email,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(refreshExpiry),
			Issuer:    "screenshot-api",
		},
	}
	refreshToken, err := utils.GenerateToken(refreshClaims, s.cfg.JWTSecretKey)
	if err != nil {
		return "", "", err
	}

	// Save Refresh Token to DB
	tokenHashBytes := sha256.Sum256([]byte(refreshToken))
	tokenHash := hex.EncodeToString(tokenHashBytes[:])

	rtModel := models.RefreshToken{
		ID:         uuid.New(),
		UserID:     userID,
		TokenHash:  tokenHash,
		ExpiresAt:  refreshExpiry,
		IPAddress:  &ip,
		DeviceInfo: &userAgent,
		IsRevoked:  false,
	}

	if err := s.db.Create(&rtModel).Error; err != nil {
		return "", "", err
	}

	return accessToken, refreshToken, nil
}

// === API Key Management ===

func (s *AuthService) CreateAPIKey(ctx context.Context, req dto.APIKeyCreateRequest, userID uuid.UUID) (*dto.APIKeyCreateResponse, error) {
	// 1. Generate Keys
	// Access Key: string (32 chars)
	// Legacy: Just random hex
	randomBytes := make([]byte, 16) // 32 chars hex
	if _, err := rand.Read(randomBytes); err != nil {
		return nil, err
	}
	accessKey := hex.EncodeToString(randomBytes)

	// Secret Key: sk_live_... (48 chars random)
	secretBytes := make([]byte, 32)
	if _, err := rand.Read(secretBytes); err != nil {
		return nil, err
	}
	secretKeyRaw := fmt.Sprintf("sk_live_%s", hex.EncodeToString(secretBytes))

	// 2. Hash & Encrypt
	keyHash := sha256.Sum256([]byte(accessKey))
	keyHashStr := hex.EncodeToString(keyHash[:])

	// Encrypt Secret Key for storage (Dual Key)
	encryptedSecret, err := utils.Encrypt(secretKeyRaw, s.cfg.SecretKeyEncryptionKey)
	if err != nil {
		// Log error but proceed? No, critical.
		// If SecretKeyEncryptionKey is missing, we must fail.
		return nil, &utils.AppError{Code: 500, Message: fmt.Sprintf("Encryption failed: %v", err)}
	}

	// 3. Create API Key Record
	apiKey := &models.APIKey{
		UserID:             userID,
		Name:               &req.Name,
		AccessKey:          accessKey,
		SecretKey:          "REDACTED", // Legacy field, not used
		SecretKeyEncrypted: &encryptedSecret,
		KeyHash:            keyHashStr, // Note: We hash Access Key, not secret key in Dual Key??
		// WAIT: In Dual Key (pk + sk):
		// Request matches PK to find record. Then verifies SK against Hash?
		// OR: Is PK public and SK secret?
		// User sends SK in header? Usually "Authorization: Bearer <SK>".
		// Python implementation:
		// "APIKeyAuth": gets "X-API-Key". Hashed it. Finds key by hash.
		// If User sends SK in header, then we hash SK.
		// BUT `CreateAPIKey` generates PK and SK?
		// Let's re-read ValidateAPIKey logic.
		// ValidateAPIKey hashes the header value.
		// So the header value MUST be what we hashed.
		// Is header value PK or SK?
		// If I use `sk_live_...` as key, then `KeyHash` stores hash of `sk_live_...`.
		// `AccessKey` is just for display/listing if we want.

		// In ScreenshotOne/Stripe:
		// PK is public (js). SK is secret.
		// If header is `X-API-Key`, it's usually the SK.
		// So we hash `secretKeyRaw`.

		KeyPrefix:      accessKey[:10], // Fits varchar(10)
		Scopes:         pq.StringArray(req.Scopes),
		EnforceSigning: req.EnforceSigning,
		IsActive:       true,
		ExpiresAt:      req.ExpiresAt,
	}

	// AccessKey = Public Key (pk_...) stored plainly.

	apiKey.ID = uuid.New()
	apiKey.KeyHash = fmt.Sprintf("%x", sha256.Sum256([]byte(secretKeyRaw)))

	if err := s.db.Create(apiKey).Error; err != nil {
		return nil, err
	}

	return &dto.APIKeyCreateResponse{
		ID:             apiKey.ID.String(),
		AccessKey:      accessKey,
		SecretKey:      secretKeyRaw, // Returned only once
		Name:           req.Name,
		Scopes:         req.Scopes,
		EnforceSigning: apiKey.EnforceSigning,
		CreatedAt:      apiKey.CreatedAt,
		ExpiresAt:      apiKey.ExpiresAt,
	}, nil
}

func (s *AuthService) ListAPIKeys(ctx context.Context, userID uuid.UUID) ([]dto.APIKeyResponse, error) {
	var keys []models.APIKey
	if err := s.db.Where("user_id = ? AND is_active = ?", userID, true).Order("created_at desc").Find(&keys).Error; err != nil {
		return nil, err
	}

	var response []dto.APIKeyResponse
	for _, k := range keys {
		name := ""
		if k.Name != nil {
			name = *k.Name
		}

		// Decrypt secret if available
		var secretKeyDecrypted *string
		if k.SecretKeyEncrypted != nil {
			decrypted, err := utils.Decrypt(*k.SecretKeyEncrypted, s.cfg.SecretKeyEncryptionKey)
			if err == nil {
				// Mask it partially? Or full?
				// Python implementation returns decrypted key in List. Allows copying again.
				// "Returns a list of API keys including decrypted secret keys"
				secretKeyDecrypted = &decrypted
			}
		}

		response = append(response, dto.APIKeyResponse{
			ID:             k.ID.String(),
			Name:           name,
			KeyPrefix:      k.KeyPrefix,
			AccessKey:      k.AccessKey,
			SecretKey:      secretKeyDecrypted,
			Scopes:         []string(k.Scopes),
			EnforceSigning: k.EnforceSigning,
			IsActive:       k.IsActive,
			LastUsedAt:     k.LastUsedAt,
			CreatedAt:      k.CreatedAt,
			ExpiresAt:      k.ExpiresAt,
		})
	}
	return response, nil
}

func (s *AuthService) DeleteAPIKey(ctx context.Context, userID uuid.UUID, keyID string) error {
	var key models.APIKey
	if err := s.db.Where("id = ? AND user_id = ?", keyID, userID).First(&key).Error; err != nil {
		return utils.ErrNotFound
	}

	// Hard delete or Soft delete?
	// Python does: delete_api_key in service. Actually python impl not shown fully but likely deletion or inactive.
	// Previous Go implementation set IsActive=false. Stick to that.
	key.IsActive = false
	if err := s.db.Save(&key).Error; err != nil {
		return err
	}

	// Cache Invalidation
	s.cache.Delete(ctx, fmt.Sprintf("apikey:%s", key.KeyHash))
	return nil
}

func (s *AuthService) ToggleEnforceSigning(ctx context.Context, userID uuid.UUID, keyID string, enforce bool) (*dto.APIKeyResponse, error) {
	var key models.APIKey
	if err := s.db.Where("id = ? AND user_id = ?", keyID, userID).First(&key).Error; err != nil {
		return nil, utils.ErrNotFound
	}

	key.EnforceSigning = enforce
	if err := s.db.Save(&key).Error; err != nil {
		return nil, err
	}

	// Invalidate Cache
	s.cache.Delete(ctx, fmt.Sprintf("apikey:%s", key.KeyHash))

	// Return response
	name := ""
	if key.Name != nil {
		name = *key.Name
	}

	return &dto.APIKeyResponse{
		ID:             key.ID.String(),
		Name:           name,
		KeyPrefix:      key.KeyPrefix,
		AccessKey:      key.AccessKey,
		Scopes:         key.Scopes,
		EnforceSigning: key.EnforceSigning,
		IsActive:       key.IsActive,
		LastUsedAt:     key.LastUsedAt,
		CreatedAt:      key.CreatedAt,
		ExpiresAt:      key.ExpiresAt,
	}, nil
}

// ValidateAPIKey validates an API key and returns the user and key (Legacy/Hybrid)
func (s *AuthService) ValidateAPIKey(ctx context.Context, apiKey string) (*models.User, *models.APIKey, error) {
	// 1. Identify key type/lookup strategy
	// Check if input is potentially a Hash (64 chars hex) or a Raw Key
	// If it matches KeyHash directly (Legacy Playground credential), use it.
	// Otherwise, hash it and check.

	hashedInput := sha256.New()
	hashedInput.Write([]byte(apiKey))
	keyHashFromInput := hex.EncodeToString(hashedInput.Sum(nil))

	// Optimistic Check: Is input ITSELF the key_hash? (length 64)
	var queryKey string
	if len(apiKey) == 64 {
		// Possibly a hash. Check validity? Logic: Try both or check cache.
		// We'll trust DB lookup.
		// NOTE: If Raw key is 64 chars, we might have collision/ambiguity?
		// Raw keys are usually shorter (32-50 chars). Hash is 64.
		// So if len=64, likely it IS the hash.
		queryKey = apiKey
	} else {
		queryKey = keyHashFromInput
	}
	// Fallback/Dual Check?
	// To be safe: If user sends Raw Key that happens to be 64 chars?
	// We should probably check:
	// Where("key_hash = ? OR key_hash = ?", apiKey, keyHashFromInput)
	// But `queryKey` logic assumes one.

	// Let's implement robust dual check:
	// Try `key_hash = apiKey` (Direct).
	// If not found, try `key_hash = hash(apiKey)`.

	// 2. Check cache first (Try keyHashFromInput - standard flow)
	user, key, err := s.cache.GetAPIKey(ctx, keyHashFromInput)
	if err == nil && user != nil && key != nil {
		return user, key, nil
	}
	// Try cache with apiKey (if it's a hash)
	if queryKey == apiKey {
		user, key, err := s.cache.GetAPIKey(ctx, apiKey)
		if err == nil && user != nil && key != nil {
			return user, key, nil
		}
	}

	// 3. Query database
	var apiKeyModel models.APIKey

	// Strategy: Search for EITHER matches
	err = s.db.Preload("User").Preload("User.Plan").
		Where("key_hash = ? OR key_hash = ?", apiKey, keyHashFromInput).
		First(&apiKeyModel).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil, utils.ErrInvalidAPIKey
		}
		return nil, nil, err
	}

	// 4. Validate
	if !apiKeyModel.IsActive {
		return nil, nil, utils.ErrInvalidAPIKey
	}

	if apiKeyModel.IsExpired() {
		return nil, nil, utils.ErrAPIKeyExpired
	}

	// 5. Update last used (async)
	// 6. Cache result (Cache under the Hashed Key to normalize?)
	// If user used Hash(Direct), we should cache under Hash(Direct).
	_ = s.cache.SetAPIKey(ctx, apiKeyModel.KeyHash, &apiKeyModel.User, &apiKeyModel)

	return &apiKeyModel.User, &apiKeyModel, nil
}

func (s *AuthService) GetUserByID(ctx context.Context, userID string) (*models.User, error) {
	// 1. Try Cache
	// TODO: Add User Cache logic (PrefixUser)

	// 2. DB
	var user models.User
	if err := s.db.Preload("Plan").Where("id = ?", userID).First(&user).Error; err != nil {
		return nil, err
	}

	return &user, nil
}

func (s *AuthService) updateLastUsed(keyID interface{}) {
	s.db.Model(&models.APIKey{}).Where("id = ?", keyID).Update("last_used_at", gorm.Expr("NOW()"))
}

func (s *AuthService) GetOrCreateDemoUser(ctx context.Context) (*models.User, error) {
	email := "demo@screenshotbeam.com"
	var user models.User

	err := s.db.Where("email = ?", email).First(&user).Error
	if err == nil {
		return &user, nil
	}

	if errors.Is(err, gorm.ErrRecordNotFound) {
		name := "Demo User"
		user = models.User{
			Email:    email,
			FullName: &name,
			IsActive: true,
			PlanID:   1,
		}
		if err := s.db.Create(&user).Error; err != nil {
			return nil, err
		}
		return &user, nil
	}

	return nil, err
}

// createDefaultAPIKey creates a default API key for new users
func (s *AuthService) createDefaultAPIKey(userID uuid.UUID) {
	// Generate Keys
	randomBytes := make([]byte, 12)
	if _, err := rand.Read(randomBytes); err != nil {
		return
	}
	accessKey := fmt.Sprintf("pk_live_%s", hex.EncodeToString(randomBytes))

	secretBytes := make([]byte, 32)
	if _, err := rand.Read(secretBytes); err != nil {
		return
	}
	secretKeyRaw := fmt.Sprintf("sk_live_%s", hex.EncodeToString(secretBytes))

	keyHash := sha256.Sum256([]byte(accessKey))
	keyHashStr := hex.EncodeToString(keyHash[:])

	encryptedSecret, err := utils.Encrypt(secretKeyRaw, s.cfg.SecretKeyEncryptionKey)
	if err != nil {
		return
	}

	name := "Default"
	apiKey := &models.APIKey{
		UserID:             userID,
		Name:               &name,
		AccessKey:          accessKey,
		SecretKey:          "REDACTED",
		SecretKeyEncrypted: &encryptedSecret,
		KeyHash:            keyHashStr,
		KeyPrefix:          accessKey[:10],
		Scopes:             pq.StringArray{"renders:read", "renders:write"},
		EnforceSigning:     false,
		IsActive:           true,
		ID:                 uuid.New(),
	}

	s.db.Create(apiKey)
}
