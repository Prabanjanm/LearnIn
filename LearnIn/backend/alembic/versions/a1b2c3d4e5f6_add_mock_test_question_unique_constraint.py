"""add unique constraint on mock_test_questions(mock_test_id, question_id)

Prevents the same question from being linked into a mock test twice at the
DB level - previously only the service layer's exists_link() check guarded
against this, so a race or a direct insert could still duplicate a link.

Revision ID: a1b2c3d4e5f6
Revises: 3f7a1c9e2b4d
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3f7a1c9e2b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        'uq_mock_test_question',
        'mock_test_questions',
        ['mock_test_id', 'question_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_mock_test_question', 'mock_test_questions', type_='unique')
