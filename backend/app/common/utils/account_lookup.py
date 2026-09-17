"""
Cross-role email uniqueness check.

Students, institution users, and admins each live in their own table with
their own repository, so a per-table uniqueness check only stops a duplicate
signup *within* that one role - the same email could otherwise sign up as a
student and, separately, as an institution user. Login/signup flows should
call is_email_registered instead of querying a single repository so one
email can only ever belong to one account across the whole platform.
"""
from sqlalchemy.orm import Session


def is_email_registered(db: Session, email: str) -> bool:
    from app.modules.admin.model import Admin
    from app.modules.institution.model import InstitutionUser
    from app.modules.student.model import Student

    return (
        db.query(Student.id).filter(Student.email == email).first() is not None
        or db.query(InstitutionUser.id).filter(InstitutionUser.email == email).first() is not None
        or db.query(Admin.id).filter(Admin.email == email).first() is not None
    )
