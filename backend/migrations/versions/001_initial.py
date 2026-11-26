"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-11-18 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.Column('source_file_key', sa.String(1024), nullable=True),
        sa.Column('source_file_size', sa.BigInteger(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('probe_data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='created'),
        sa.Column('error_message', sa.String(2048), nullable=True),
        sa.Column('analyzed_duration', sa.Float(), server_default='0.0'),
        sa.Column('total_chunks', sa.Integer(), server_default='0'),
        sa.Column('completed_chunks', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # Upload sessions
    op.create_table(
        'upload_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('upload_id', sa.String(512), nullable=False),
        sa.Column('file_key', sa.String(1024), nullable=False),
        sa.Column('file_name', sa.String(512), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('chunk_size', sa.Integer(), nullable=False),
        sa.Column('total_parts', sa.Integer(), nullable=False),
        sa.Column('completed_parts', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='in_progress'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # Analysis chunks
    op.create_table(
        'analysis_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.String(2048), nullable=True),
        sa.Column('transcript', sa.JSON(), nullable=True),
        sa.Column('scene_changes', sa.JSON(), nullable=True),
        sa.Column('audio_peaks', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_analysis_chunks_project_id', 'analysis_chunks', ['project_id'])

    # Reels
    op.create_table(
        'reels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('reason', sa.String(2048), nullable=False),
        sa.Column('category', sa.String(50), nullable=False, server_default='highlight'),
        sa.Column('source_start', sa.Float(), nullable=False),
        sa.Column('source_end', sa.Float(), nullable=False),
        sa.Column('clip_duration', sa.Float(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('score_hook', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('score_payoff', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('score_clarity', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('score_entertainment', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('is_borderline', sa.Boolean(), server_default='false'),
        sa.Column('framing_mode', sa.String(50), nullable=False, server_default='crop'),
        sa.Column('pan_x_offset', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('top_caption', sa.String(512), nullable=False),
        sa.Column('subtitles_json', sa.JSON(), nullable=True),
        sa.Column('video_key', sa.String(1024), nullable=True),
        sa.Column('thumbnail_key', sa.String(1024), nullable=True),
        sa.Column('render_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('render_error', sa.String(2048), nullable=True),
        sa.Column('render_progress', sa.Float(), server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_reels_project_id', 'reels', ['project_id'])

    # Bulk exports
    op.create_table(
        'bulk_exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zip_key', sa.String(1024), nullable=True),
        sa.Column('reel_count', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.String(2048), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('bulk_exports')
    op.drop_table('reels')
    op.drop_table('analysis_chunks')
    op.drop_table('upload_sessions')
    op.drop_table('projects')
    op.drop_table('users')
