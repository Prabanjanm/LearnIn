"""create students table and attribute mock test attempts

Revision ID: 90a250bc41a6
Revises: 9e7c553db4a8
Create Date: 2026-09-05 12:48:51.297812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '90a250bc41a6'
down_revision: Union[str, Sequence[str], None] = '9e7c553db4a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('students',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_students_email'), 'students', ['email'], unique=True)
    op.create_index(op.f('ix_students_id'), 'students', ['id'], unique=False)
    op.add_column('mock_test_attempts', sa.Column('student_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_mock_test_attempts_student_id'), 'mock_test_attempts', ['student_id'], unique=False)
    op.create_foreign_key(
        'fk_mock_test_attempts_student_id', 'mock_test_attempts', 'students', ['student_id'], ['id']
    )
    #
    # Note: autogenerate also proposed dropping `temporary_uploads` and
    # renaming a few unrelated constraints (admins/exams/mock_test_questions).
    # Those reflect pre-existing drift between the live database and this
    # repo's models/migrations (see 9e7c553db4a8) - left out here too.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_mock_test_attempts_student_id', 'mock_test_attempts', type_='foreignkey')
    op.drop_index(op.f('ix_mock_test_attempts_student_id'), table_name='mock_test_attempts')
    op.drop_column('mock_test_attempts', 'student_id')
    op.drop_index(op.f('ix_students_id'), table_name='students')
    op.drop_index(op.f('ix_students_email'), table_name='students')
    op.drop_table('students')
