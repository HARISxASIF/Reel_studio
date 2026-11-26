"""Add user_credentials table

Revision ID: 002_user_credentials
Revises: 001_initial
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_user_credentials'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User credentials table for multi-tenant Google AI Studio and YouTube OAuth credentials
    op.create_table(
        'user_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gemini_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('gemini_status', sa.String(50), nullable=False, server_default='not_configured'),
        sa.Column('gemini_last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('gemini_model', sa.String(100), nullable=False, server_default='gemini-3.5-flash-lite'),
        sa.Column('youtube_client_id', sa.String(255), nullable=True),
        sa.Column('youtube_client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('youtube_status', sa.String(50), nullable=False, server_default='not_configured'),
        sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('storage_limit_mb', sa.Integer(), nullable=False, server_default='10240'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_user_credentials_user_id', 'user_credentials', ['user_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_user_credentials_user_id', table_name='user_credentials')
    op.drop_table('user_credentials')
