"""create mock test session answers table

Revision ID: daf52968b5f9
Revises: 2ee10bc6285d
Create Date: 2026-09-05 14:23:42.097543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'daf52968b5f9'
down_revision: Union[str, Sequence[str], None] = '2ee10bc6285d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mock_test_session_answers',
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('selected_answer', sa.String(length=255), nullable=True),
    sa.Column('is_marked', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['mock_test_sessions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id', 'question_id', name='uq_mock_test_session_answer_question')
    )
    op.create_index(op.f('ix_mock_test_session_answers_id'), 'mock_test_session_answers', ['id'], unique=False)
    op.create_index(op.f('ix_mock_test_session_answers_question_id'), 'mock_test_session_answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_mock_test_session_answers_session_id'), 'mock_test_session_answers', ['session_id'], unique=False)
    #
    # Note: autogenerate also proposed renaming a few unrelated constraints
    # (admins/exams/mock_test_questions) - pre-existing drift between the
    # live database and this repo's models/migrations (see 9e7c553db4a8),
    # unrelated to this change, left out here too.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mock_test_session_answers_session_id'), table_name='mock_test_session_answers')
    op.drop_index(op.f('ix_mock_test_session_answers_question_id'), table_name='mock_test_session_answers')
    op.drop_index(op.f('ix_mock_test_session_answers_id'), table_name='mock_test_session_answers')
    op.drop_table('mock_test_session_answers')
