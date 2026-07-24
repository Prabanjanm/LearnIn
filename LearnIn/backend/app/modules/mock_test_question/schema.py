from pydantic import BaseModel, ConfigDict

from app.modules.question.schema import QuestionPublicResponse


class MockTestQuestionResponse(BaseModel):

    question_order: int
    question: QuestionPublicResponse

    model_config = ConfigDict(
        from_attributes=True
    )
