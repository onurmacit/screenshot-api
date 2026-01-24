#!/bin/bash
set -e

echo "====================================="
echo "🔐 Secrets Setup"
echo "====================================="
echo ""

# Check if age is installed
if ! command -v age &> /dev/null; then
  echo "Installing age encryption tool..."
  
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    brew install age
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    curl -LO https://github.com/FiloSottile/age/releases/download/v1.1.1/age-v1.1.1-linux-amd64.tar.gz
    tar xzf age-v1.1.1-linux-amd64.tar.gz
    sudo mv age/age age/age-keygen /usr/local/bin/
    rm -rf age age-v1.1.1-linux-amd64.tar.gz
  else
    echo "Please install age manually: https://github.com/FiloSottile/age"
    exit 1
  fi
  
  echo "✓ age installed"
fi

# Create key directory
mkdir -p ~/.age

# Check if key exists
if [ -f ~/.age/key.txt ]; then
  echo "✓ Age key already exists at ~/.age/key.txt"
else
  echo "Generating new age key pair..."
  age-keygen -o ~/.age/key.txt
  echo "✓ Key generated at ~/.age/key.txt"
fi

# Generate public key
age-keygen -y ~/.age/key.txt > ~/.age/key.pub
echo "✓ Public key at ~/.age/key.pub"
echo ""

# Show public key
echo "Your public key (share this, it's safe):"
echo "---"
cat ~/.age/key.pub
echo "---"
echo ""

# Check for .env.production
if [ -f .env.production ]; then
  echo "Found .env.production"
  
  read -p "Encrypt .env.production? (y/N) " -n 1 -r
  echo
  
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Encrypting..."
    age --encrypt --recipient "$(cat ~/.age/key.pub)" --output .env.production.age .env.production
    echo "✓ Created .env.production.age"
    
    echo ""
    echo "You should now:"
    echo "1. Add .env.production to .gitignore"
    echo "2. Commit .env.production.age (encrypted version)"
    echo "3. Store the private key (~/.age/key.txt) securely"
    echo "4. Add private key to GitHub Secrets as AGE_PRIVATE_KEY"
  fi
else
  echo "No .env.production found."
  echo ""
  echo "Create one first, then run this script again:"
  echo "  cp .env.example .env.production"
  echo "  # Edit .env.production with your secrets"
fi

echo ""
echo "====================================="
echo "✅ Setup Complete"
echo "====================================="
echo ""
echo "Important: Back up your private key!"
echo "Location: ~/.age/key.txt"
echo ""
echo "Add to GitHub Secrets:"
echo "  Name: AGE_PRIVATE_KEY"
echo "  Value: (contents of ~/.age/key.txt)"
