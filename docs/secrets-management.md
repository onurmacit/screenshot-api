# Secrets Management

## Overview

This project uses `age` encryption for secure secret management. Secrets are:
- Encrypted at rest in the repository
- Decrypted during deployment
- Never committed in plain text

## Quick Start

```bash
# Setup encryption (one-time)
./scripts/setup-secrets.sh

# Encrypt your .env.production
age --encrypt --recipient $(cat ~/.age/key.pub) -o .env.production.age .env.production

# Decrypt (when needed)
age --decrypt --identity ~/.age/key.txt .env.production.age > .env.production
```

## Files

| File | Purpose | Commit to Git? |
|------|---------|----------------|
| `.env.production` | Plain-text secrets | ❌ NO |
| `.env.production.age` | Encrypted secrets | ✅ YES |
| `~/.age/key.txt` | Private key | ❌ NO (store securely) |
| `~/.age/key.pub` | Public key | ✅ YES (safe to share) |

## Secrets in Use

| Secret | Description |
|--------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (Supabase) |
| `REDIS_URL` | Redis connection string (Upstash) |
| `JWT_SECRET` | JWT signing key |
| `AWS_ACCESS_KEY_ID` | DigitalOcean Spaces access key |
| `AWS_SECRET_ACCESS_KEY` | DigitalOcean Spaces secret key |
| `ADMIN_EMAILS` | Comma-separated admin email list |

## Rotating Secrets

### Automatic (for JWT_SECRET)
```bash
./scripts/emergency-key-rotation.sh JWT_SECRET
```

### Manual
```bash
# 1. Decrypt
age --decrypt --identity ~/.age/key.txt .env.production.age > .env.production

# 2. Edit
nano .env.production

# 3. Re-encrypt
age --encrypt --recipient $(cat ~/.age/key.pub) -o .env.production.age .env.production

# 4. Clean up
rm .env.production

# 5. Commit and deploy
git add .env.production.age
git commit -m "security: Rotate secrets"
git push
```

## Docker Secrets Support

The application supports Docker secrets pattern with `_FILE` suffix:

```yaml
# docker-compose.production.yml
services:
  api-go-blue:
    secrets:
      - db_url
      - jwt_secret
    environment:
      - DATABASE_URL_FILE=/run/secrets/db_url
      - JWT_SECRET_FILE=/run/secrets/jwt_secret

secrets:
  db_url:
    external: true
  jwt_secret:
    external: true
```

## GitHub Actions Integration

The deployment workflow decrypts secrets automatically:

```yaml
- name: Decrypt secrets
  run: |
    echo "${{ secrets.AGE_PRIVATE_KEY }}" > /tmp/age_key.txt
    age --decrypt --identity /tmp/age_key.txt .env.production.age > .env.production
    rm /tmp/age_key.txt
```

Required GitHub Secrets:
- `AGE_PRIVATE_KEY` - Content of `~/.age/key.txt`
- `SSH_PRIVATE_KEY` - Server SSH key
- `SERVER_IP` - Production server IP

## Emergency Procedures

### Secret Leaked in Public

1. **Immediately revoke** the compromised key in the service dashboard
2. Generate new key
3. Run emergency rotation:
   ```bash
   ./scripts/emergency-key-rotation.sh JWT_SECRET
   ```
4. Check access logs for unauthorized usage
5. Notify team

### Lost Encryption Key

If you lose `~/.age/key.txt`:
1. Generate new key pair: `age-keygen -o ~/.age/key.txt`
2. On server, re-encrypt from decrypted `.env.production`
3. Update `AGE_PRIVATE_KEY` in GitHub Secrets
4. Commit new `.env.production.age`

## Best Practices

1. **Never** commit `.env.production` (plain text)
2. **Always** use encrypted `.env.production.age`
3. **Rotate** JWT_SECRET every 90 days
4. **Audit** secret access in logs
5. **Backup** private key in secure location (not cloud storage)
6. **Limit** who has access to private key
