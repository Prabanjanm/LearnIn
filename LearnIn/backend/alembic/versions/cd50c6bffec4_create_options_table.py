"""create options table

Revision ID: cd50c6bffec4
Revises: 7f6192c7aa9f
Create Date: 2026-07-18 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd50c6bffec4'
down_revision: Union[str, Sequence[str], None] = '7f6192c7aa9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('options',
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=2), nullable=False),
    sa.Column('option_text', sa.Text(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('question_id', 'label', name='uq_option_label')
    )
    op.create_index(op.f('ix_options_id'), 'options', ['id'], unique=False)
    op.create_index(op.f('ix_options_question_id'), 'options', ['question_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_options_question_id'), table_name='options')
    op.drop_index(op.f('ix_options_id'), table_name='options')
    op.drop_table('options')
