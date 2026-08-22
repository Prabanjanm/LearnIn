"""
Cross-entity Google Drive file bookkeeping.

Drive file ids live directly on the owning row (icon_file_id, question_file_id,
etc.) rather than in a dedicated files table. That's fine as long as two rules
are enforced everywhere a row that owns a file is updated or deleted:

1. A file is never deleted from Drive while some other row still references
   it (`is_file_referenced`) - two entities are never assumed to "own" a file
   exclusively just because one of them is being mutated.
2. A cascading delete (Exam -> Departments -> Subjects -> ... ) must not leak
   Drive files just because SQLAlchemy's cascade="all, delete-orphan" quietly
   removes the child DB rows - `collect_subtree_file_ids` walks the same
   relationships before the delete so the caller knows every file id that
   *might* need cleanup afterwards.

Callers always: collect ids -> commit the DB delete/update -> only then call
`cleanup_drive_file` per id, so a Drive failure during cleanup never blocks
or reverts the DB change, and a file is never removed from Drive before the
DB agrees it's no longer referenced.
"""
import logging

from sqlalchemy.orm import Session

from app.core.google_drive import get_drive_client

logger = logging.getLogger(__name__)

# Populated lazily (see _file_id_columns) to avoid import cycles between
# modules at startup - every (model, column) pair here can hold a Drive file id.
_FILE_ID_COLUMNS = None

# Direct parent -> children relationship attribute names that cascade-delete,
# used to walk a subtree before deleting the root so we know every file id
# that will disappear from the DB along with it.
_CASCADE_CHILDREN = None


def _file_id_columns():
    global _FILE_ID_COLUMNS
    if _FILE_ID_COLUMNS is None:
        from app.modules.blog.model import Blog
        from app.modules.department.model import Department
        from app.modules.exam.model import Exam
        from app.modules.option.model import Option
        from app.modules.paper.model import Paper
        from app.modules.question.model import Question
        from app.modules.resource.model import Resource
        from app.modules.subject.model import Subject

        _FILE_ID_COLUMNS = [
            (Exam, "icon_file_id"),
            (Department, "icon_file_id"),
            (Subject, "icon_file_id"),
            (Paper, "question_file_id"),
            (Paper, "answer_file_id"),
            (Question, "image_file_id"),
            (Question, "explanation_image_file_id"),
            (Option, "image_file_id"),
            (Resource, "google_drive_file_id"),
            (Blog, "thumbnail_file_id"),
        ]
    return _FILE_ID_COLUMNS


def _cascade_children():
    global _CASCADE_CHILDREN
    if _CASCADE_CHILDREN is None:
        from app.modules.department.model import Department
        from app.modules.exam.model import Exam
        from app.modules.paper.model import Paper
        from app.modules.question.model import Question
        from app.modules.subject.model import Subject

        _CASCADE_CHILDREN = {
            Exam: ["departments"],
            Department: ["subjects"],
            Subject: ["papers", "resources"],
            Paper: ["questions"],
            Question: ["options"],
        }
    return _CASCADE_CHILDREN


def is_file_referenced(db: Session, file_id: str | None) -> bool:
    """True if any row in any file-owning table still points at this file id."""
    if not file_id:
        return False

    for model, column in _file_id_columns():
        if db.query(model).filter(getattr(model, column) == file_id).first() is not None:
            return True

    return False


def collect_subtree_file_ids(obj) -> list[str]:
    """
    File ids owned by `obj` and every descendant reachable through a
    cascade="all, delete-orphan" relationship - i.e. everything that will be
    removed from the DB when `obj` is deleted.
    """
    file_ids = []

    for model, column in _file_id_columns():
        if isinstance(obj, model):
            value = getattr(obj, column, None)
            if value:
                file_ids.append(value)

    for child_attr in _cascade_children().get(type(obj), []):
        for child in getattr(obj, child_attr, []) or []:
            file_ids.extend(collect_subtree_file_ids(child))

    return file_ids


def cleanup_drive_file(db: Session, file_id: str | None) -> None:
    """
    Delete a Drive file only after the DB change that stopped referencing it
    has already committed, and only if no other row has since claimed it.
    Cleanup failures are logged, never raised - the DB is the source of truth
    and must not be rolled back because Drive cleanup failed.
    """
    if not file_id or is_file_referenced(db, file_id):
        return

    try:
        get_drive_client().delete_file(file_id)
    except Exception:
        logger.warning("Failed to clean up orphaned Drive file %s", file_id, exc_info=True)


def cleanup_drive_files(db: Session, file_ids: list[str]) -> None:
    for file_id in file_ids:
        cleanup_drive_file(db, file_id)
