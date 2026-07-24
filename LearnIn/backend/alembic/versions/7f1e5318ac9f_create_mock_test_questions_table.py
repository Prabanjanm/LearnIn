"""create mock_test_questions table

Revision ID: 7f1e5318ac9f
Revises: 5deabfebb607
Create Date: 2026-07-18 02:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f1e5318ac9f'
down_revision: Union[str, Sequence[str], None] = '5deabfebb607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mock_test_questions',
    sa.Column('mock_test_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('question_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['mock_test_id'], ['mock_tests.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mock_test_questions_id'), 'mock_test_questions', ['id'], unique=False)
    op.create_index(op.f('ix_mock_test_questions_mock_test_id'), 'mock_test_questions', ['mock_test_id'], unique=False)
    op.create_index(op.f('ix_mock_test_questions_question_id'), 'mock_test_questions', ['question_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mock_test_questions_question_id'), table_name='mock_test_questions')
    op.drop_index(op.f('ix_mock_test_questions_mock_test_id'), table_name='mock_test_questions')
    op.drop_index(op.f('ix_mock_test_questions_id'), table_name='mock_test_questions')
    op.drop_table('mock_test_questions')
