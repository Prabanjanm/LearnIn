"""create blogs table

Revision ID: 28cb5e56c06a
Revises: 7f1e5318ac9f
Create Date: 2026-07-18 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28cb5e56c06a'
down_revision: Union[str, Sequence[str], None] = '7f1e5318ac9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('blogs',
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('thumbnail', sa.String(length=255), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('tags', sa.String(length=500), nullable=True),
    sa.Column('published_date', sa.Date(), nullable=True),
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
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug', name='uq_blogs_slug')
    )
    op.create_index(op.f('ix_blogs_category'), 'blogs', ['category'], unique=False)
    op.create_index(op.f('ix_blogs_id'), 'blogs', ['id'], unique=False)
    op.create_index(op.f('ix_blogs_slug'), 'blogs', ['slug'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_blogs_slug'), table_name='blogs')
    op.drop_index(op.f('ix_blogs_id'), table_name='blogs')
    op.drop_index(op.f('ix_blogs_category'), table_name='blogs')
    op.drop_table('blogs')
