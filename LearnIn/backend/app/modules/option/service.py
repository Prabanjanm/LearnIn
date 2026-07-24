from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException
from app.common.services.base_service import BaseService

from .model import Option
from .repository import OptionRepository
from .schema import OptionCreate


class OptionService(BaseService):

    def __init__(self):
        super().__init__(OptionRepository())

    def create_option(
        self,
        db: Session,
        data: OptionCreate
    ) -> Option:

        if self.repository.exists_by_label(db, data.question_id, data.label):
            raise AlreadyExistsException(
                "An option with this label already exists for this question"
            )

        option = Option(
            question_id=data.question_id,
            label=data.label,
            option_text=data.option_text,
            image_file_id=data.image_file_id,
            image_mime_type=data.image_mime_type,
            image_file_size=data.image_file_size,
            image_filename=data.image_filename,
        )

        return self.repository.create(db, option)

    def get_by_question(
        self,
        db: Session,
        question_id: int
    ):
        return self.repository.get_by_question(db, question_id)


option_service = OptionService()
