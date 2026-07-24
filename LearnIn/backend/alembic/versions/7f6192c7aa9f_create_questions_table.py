"""create questions table

Revision ID: 7f6192c7aa9f
Revises: 029fef04692c
Create Date: 2026-07-18 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f6192c7aa9f'
down_revision: Union[str, Sequence[str], None] = '029fef04692c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('questions',
    sa.Column('paper_id', sa.Integer(), nullable=False),
    sa.Column('question_number', sa.Integer(), nullable=False),
    sa.Column('question_type', sa.Enum('MCQ', 'MSQ', 'NAT', name='questiontype'), nullable=False),
    sa.Column('question_text', sa.Text(), nullable=False),
    sa.Column('image_file_id', sa.String(length=255), nullable=True),
    sa.Column('correct_answer', sa.String(length=50), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('marks', sa.Float(), nullable=False),
    sa.Column('negative_marks', sa.Float(), nullable=False),
    sa.Column('difficulty', sa.Enum('EASY', 'MEDIUM', 'HARD', name='difficultyenum'), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column(
        'status',
        sa.Enum('DRAFT', 'PUBLISHED', 'ARCHIVED', name='statusenum', create_type=False),
        nullable=False
    ),
    sa.ForeignKeyConstraint(['paper_id'], ['papers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('paper_id', 'question_number', name='uq_question_number')
    )
    op.create_index(op.f('ix_questions_id'), 'questions', ['id'], unique=False)
    op.create_index(op.f('ix_questions_paper_id'), 'questions', ['paper_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_questions_paper_id'), table_name='questions')
    op.drop_index(op.f('ix_questions_id'), table_name='questions')
    op.drop_table('questions')

    sa.Enum(name='questiontype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='difficultyenum').drop(op.get_bind(), checkfirst=True)
