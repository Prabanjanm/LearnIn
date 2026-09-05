from sqlalchemy.exc import IntegrityError

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException


class BaseService:

    def __init__(self, repository):
        self.repository = repository

    def get_all(self, db):
        return self.repository.get_all(db)

    def get_all_paginated(self, db, page: int = 1, page_size: int = 20):
        return self.repository.get_all_paginated(db, page, page_size)

    def get_by_id(self, db, obj_id):
        return self.repository.get_by_id(db, obj_id)

    def get_or_404(self, db, obj_id, message: str = "Not found"):
        obj = self.repository.get_by_id(db, obj_id)
        if obj is None:
            raise NotFoundException(message)
        return obj

    def create(self, db, obj):
        """
        A raw unique-constraint violation (duplicate code/slug/year, etc.)
        would otherwise surface as an unhandled sqlalchemy.exc.IntegrityError
        - a 500 with an internal DB error, or a raw traceback in DEBUG mode -
        instead of a clean, expected "this already exists" response.
        Converting it here means every caller that creates through the
        normal service/repository path gets sane 409 behavior for free,
        without each entity's create_X method repeating the same try/except.
        """
        try:
            return self.repository.create(db, obj)
        except IntegrityError:
            db.rollback()
            raise AlreadyExistsException("A record with conflicting unique data already exists")

    def update(self, db, obj):
        return self.repository.update(db, obj)

    def delete(self, db, obj):
        return self.repository.delete(db, obj)

    def count(self, db):
        return self.repository.count(db)