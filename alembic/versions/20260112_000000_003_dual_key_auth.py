"""Add dual-key API authentication system

Revision ID: 003_dual_key_auth
Revises: 002
Create Date: 2026-01-12

Migration adds:
- access_key: Public identifier (safe to share in URLs)
- secret_key_encrypted: Private key for HMAC signing (encrypted)
- enforce_signing: Toggle to require signed requests
- is_legacy: Flag for old single-key system
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_dual_key_auth"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for dual-key system
    op.add_column(
        "api_keys",
        sa.Column("access_key", sa.String(32), nullable=True, unique=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("secret_key_encrypted", sa.String(512), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("enforce_signing", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "api_keys",
        sa.Column("is_legacy", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Create index for access_key lookups
    op.create_index("idx_api_keys_access_key", "api_keys", ["access_key"])

    # Make legacy columns nullable (for new dual-key entries)
    op.alter_column("api_keys", "key_hash", nullable=True)
    op.alter_column("api_keys", "key_prefix", nullable=True)


def downgrade() -> None:
    # Remove new columns
    op.drop_index("idx_api_keys_access_key", table_name="api_keys")
    op.drop_column("api_keys", "is_legacy")
    op.drop_column("api_keys", "enforce_signing")
    op.drop_column("api_keys", "secret_key_encrypted")
    op.drop_column("api_keys", "access_key")

    # Restore NOT NULL constraints on legacy columns
    op.alter_column("api_keys", "key_hash", nullable=False)
    op.alter_column("api_keys", "key_prefix", nullable=False)
