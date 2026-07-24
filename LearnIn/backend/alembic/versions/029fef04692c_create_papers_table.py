"""create papers table

Revision ID: 029fef04692c
Revises: 2162219dbcdb
Create Date: 2026-07-18 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '029fef04692c'
down_revision: Union[str, Sequence[str], None] = '2162219dbcdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('papers',
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('question_file_id', sa.String(length=255), nullable=False),
    sa.Column('answer_file_id', sa.String(length=255), nullable=True),
    sa.Column('duration', sa.Integer(), nullable=True),
    sa.Column('total_questions', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column(
        'status',
        sa.Enum('DRAFT', 'PUBLISHED', 'ARCHIVED', name='statusenum', create_type=False),
        nullable=False
    ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('subject_id', 'year', name='uq_subject_year')
    )
    op.create_index(op.f('ix_papers_id'), 'papers', ['id'], unique=False)
    op.create_index(op.f('ix_papers_subject_id'), 'papers', ['subject_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_papers_subject_id'), table_name='papers')
    op.drop_index(op.f('ix_papers_id'), table_name='papers')
    op.drop_table('papers')
