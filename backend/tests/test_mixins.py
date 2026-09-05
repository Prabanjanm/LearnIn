from app.core.enums import StatusEnum
from app.modules.exam.model import Exam


def test_status_mixin_maps_status_column():
    column = Exam.__table__.columns["status"]

    assert column is not None
    assert column.nullable is False
    assert column.default.arg == StatusEnum.DRAFT
