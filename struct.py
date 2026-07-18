# ============================================================
# PART 1C.2
# Generate Boilerplate for Every Module
# ============================================================

from pathlib import Path

PROJECT_NAME = "LearnIn"

root = Path(PROJECT_NAME)


from pathlib import Path

MODULES = [

    "exam",
    "department",
    "subject",
    "paper",
    "question",
    "mock_test",
    "note",
    "download",
    "blog",

]

# ============================================================
# model.py
# ============================================================

MODEL = '''from sqlalchemy import Column, Integer
from app.core.database import Base


class {class_name}(Base):

    __tablename__ = "{table_name}"

    id = Column(Integer, primary_key=True, index=True)
'''

# ============================================================
# schema.py
# ============================================================

SCHEMA = '''from pydantic import BaseModel


class {class_name}Base(BaseModel):
    pass


class {class_name}Create({class_name}Base):
    pass


class {class_name}Update({class_name}Base):
    pass


class {class_name}Response({class_name}Base):

    id: int

    class Config:
        from_attributes = True
'''

# ============================================================
# repository.py
# ============================================================

REPOSITORY = '''from sqlalchemy.orm import Session

from .model import {class_name}


class {class_name}Repository:

    @staticmethod
    def get_all(db: Session):

        return db.query({class_name}).all()


    @staticmethod
    def get_by_id(db: Session, item_id: int):

        return db.query({class_name}).filter(
            {class_name}.id == item_id
        ).first()


    @staticmethod
    def create(db: Session, obj):

        db.add(obj)

        db.commit()

        db.refresh(obj)

        return obj


    @staticmethod
    def delete(db: Session, obj):

        db.delete(obj)

        db.commit()
'''

# ============================================================
# service.py
# ============================================================

SERVICE = '''from sqlalchemy.orm import Session

from .repository import {class_name}Repository


class {class_name}Service:

    @staticmethod
    def list(db: Session):

        return {class_name}Repository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return {class_name}Repository.get_by_id(
            db,
            item_id
        )
'''

# ============================================================
# router.py
# ============================================================

ROUTER = '''from fastapi import APIRouter

router = APIRouter(

    prefix="/{table_name}",

    tags=["{class_name}"]

)


@router.get("/")

def list_items():

    return {{

        "message":"{class_name} List"

    }}


@router.get("/{{item_id}}")

def details(item_id:int):

    return {{

        "message":"{class_name} Details",

        "id":item_id

    }}
'''

# ============================================================
# Write Files
# ============================================================

for module in MODULES:

    class_name = "".join(
        word.capitalize()
        for word in module.split("_")
    )

    table_name = module + "s"

    module_path = Path(PROJECT_NAME) / "backend" / "app" / "modules" / module

    (module_path / "model.py").write_text(
        MODEL.format(
            class_name=class_name,
            table_name=table_name
        ),
        encoding="utf-8"
    )

    (module_path / "schema.py").write_text(
        SCHEMA.format(
            class_name=class_name
        ),
        encoding="utf-8"
    )

    (module_path / "repository.py").write_text(
        REPOSITORY.format(
            class_name=class_name
        ),
        encoding="utf-8"
    )

    (module_path / "service.py").write_text(
        SERVICE.format(
            class_name=class_name
        ),
        encoding="utf-8"
    )

    (module_path / "router.py").write_text(
        ROUTER.format(
            class_name=class_name,
            table_name=table_name
        ),
        encoding="utf-8"
    )

print("✅ Module boilerplate generated.")
# =====================================================
# Create Files
# =====================================================
from pathlib import Path

PROJECT_NAME = "LearnIn"

root = Path(PROJECT_NAME)

