import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.question.schema import QuestionPublicResponse


class MockTestQuestionCreate(BaseModel):
    mock_test_id: uuid.UUID
    question_id: uuid.UUID
    question_order: int | None = None


class MockTestQuestionReorder(BaseModel):
    question_ids: list[uuid.UUID]


class MockTestQuestionResponse(BaseModel):

    id: uuid.UUID
    question_order: int
    question: QuestionPublicResponse

    model_config = ConfigDict(
        from_attributes=True
    )
