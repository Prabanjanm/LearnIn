"""create temporary_uploads table

Reconciliation migration: the live database was already stamped at this
revision, but the migration file itself (and the model/service behind the
two-phase "upload now, commit on form save" flow it supports) had been
lost from the repo before this session started - discovered while adding
a new migration and finding `alembic revision --autogenerate` couldn't
locate this revision. This file recreates the migration from the actual
live schema (introspected column-for-column) purely to make history
contiguous again for anyone provisioning a fresh database; it is a no-op
against any database that already has the table.

The corresponding `temporary_uploads` model/service/router are still
missing and out of scope for this change - nothing in the current
codebase references this table. Flagged for a follow-up investigation.

Revision ID: 6fc87f09c3d4
Revises: a1b2c3d4e5f6
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fc87f09c3d4'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
    op.create_index(op.f('ix_temporary_uploads_committed'), 'temporary_uploads', ['committed'], unique=False)
    op.create_index(op.f('ix_temporary_uploads_drive_file_id'), 'temporary_uploads', ['drive_file_id'], unique=True)
    op.create_index(op.f('ix_temporary_uploads_expires_at'), 'temporary_uploads', ['expires_at'], unique=False)
    op.create_index(op.f('ix_temporary_uploads_id'), 'temporary_uploads', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_temporary_uploads_id'), table_name='temporary_uploads')
    op.drop_index(op.f('ix_temporary_uploads_expires_at'), table_name='temporary_uploads')
    op.drop_index(op.f('ix_temporary_uploads_drive_file_id'), table_name='temporary_uploads')
    op.drop_index(op.f('ix_temporary_uploads_committed'), table_name='temporary_uploads')
    op.drop_table('temporary_uploads')
