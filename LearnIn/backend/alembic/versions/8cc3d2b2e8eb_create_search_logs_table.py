"""create search_logs table

Revision ID: 8cc3d2b2e8eb
Revises: 28cb5e56c06a
Create Date: 2026-07-18 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8cc3d2b2e8eb'
down_revision: Union[str, Sequence[str], None] = '28cb5e56c06a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('search_logs',
    sa.Column('query', sa.String(length=255), nullable=False),
    sa.Column('results_count', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_logs_id'), 'search_logs', ['id'], unique=False)
    op.create_index(op.f('ix_search_logs_query'), 'search_logs', ['query'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_search_logs_query'), table_name='search_logs')
    op.drop_index(op.f('ix_search_logs_id'), table_name='search_logs')
    op.drop_table('search_logs')
