from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException
from app.common.services.base_service import BaseService

from .model import MockTestQuestion
from .repository import MockTestQuestionRepository
from .schema import MockTestQuestionCreate, MockTestQuestionReorder


class MockTestQuestionService(BaseService):

    def __init__(self):
        super().__init__(MockTestQuestionRepository())

    def get_by_mock_test(
        self,
        db: Session,
        mock_test_id: int
    ):
        return self.repository.get_by_mock_test(db, mock_test_id)

    def add_question(
        self,
        db: Session,
        data: MockTestQuestionCreate
    ) -> MockTestQuestion:

        if self.repository.exists_link(db, data.mock_test_id, data.question_id):
            raise AlreadyExistsException("This question is already in the mock test")

        order = data.question_order or (self.repository.get_max_order(db, data.mock_test_id) + 1)

        link = MockTestQuestion(
            mock_test_id=data.mock_test_id,
            question_id=data.question_id,
            question_order=order,
        )

        created = self.repository.create(db, link)
        self._resync_total_questions(db, data.mock_test_id)
        return created

    def remove_question(
        self,
        db: Session,
        link: MockTestQuestion
    ) -> None:
        mock_test_id = link.mock_test_id
        self.repository.delete(db, link)
        self._resync_total_questions(db, mock_test_id)

    def reorder(
        self,
        db: Session,
        mock_test_id: int,
        data: MockTestQuestionReorder
    ) -> list[MockTestQuestion]:
        """
        Reassigns question_order deterministically from the given ordering
        of question_ids. Any link for this mock test not listed keeps its
        relative order, appended after the ones explicitly reordered.
        """
        links = self.repository.get_by_mock_test(db, mock_test_id)
        by_question_id = {link.question_id: link for link in links}

        order = 1
        seen = set()
        for question_id in data.question_ids:
            link = by_question_id.get(question_id)
            if link is None:
                continue
            link.question_order = order
            order += 1
            seen.add(question_id)

        for link in links:
            if link.question_id not in seen:
                link.question_order = order
                order += 1

        db.commit()
        return self.repository.get_by_mock_test(db, mock_test_id)

    def set_questions(
        self,
        db: Session,
        mock_test_id: int,
        question_ids: list[int]
    ) -> list[MockTestQuestion]:
        """
        Full replace of a mock test's question set from an ordered list of
        question ids - used by the edit form, where the admin retypes the
        whole list rather than adding/removing one at a time. Unlike
        reorder(), this actually drops links whose question id is no longer
        present and creates links for ids that are new.
        """
        existing_links = self.repository.get_by_mock_test(db, mock_test_id)
        existing_by_question_id = {link.question_id: link for link in existing_links}

        # De-dupe while preserving the admin's given order.
        seen_ids: set[int] = set()
        ordered_ids = [qid for qid in question_ids if not (qid in seen_ids or seen_ids.add(qid))]

        for link in existing_links:
            if link.question_id not in ordered_ids:
                db.delete(link)

        for order, question_id in enumerate(ordered_ids, start=1):
            link = existing_by_question_id.get(question_id)
            if link is not None:
                link.question_order = order
            else:
                db.add(MockTestQuestion(
                    mock_test_id=mock_test_id,
                    question_id=question_id,
                    question_order=order,
                ))

        db.commit()
        self._resync_total_questions(db, mock_test_id)
        return self.repository.get_by_mock_test(db, mock_test_id)

    def _resync_total_questions(self, db: Session, mock_test_id: int) -> None:
        from app.modules.mock_test.repository import MockTestRepository

        mock_test = MockTestRepository().get_by_id(db, mock_test_id)
        if mock_test is not None:
            mock_test.total_questions = len(self.repository.get_by_mock_test(db, mock_test_id))
            db.commit()


mock_test_question_service = MockTestQuestionService()
