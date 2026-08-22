class BaseRepository:

    def __init__(self, model):
        self.model = model

    def get_all(self, db):
        return db.query(self.model).all()

    def get_all_paginated(self, db, page: int = 1, page_size: int = 20):
        query = db.query(self.model).order_by(self.model.id.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    def get_by_id(self, db, obj_id):
        return (
            db.query(self.model)
            .filter(self.model.id == obj_id)
            .first()
        )

    def create(self, db, obj):
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db, obj):
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db, obj):
        db.delete(obj)
        db.commit()

    def exists(self, db, **filters):
        return db.query(self.model).filter_by(**filters).first() is not None

    def count(self, db):
        return db.query(self.model).count()