#!/bin/bash
# Database migration helper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

case "$1" in
    upgrade)
        echo "Running database migrations..."
        alembic upgrade head
        echo "Migrations complete!"
        ;;
    downgrade)
        if [ -z "$2" ]; then
            echo "Downgrading by one revision..."
            alembic downgrade -1
        else
            echo "Downgrading to revision: $2"
            alembic downgrade "$2"
        fi
        echo "Downgrade complete!"
        ;;
    revision)
        if [ -z "$2" ]; then
            echo "Usage: $0 revision <message>"
            exit 1
        fi
        echo "Creating new migration..."
        alembic revision --autogenerate -m "$2"
        echo "Migration created!"
        ;;
    current)
        echo "Current revision:"
        alembic current
        ;;
    history)
        echo "Migration history:"
        alembic history
        ;;
    *)
        echo "Usage: $0 {upgrade|downgrade|revision|current|history}"
        echo ""
        echo "Commands:"
        echo "  upgrade           - Run all pending migrations"
        echo "  downgrade [rev]   - Downgrade by one revision or to specific revision"
        echo "  revision <msg>    - Create a new migration with autogenerate"
        echo "  current           - Show current revision"
        echo "  history           - Show migration history"
        exit 1
        ;;
esac

