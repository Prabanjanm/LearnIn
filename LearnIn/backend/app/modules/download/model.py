from sqlalchemy import Column, Integer
from app.core.database import Base


class Download(Base):

    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
