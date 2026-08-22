"""create temporary uploads table

Revision ID: 6fc87f09c3d4
Revises: 3f7a1c9e2b4d
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fc87f09c3d4'
down_revision: Union[str, Sequence[str], None] = '3f7a1c9e2b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'temporary_uploads',
        sa.Column('drive_file_id', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('upload_type', sa.String(length=20), nullable=False),
        sa.Column('committed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_temporary_uploads_drive_file_id'), 'temporary_uploads', ['drive_file_id'], unique=True)
    op.create_index(op.f('ix_temporary_uploads_committed'), 'temporary_uploads', ['committed'], unique=False)
    op.create_index(op.f('ix_temporary_uploads_expires_at'), 'temporary_uploads', ['expires_at'], unique=False)
    op.create_index(op.f('ix_temporary_uploads_id'), 'temporary_uploads', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_temporary_uploads_expires_at'), table_name='temporary_uploads')
    op.drop_index(op.f('ix_temporary_uploads_committed'), table_name='temporary_uploads')
    op.drop_index(op.f('ix_temporary_uploads_drive_file_id'), table_name='temporary_uploads')
    op.drop_index(op.f('ix_temporary_uploads_id'), table_name='temporary_uploads')
    op.drop_table('temporary_uploads')
