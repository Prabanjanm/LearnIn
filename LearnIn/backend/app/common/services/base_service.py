class BaseService:

    def __init__(self, repository):
        self.repository = repository

    def get_all(self, db):
        return self.repository.get_all(db)

    def get_by_id(self, db, obj_id):
        return self.repository.get_by_id(db, obj_id)

    def create(self, db, obj):
        return self.repository.create(db, obj)

    def update(self, db, obj):
        return self.repository.update(db, obj)

    def delete(self, db, obj):
        return self.repository.delete(db, obj)

    def count(self, db):
        return self.repository.count(db)