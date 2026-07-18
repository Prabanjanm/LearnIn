from sqlalchemy import Column, Integer
from app.core.database import Base


class Note(Base):

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
