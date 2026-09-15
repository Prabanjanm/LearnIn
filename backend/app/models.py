from app.modules.admin.model import Admin
from app.modules.exam.model import Exam
from app.modules.department.model import Department
from app.modules.subject.model import Subject
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.option.model import Option
from app.modules.mock_test.model import MockTest
from app.modules.mock_test_question.model import MockTestQuestion
from app.modules.mock_test_attempt.model import (
    MockTestAttempt,
    MockTestAttemptAnswer,
    MockTestSession,
    MockTestSessionAnswer,
)
from app.modules.institution.model import Institution, InstitutionUser
from app.modules.conducted_test.model import ConductedTest
from app.modules.conducted_test_attempt.model import ConductedTestAttempt, ConductedTestAttemptAnswer
from app.modules.student.model import Student
from app.modules.resource.model import Resource
from app.modules.blog.model import Blog
from app.modules.search.model import SearchLog
from app.modules.paper_processing.model import (
    PaperProcessingJob,
    ExtractedQuestion,
    ExtractedOption,
    ExtractedQuestionImage,
)