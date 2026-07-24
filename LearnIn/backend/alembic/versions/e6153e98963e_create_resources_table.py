"""create resources table

Revision ID: e6153e98963e
Revises: cd50c6bffec4
Create Date: 2026-07-18 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6153e98963e'
down_revision: Union[str, Sequence[str], None] = 'cd50c6bffec4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('resources',
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column(
        'resource_type',
        sa.Enum(
            'NOTES', 'PYQ', 'FORMULA_SHEET', 'REVISION_NOTES',
            'IMPORTANT_QUESTIONS', 'CHEAT_SHEET',
            name='resourcetype'
        ),
        nullable=False
    ),
    sa.Column('google_drive_file_id', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column(
        'status',
        sa.Enum('DRAFT', 'PUBLISHED', 'ARCHIVED', name='statusenum', create_type=False),
        nullable=False
    ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resources_id'), 'resources', ['id'], unique=False)
    op.create_index(op.f('ix_resources_subject_id'), 'resources', ['subject_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_resources_subject_id'), table_name='resources')
    op.drop_index(op.f('ix_resources_id'), table_name='resources')
    op.drop_table('resources')

    sa.Enum(name='resourcetype').drop(op.get_bind(), checkfirst=True)
