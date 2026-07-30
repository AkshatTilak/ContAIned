"""v6_user_identity_invites

Revision ID: c8d3e4f5a6b7
Revises: b7c2d3e4f5a6
Create Date: 2026-07-28 17:30:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b7c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    columns = [c["name"] for c in _inspector().get_columns(table)]
    return column in columns


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. Create user_identities
    if not _has_table("user_identities"):
        op.create_table(
            "user_identities",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("provider_id", sa.String(255), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(), default=datetime.utcnow),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("provider", "provider_id", name="uq_user_identity_provider"),
        )

    # 2. Create user_invites
    if not _has_table("user_invites"):
        op.create_table(
            "user_invites",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False, index=True),
            sa.Column("token_hash", sa.String(255), nullable=False, index=True),
            sa.Column("platform_role", sa.String(20), nullable=False, server_default="member"),
            sa.Column("hub_grants_json", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(), nullable=True),
            sa.Column("accepted_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resend_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), default=datetime.utcnow),
        )

    # Partial unique index for one open invite per email
    indexes = [idx["name"] for idx in _inspector().get_indexes("user_invites")] if _has_table("user_invites") else []
    if "uq_user_invites_open_email" not in indexes:
        if is_sqlite:
            op.create_index(
                "uq_user_invites_open_email",
                "user_invites",
                ["email"],
                unique=True,
                sqlite_where=sa.text("status = 'pending'"),
            )
        else:
            op.create_index(
                "uq_user_invites_open_email",
                "user_invites",
                ["email"],
                unique=True,
                postgresql_where=sa.text("status = 'pending'"),
            )

    # 3. Create password_reset_tokens
    if not _has_table("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(64), nullable=False, index=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), default=datetime.utcnow),
        )

    # 4. Add new columns to users
    with op.batch_alter_table("users") as batch_op:
        if not _has_column("users", "platform_role"):
            batch_op.add_column(sa.Column("platform_role", sa.String(20), nullable=True))
        if not _has_column("users", "status"):
            batch_op.add_column(sa.Column("status", sa.String(20), nullable=True))
        if not _has_column("users", "password_hash"):
            batch_op.add_column(sa.Column("password_hash", sa.String(255), nullable=True))
        if not _has_column("users", "password_updated_at"):
            batch_op.add_column(sa.Column("password_updated_at", sa.DateTime(), nullable=True))
        if not _has_column("users", "approved_by"):
            batch_op.add_column(sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id", name="fk_users_approved_by", ondelete="SET NULL"), nullable=True))

        if not _has_column("users", "approved_at"):
            batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        if not _has_column("users", "failed_login_count"):
            batch_op.add_column(sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
        if not _has_column("users", "locked_until"):
            batch_op.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))

    # 5. Backfills & Column Cleanup
    if _has_column("users", "role"):
        bind.execute(sa.text("""
            UPDATE users SET platform_role = CASE
                WHEN role = 'admin' THEN 'admin'
                ELSE 'member'
            END WHERE platform_role IS NULL;
        """))
    bind.execute(sa.text("UPDATE users SET platform_role = 'member' WHERE platform_role IS NULL;"))

    if _has_column("users", "is_active"):
        bind.execute(sa.text("""
            UPDATE users SET status = CASE
                WHEN is_active IS TRUE OR CAST(is_active AS VARCHAR) = '1' THEN 'active'
                ELSE 'suspended'
            END WHERE status IS NULL;
        """))
    bind.execute(sa.text("UPDATE users SET status = 'active' WHERE status IS NULL;"))

    if _has_column("users", "provider") and _has_column("users", "provider_id"):
        users_result = bind.execute(sa.text("""
            SELECT id, provider, provider_id, email, created_at FROM users
            WHERE provider IS NOT NULL AND provider_id IS NOT NULL;
        """)).fetchall()

        for u in users_result:
            u_id, u_provider, u_provider_id, u_email, u_created_at = u
            existing = bind.execute(sa.text("""
                SELECT id FROM user_identities WHERE provider = :p AND provider_id = :pid
            """), {"p": u_provider, "pid": u_provider_id}).fetchone()
            if not existing:
                bind.execute(sa.text("""
                    INSERT INTO user_identities (id, user_id, provider, provider_id, email, created_at)
                    VALUES (:id, :user_id, :provider, :provider_id, :email, :created_at)
                """), {
                    "id": str(uuid.uuid4()),
                    "user_id": u_id,
                    "provider": u_provider,
                    "provider_id": u_provider_id,
                    "email": (u_email or "").strip().lower(),
                    "created_at": u_created_at or datetime.utcnow(),
                })

    bind.execute(sa.text("UPDATE users SET email = lower(trim(email)) WHERE email IS NOT NULL;"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("platform_role", nullable=False, server_default="member")
        batch_op.alter_column("status", nullable=False, server_default="pending")

        if _has_column("users", "role"):
            batch_op.drop_column("role")
        if _has_column("users", "is_active"):
            batch_op.drop_column("is_active")
        if _has_column("users", "provider"):
            batch_op.drop_column("provider")
        if _has_column("users", "provider_id"):
            batch_op.drop_column("provider_id")



def downgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("users") as batch_op:
        if not _has_column("users", "role"):
            batch_op.add_column(sa.Column("role", sa.String(20), nullable=True, server_default="viewer"))
        if not _has_column("users", "is_active"):
            batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
        if not _has_column("users", "provider"):
            batch_op.add_column(sa.Column("provider", sa.String(20), nullable=True))
        if not _has_column("users", "provider_id"):
            batch_op.add_column(sa.Column("provider_id", sa.String(255), nullable=True))

    bind.execute(sa.text("""
        UPDATE users SET role = CASE
            WHEN platform_role = 'admin' THEN 'admin'
            ELSE 'viewer'
        END;
    """))
    bind.execute(sa.text("""
        UPDATE users SET is_active = (status = 'active');
    """))

    if _has_table("user_identities"):
        identities = bind.execute(sa.text("SELECT user_id, provider, provider_id FROM user_identities")).fetchall()
        seen_users = set()
        for u_id, p, pid in identities:
            if u_id not in seen_users:
                seen_users.add(u_id)
                bind.execute(sa.text("""
                    UPDATE users SET provider = :p, provider_id = :pid WHERE id = :u_id
                """), {"p": p, "pid": pid, "u_id": u_id})

    with op.batch_alter_table("users") as batch_op:
        for col in ["platform_role", "status", "password_hash", "password_updated_at", "approved_by", "approved_at", "failed_login_count", "locked_until"]:
            if _has_column("users", col):
                batch_op.drop_column(col)

    if _has_table("password_reset_tokens"):
        op.drop_table("password_reset_tokens")
    if _has_table("user_invites"):
        op.drop_table("user_invites")
    if _has_table("user_identities"):
        op.drop_table("user_identities")
