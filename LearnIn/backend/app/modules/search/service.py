from sqlalchemy.orm import Session

from app.modules.blog.repository import BlogRepository
from app.modules.department.repository import DepartmentRepository
from app.modules.exam.repository import ExamRepository
from app.modules.paper.repository import PaperRepository
from app.modules.question.repository import QuestionRepository
from app.modules.resource.repository import ResourceRepository
from app.modules.subject.repository import SubjectRepository

from .repository import SearchLogRepository
from .schema import SearchResponse, SearchResultItem


class SearchService:

    def __init__(self):
        self._exam_repository = ExamRepository()
        self._department_repository = DepartmentRepository()
        self._subject_repository = SubjectRepository()
        self._paper_repository = PaperRepository()
        self._question_repository = QuestionRepository()
        self._blog_repository = BlogRepository()
        self._resource_repository = ResourceRepository()
        self._log_repository = SearchLogRepository()

    def search(
        self,
        db: Session,
        query: str,
        limit_per_type: int = 5
    ) -> SearchResponse:

        results: list[SearchResultItem] = []

        for exam in self._exam_repository.search(db, query, limit_per_type):
            results.append(SearchResultItem(
                type="exam",
                id=exam.id,
                title=exam.name,
                slug=exam.slug,
                url=f"/{exam.slug}",
            ))

        for department in self._department_repository.search(db, query, limit_per_type):
            results.append(SearchResultItem(
                type="department",
                id=department.id,
                title=department.name,
                slug=department.slug,
                url=f"/{department.exam.slug}/{department.slug}",
            ))

        for subject in self._subject_repository.search(db, query, limit_per_type):
            department = subject.department
            results.append(SearchResultItem(
                type="subject",
                id=subject.id,
                title=subject.name,
                slug=subject.slug,
                url=f"/{department.exam.slug}/{department.slug}/{subject.slug}",
            ))

        for paper in self._paper_repository.search(db, query, limit_per_type):
            subject = paper.subject
            department = subject.department
            results.append(SearchResultItem(
                type="paper",
                id=paper.id,
                title=paper.title,
                slug=None,
                url=f"/{department.exam.slug}/{department.slug}/{subject.slug}/{paper.year}",
            ))

        for question in self._question_repository.search(db, query, limit_per_type):
            paper = question.paper
            subject = paper.subject
            department = subject.department
            results.append(SearchResultItem(
                type="question",
                id=question.id,
                title=question.question_text[:120],
                slug=None,
                url=f"/{department.exam.slug}/{department.slug}/{subject.slug}/{paper.year}/practice",
            ))

        for blog in self._blog_repository.search(db, query, limit_per_type):
            results.append(SearchResultItem(
                type="blog",
                id=blog.id,
                title=blog.title,
                slug=blog.slug,
                url=f"/blog/{blog.slug}",
            ))

        for resource in self._resource_repository.search(db, query, limit_per_type):
            subject = resource.subject
            department = subject.department
            results.append(SearchResultItem(
                type="resource",
                id=resource.id,
                title=resource.title,
                slug=None,
                url=f"/{department.exam.slug}/{department.slug}/{subject.slug}#resources",
            ))

        self._log_repository.log(db, query, len(results))

        return SearchResponse(
            query=query,
            total=len(results),
            results=results,
        )


search_service = SearchService()
