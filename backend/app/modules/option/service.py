from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file

from .model import Option
from .repository import OptionRepository
from .schema import OptionCreate, OptionUpdate


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

    def update_option(
        self,
        db: Session,
        option: Option,
        data: OptionUpdate
    ) -> Option:

        updates = data.model_dump(exclude_unset=True)

        if "label" in updates and updates["label"] is not None and updates["label"] != option.label:
            if self.repository.exists_by_label(db, option.question_id, updates["label"]):
                raise AlreadyExistsException(
                    "An option with this label already exists for this question"
                )

        old_image_file_id = option.image_file_id
        replacing_image = "image_file_id" in updates and updates["image_file_id"] != old_image_file_id

        for field, value in updates.items():
            setattr(option, field, value)

        updated = self.repository.update(db, option)

        if replacing_image:
            cleanup_drive_file(db, old_image_file_id)

        return updated

    def delete_option(
        self,
        db: Session,
        option: Option
    ) -> None:
        file_id = option.image_file_id
        self.repository.delete(db, option)
        cleanup_drive_file(db, file_id)


option_service = OptionService()
