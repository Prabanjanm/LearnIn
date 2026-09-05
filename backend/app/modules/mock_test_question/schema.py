from pydantic import BaseModel, ConfigDict

from app.modules.question.schema import QuestionPublicResponse


class MockTestQuestionCreate(BaseModel):
    mock_test_id: int
    question_id: int
    question_order: int | None = None


class MockTestQuestionReorder(BaseModel):
    question_ids: list[int]


class MockTestQuestionResponse(BaseModel):

    id: int
    question_order: int
    question: QuestionPublicResponse

    model_config = ConfigDict(
        from_attributes=True
    )
