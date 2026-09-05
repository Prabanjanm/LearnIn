"""create mock test sessions table for server-authoritative timer

Revision ID: 2ee10bc6285d
Revises: b67104b44ed7
Create Date: 2026-09-05 13:48:09.979632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ee10bc6285d'
down_revision: Union[str, Sequence[str], None] = 'b67104b44ed7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mock_test_sessions',
    sa.Column('mock_test_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=True),
    sa.Column('client_token', sa.String(length=64), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['mock_test_id'], ['mock_tests.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('mock_test_id', 'client_token', name='uq_mock_test_session_client_token')
    )
    op.create_index(op.f('ix_mock_test_sessions_client_token'), 'mock_test_sessions', ['client_token'], unique=False)
    op.create_index(op.f('ix_mock_test_sessions_id'), 'mock_test_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_mock_test_sessions_mock_test_id'), 'mock_test_sessions', ['mock_test_id'], unique=False)
    op.create_index(op.f('ix_mock_test_sessions_student_id'), 'mock_test_sessions', ['student_id'], unique=False)
    #
    # Note: autogenerate also proposed renaming a few unrelated constraints
    # (admins/exams/mock_test_questions) - pre-existing drift between the
    # live database and this repo's models/migrations (see 9e7c553db4a8),
    # unrelated to this change, left out here too.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mock_test_sessions_student_id'), table_name='mock_test_sessions')
    op.drop_index(op.f('ix_mock_test_sessions_mock_test_id'), table_name='mock_test_sessions')
    op.drop_index(op.f('ix_mock_test_sessions_id'), table_name='mock_test_sessions')
    op.drop_index(op.f('ix_mock_test_sessions_client_token'), table_name='mock_test_sessions')
    op.drop_table('mock_test_sessions')
