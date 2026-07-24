from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.modules.mock_test_question.model import MockTestQuestion
from app.modules.mock_test_question.repository import MockTestQuestionRepository
from app.modules.question.service import QuestionService

from .model import MockTest
from .repository import MockTestRepository
from .schema import (
    MockTestCreate,
    MockTestResult,
    MockTestSubmission,
    QuestionResult,
)


class MockTestService(BaseService):

    def __init__(self):
        super().__init__(MockTestRepository())
        self._mock_test_question_repository = MockTestQuestionRepository()
        self._question_service = QuestionService()

    def create_mock_test(
        self,
        db: Session,
        data: MockTestCreate
    ) -> MockTest:

        mock_test = MockTest(
            paper_id=data.paper_id,
            title=data.title,
            description=data.description,
            duration=data.duration,
            total_marks=data.total_marks,
            total_questions=len(data.question_ids),
            questions=[
                MockTestQuestion(question_id=question_id, question_order=index + 1)
                for index, question_id in enumerate(data.question_ids)
            ],
            status=data.status,
        )

        return self.repository.create(db, mock_test)

    def get_published_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return self.repository.get_published_by_paper(db, paper_id)

    def get_published_by_id(
        self,
        db: Session,
        mock_test_id: int
    ) -> MockTest:

        mock_test = self.repository.get_published_by_id(db, mock_test_id)

        if mock_test is None:
            raise NotFoundException("Mock test not found")

        return mock_test

    def submit_attempt(
        self,
        db: Session,
        mock_test_id: int,
        submission: MockTestSubmission
    ) -> MockTestResult:

        mock_test = self.get_published_by_id(db, mock_test_id)

        links = self._mock_test_question_repository.get_by_mock_test(db, mock_test_id)
        answer_map = {item.question_id: item.answer for item in submission.answers}

        results: list[QuestionResult] = []
        scored_marks = 0.0
        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0

        for link in links:
            question = link.question
            submitted = answer_map.get(question.id)

            if submitted is None:
                unanswered_count += 1
                results.append(QuestionResult(
                    question_id=question.id,
                    is_correct=None,
                    marks_awarded=0,
                    correct_answer=question.correct_answer,
                    explanation=question.explanation,
                ))
                continue

            is_correct = self._question_service.is_answer_correct(question, submitted)
            marks_awarded = question.marks if is_correct else -question.negative_marks

            if is_correct:
                correct_count += 1
            else:
                incorrect_count += 1

            scored_marks += marks_awarded

            results.append(QuestionResult(
                question_id=question.id,
                is_correct=is_correct,
                marks_awarded=marks_awarded,
                correct_answer=question.correct_answer,
                explanation=question.explanation,
            ))

        return MockTestResult(
            mock_test_id=mock_test_id,
            total_marks=mock_test.total_marks,
            scored_marks=scored_marks,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unanswered_count=unanswered_count,
            results=results,
        )


mock_test_service = MockTestService()
