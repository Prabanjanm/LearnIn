"""create subjects table

Revision ID: 2162219dbcdb
Revises: c150cfc7109f
Create Date: 2026-07-18 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2162219dbcdb'
down_revision: Union[str, Sequence[str], None] = 'c150cfc7109f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('subjects',
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column(
        'status',
        sa.Enum('DRAFT', 'PUBLISHED', 'ARCHIVED', name='statusenum', create_type=False),
        nullable=False
    ),
    sa.Column('meta_title', sa.String(length=255), nullable=True),
    sa.Column('meta_description', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('department_id', 'slug', name='uq_department_subject')
    )
    op.create_index(op.f('ix_subjects_department_id'), 'subjects', ['department_id'], unique=False)
    op.create_index(op.f('ix_subjects_id'), 'subjects', ['id'], unique=False)
    op.create_index(op.f('ix_subjects_slug'), 'subjects', ['slug'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_subjects_slug'), table_name='subjects')
    op.drop_index(op.f('ix_subjects_id'), table_name='subjects')
    op.drop_index(op.f('ix_subjects_department_id'), table_name='subjects')
    op.drop_table('subjects')
