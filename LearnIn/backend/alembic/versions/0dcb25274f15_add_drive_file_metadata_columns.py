"""add drive file metadata columns (file_id/mime_type/size/filename)

Converts Exam.icon and Blog.thumbnail from a bare string into structured
Drive metadata, adds the same to Department/Subject (new upload fields),
and adds mime_type/size/filename alongside the existing file_id columns
on Resource/Paper/Question so every upload records full metadata -
matching the admin CMS's automatic-upload flow.

Revision ID: 0dcb25274f15
Revises: 8cc3d2b2e8eb
Create Date: 2026-07-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0dcb25274f15'
down_revision: Union[str, Sequence[str], None] = '8cc3d2b2e8eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # exams: icon (bare string, never actually used) -> structured metadata
    op.drop_column('exams', 'icon')
    op.add_column('exams', sa.Column('icon_file_id', sa.String(length=255), nullable=True))
    op.add_column('exams', sa.Column('icon_mime_type', sa.String(length=100), nullable=True))
    op.add_column('exams', sa.Column('icon_file_size', sa.Integer(), nullable=True))
    op.add_column('exams', sa.Column('icon_filename', sa.String(length=255), nullable=True))

    # departments: brand new icon upload
    op.add_column('departments', sa.Column('icon_file_id', sa.String(length=255), nullable=True))
    op.add_column('departments', sa.Column('icon_mime_type', sa.String(length=100), nullable=True))
    op.add_column('departments', sa.Column('icon_file_size', sa.Integer(), nullable=True))
    op.add_column('departments', sa.Column('icon_filename', sa.String(length=255), nullable=True))

    # subjects: brand new icon upload
    op.add_column('subjects', sa.Column('icon_file_id', sa.String(length=255), nullable=True))
    op.add_column('subjects', sa.Column('icon_mime_type', sa.String(length=100), nullable=True))
    op.add_column('subjects', sa.Column('icon_file_size', sa.Integer(), nullable=True))
    op.add_column('subjects', sa.Column('icon_filename', sa.String(length=255), nullable=True))

    # blogs: thumbnail (bare string) -> structured metadata
    op.drop_column('blogs', 'thumbnail')
    op.add_column('blogs', sa.Column('thumbnail_file_id', sa.String(length=255), nullable=True))
    op.add_column('blogs', sa.Column('thumbnail_mime_type', sa.String(length=100), nullable=True))
    op.add_column('blogs', sa.Column('thumbnail_file_size', sa.Integer(), nullable=True))
    op.add_column('blogs', sa.Column('thumbnail_filename', sa.String(length=255), nullable=True))

    # resources: keep google_drive_file_id, add sibling metadata
    op.add_column('resources', sa.Column('google_drive_mime_type', sa.String(length=100), nullable=True))
    op.add_column('resources', sa.Column('google_drive_file_size', sa.Integer(), nullable=True))
    op.add_column('resources', sa.Column('google_drive_filename', sa.String(length=255), nullable=True))

    # papers: keep question_file_id/answer_file_id, add sibling metadata
    op.add_column('papers', sa.Column('question_file_mime_type', sa.String(length=100), nullable=True))
    op.add_column('papers', sa.Column('question_file_size', sa.Integer(), nullable=True))
    op.add_column('papers', sa.Column('question_filename', sa.String(length=255), nullable=True))
    op.add_column('papers', sa.Column('answer_file_mime_type', sa.String(length=100), nullable=True))
    op.add_column('papers', sa.Column('answer_file_size', sa.Integer(), nullable=True))
    op.add_column('papers', sa.Column('answer_filename', sa.String(length=255), nullable=True))

    # questions: keep image_file_id, add sibling metadata
    op.add_column('questions', sa.Column('image_mime_type', sa.String(length=100), nullable=True))
    op.add_column('questions', sa.Column('image_file_size', sa.Integer(), nullable=True))
    op.add_column('questions', sa.Column('image_filename', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('questions', 'image_filename')
    op.drop_column('questions', 'image_file_size')
    op.drop_column('questions', 'image_mime_type')

    op.drop_column('papers', 'answer_filename')
    op.drop_column('papers', 'answer_file_size')
    op.drop_column('papers', 'answer_file_mime_type')
    op.drop_column('papers', 'question_filename')
    op.drop_column('papers', 'question_file_size')
    op.drop_column('papers', 'question_file_mime_type')

    op.drop_column('resources', 'google_drive_filename')
    op.drop_column('resources', 'google_drive_file_size')
    op.drop_column('resources', 'google_drive_mime_type')

    op.drop_column('blogs', 'thumbnail_filename')
    op.drop_column('blogs', 'thumbnail_file_size')
    op.drop_column('blogs', 'thumbnail_mime_type')
    op.drop_column('blogs', 'thumbnail_file_id')
    op.add_column('blogs', sa.Column('thumbnail', sa.String(length=255), nullable=True))

    op.drop_column('subjects', 'icon_filename')
    op.drop_column('subjects', 'icon_file_size')
    op.drop_column('subjects', 'icon_mime_type')
    op.drop_column('subjects', 'icon_file_id')

    op.drop_column('departments', 'icon_filename')
    op.drop_column('departments', 'icon_file_size')
    op.drop_column('departments', 'icon_mime_type')
    op.drop_column('departments', 'icon_file_id')

    op.drop_column('exams', 'icon_filename')
    op.drop_column('exams', 'icon_file_size')
    op.drop_column('exams', 'icon_mime_type')
    op.drop_column('exams', 'icon_file_id')
    op.add_column('exams', sa.Column('icon', sa.String(length=255), nullable=True))
