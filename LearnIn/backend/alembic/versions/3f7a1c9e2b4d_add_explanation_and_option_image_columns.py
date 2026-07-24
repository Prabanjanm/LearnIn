"""add explanation image (questions) and option image columns

Adds structured Drive metadata (file_id/mime_type/size/filename) for a
question's explanation image and for each option's image, matching the
same automatic-upload pattern already used for the question's own image.

Revision ID: 3f7a1c9e2b4d
Revises: 0dcb25274f15
Create Date: 2026-07-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f7a1c9e2b4d'
down_revision: Union[str, Sequence[str], None] = '0dcb25274f15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('questions', sa.Column('explanation_image_file_id', sa.String(length=255), nullable=True))
    op.add_column('questions', sa.Column('explanation_image_mime_type', sa.String(length=100), nullable=True))
    op.add_column('questions', sa.Column('explanation_image_file_size', sa.Integer(), nullable=True))
    op.add_column('questions', sa.Column('explanation_image_filename', sa.String(length=255), nullable=True))

    op.add_column('options', sa.Column('image_file_id', sa.String(length=255), nullable=True))
    op.add_column('options', sa.Column('image_mime_type', sa.String(length=100), nullable=True))
    op.add_column('options', sa.Column('image_file_size', sa.Integer(), nullable=True))
    op.add_column('options', sa.Column('image_filename', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('options', 'image_filename')
    op.drop_column('options', 'image_file_size')
    op.drop_column('options', 'image_mime_type')
    op.drop_column('options', 'image_file_id')

    op.drop_column('questions', 'explanation_image_filename')
    op.drop_column('questions', 'explanation_image_file_size')
    op.drop_column('questions', 'explanation_image_mime_type')
    op.drop_column('questions', 'explanation_image_file_id')
