from app.common.exceptions.exceptions import NotFoundException


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
        return self.repository.create(db, obj)

    def update(self, db, obj):
        return self.repository.update(db, obj)

    def delete(self, db, obj):
        return self.repository.delete(db, obj)

    def count(self, db):
        return self.repository.count(db)