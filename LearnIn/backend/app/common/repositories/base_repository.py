class BaseRepository:

    def __init__(self, model):
        self.model = model

    def get_all(self, db):
        return db.query(self.model).all()

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