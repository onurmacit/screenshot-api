#!/bin/bash
set -e

KEY_NAME=$1
NEW_VALUE=$2

if [ -z "$KEY_NAME" ]; then
  echo "Usage: $0 <key_name> [new_value]"
  echo ""
  echo "Examples:"
  echo "  $0 JWT_SECRET                          # Auto-generate new JWT secret"
  echo "  $0 JWT_SECRET my-new-secret-value      # Use specific value"
  echo "  $0 DATABASE_URL postgresql://new-url   # Update database URL"
  echo ""
  echo "Common keys:"
  echo "  JWT_SECRET"
  echo "  DATABASE_URL"
  echo "  REDIS_URL"
  echo "  AWS_ACCESS_KEY_ID"
  echo "  AWS_SECRET_ACCESS_KEY"
  exit 1
fi

# Auto-generate values for known secrets
if [ -z "$NEW_VALUE" ]; then
  case "$KEY_NAME" in
    JWT_SECRET)
      NEW_VALUE=$(openssl rand -hex 32)
      echo "Generated new JWT_SECRET"
      ;;
    *)
      echo "Error: New value is required for $KEY_NAME"
      exit 1
      ;;
  esac
fi

# Check for age key
AGE_KEY="$HOME/.age/key.txt"
AGE_PUB="$HOME/.age/key.pub"

if [ ! -f "$AGE_KEY" ]; then
  echo "Error: Age key not found at $AGE_KEY"
  echo ""
  echo "Generate key with:"
  echo "  mkdir -p ~/.age"
  echo "  age-keygen -o ~/.age/key.txt"
  echo "  age-keygen -y ~/.age/key.txt > ~/.age/key.pub"
  exit 1
fi

echo "====================================="
echo "🔐 Emergency Secret Rotation"
echo "====================================="
echo ""
echo "Secret: $KEY_NAME"
echo "New value: ${NEW_VALUE:0:10}... (truncated)"
echo ""

# Check if encrypted file exists
if [ -f ".env.production.age" ]; then
  echo "Step 1: Decrypting .env.production.age"
  age --decrypt --identity "$AGE_KEY" .env.production.age > /tmp/.env.production
elif [ -f ".env.production" ]; then
  echo "Step 1: Using existing .env.production"
  cp .env.production /tmp/.env.production
else
  echo "Error: Neither .env.production nor .env.production.age found"
  exit 1
fi

# Check if key exists
if grep -q "^$KEY_NAME=" /tmp/.env.production; then
  echo "Step 2: Updating existing key"
  # Escape special characters in the new value for sed
  ESCAPED_VALUE=$(echo "$NEW_VALUE" | sed 's/[&/\]/\\&/g')
  sed -i "s|^$KEY_NAME=.*|$KEY_NAME=$ESCAPED_VALUE|" /tmp/.env.production
else
  echo "Step 2: Adding new key"
  echo "$KEY_NAME=$NEW_VALUE" >> /tmp/.env.production
fi

# Re-encrypt
echo "Step 3: Re-encrypting"
age --encrypt --recipient "$(cat $AGE_PUB)" --output .env.production.age /tmp/.env.production

# Clean up
rm /tmp/.env.production

echo ""
echo "✅ Secret rotated successfully!"
echo ""
echo "====================================="
echo "Next Steps:"
echo "====================================="
echo ""
echo "1. Commit the encrypted file:"
echo "   git add .env.production.age"
echo "   git commit -m 'security: Rotate $KEY_NAME'"
echo "   git push"
echo ""
echo "2. Deploy to production:"
echo "   # SSH to server and run deploy-go"
echo "   # Or wait for GitHub Actions"
echo ""
echo "3. Verify the application works"
echo ""

# Ask if user wants to immediately deploy
read -p "Deploy to server now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  git add .env.production.age
  git commit -m "security: Rotate $KEY_NAME"
  git push
  echo ""
  echo "✅ Pushed to GitHub. CI/CD will deploy."
fi
