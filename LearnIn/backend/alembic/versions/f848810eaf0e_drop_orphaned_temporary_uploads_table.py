"""drop orphaned temporary_uploads table

`temporary_uploads` (recreated as a reconciliation stub in 6fc87f09c3d4,
since its original migration file had been lost) turns out to be dead:
nothing in the codebase references it. The actual, working upload flow
(app/common/utils/file_tracking.py, /admin/upload in
app/modules/admin/pages.py) uploads straight to Google Drive and stores
the file id directly on the owning row (icon_file_id, question_file_id,
etc.) - it was never staged through a temporary/expiring table. This
table was an earlier design that was superseded; there is no feature to
rebuild here, just cleanup.

Revision ID: f848810eaf0e
Revises: 90a250bc41a6
Create Date: 2026-09-05 13:01:08.351292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f848810eaf0e'
down_revision: Union[str, Sequence[str], None] = '90a250bc41a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('ix_temporary_uploads_committed', table_name='temporary_uploads')
    op.drop_index('ix_temporary_uploads_drive_file_id', table_name='temporary_uploads')
    op.drop_index('ix_temporary_uploads_expires_at', table_name='temporary_uploads')
    op.drop_index('ix_temporary_uploads_id', table_name='temporary_uploads')
    op.drop_table('temporary_uploads')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('temporary_uploads',
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
    op.create_index('ix_temporary_uploads_committed', 'temporary_uploads', ['committed'], unique=False)
    op.create_index('ix_temporary_uploads_drive_file_id', 'temporary_uploads', ['drive_file_id'], unique=True)
    op.create_index('ix_temporary_uploads_expires_at', 'temporary_uploads', ['expires_at'], unique=False)
    op.create_index('ix_temporary_uploads_id', 'temporary_uploads', ['id'], unique=False)
