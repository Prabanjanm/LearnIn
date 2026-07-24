"""create mock_tests table

Revision ID: 5deabfebb607
Revises: e6153e98963e
Create Date: 2026-07-18 02:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5deabfebb607'
down_revision: Union[str, Sequence[str], None] = 'e6153e98963e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mock_tests',
    sa.Column('paper_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('duration', sa.Integer(), nullable=False),
    sa.Column('total_marks', sa.Integer(), nullable=False),
    sa.Column('total_questions', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column(
        'status',
        sa.Enum('DRAFT', 'PUBLISHED', 'ARCHIVED', name='statusenum', create_type=False),
        nullable=False
    ),
    sa.ForeignKeyConstraint(['paper_id'], ['papers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mock_tests_id'), 'mock_tests', ['id'], unique=False)
    op.create_index(op.f('ix_mock_tests_paper_id'), 'mock_tests', ['paper_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mock_tests_paper_id'), table_name='mock_tests')
    op.drop_index(op.f('ix_mock_tests_id'), table_name='mock_tests')
    op.drop_table('mock_tests')
