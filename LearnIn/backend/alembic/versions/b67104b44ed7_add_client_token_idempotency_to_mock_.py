"""add client_token idempotency to mock test attempts

Revision ID: b67104b44ed7
Revises: f848810eaf0e
Create Date: 2026-09-05 13:16:40.629475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b67104b44ed7'
down_revision: Union[str, Sequence[str], None] = 'f848810eaf0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('mock_test_attempts', sa.Column('client_token', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_mock_test_attempts_client_token'), 'mock_test_attempts', ['client_token'], unique=False)
    op.create_unique_constraint('uq_mock_test_attempt_client_token', 'mock_test_attempts', ['mock_test_id', 'client_token'])
    #
    # Note: autogenerate also proposed renaming a few unrelated constraints
    # (admins/exams/mock_test_questions) - pre-existing drift between the
    # live database and this repo's models/migrations (see 9e7c553db4a8),
    # unrelated to this change, left out here too.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_mock_test_attempt_client_token', 'mock_test_attempts', type_='unique')
    op.drop_index(op.f('ix_mock_test_attempts_client_token'), table_name='mock_test_attempts')
    op.drop_column('mock_test_attempts', 'client_token')
