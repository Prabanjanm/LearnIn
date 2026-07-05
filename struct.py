import os

PROJECT_NAME = "LearnIn"

structure = {
    PROJECT_NAME: {
        "backend": {
            "app": {
                "routers": [
                    "__init__.py",
                    "home.py",
                    "exam.py",
                    "department.py",
                    "subject.py",
                    "paper.py",
                    "practice.py",
                    "mock_test.py",
                    "search.py",
                    "blog.py",
                    "download.py",
                ],

                "models": [
                    "__init__.py",
                    "exam.py",
                    "department.py",
                    "subject.py",
                    "paper.py",
                    "question.py",
                    "option.py",
                    "mock_test.py",
                    "download.py",
                    "note.py",
                    "blog.py",
                ],

                "schemas": [
                    "__init__.py",
                ],

                "repositories": [
                    "__init__.py",
                    "exam_repository.py",
                    "department_repository.py",
                    "subject_repository.py",
                    "paper_repository.py",
                    "question_repository.py",
                    "mock_repository.py",
                ],

                "services": [
                    "__init__.py",
                    "drive_service.py",
                    "pdf_service.py",
                    "search_service.py",
                    "practice_service.py",
                    "mock_service.py",
                ],

                "utils": [
                    "__init__.py",
                    "constants.py",
                    "helpers.py",
                ],

                "middleware": [
                    "__init__.py",
                ],

                "templates": {
                    "layouts": [
                        "base.html",
                        "navbar.html",
                        "footer.html",
                    ],

                    "home": [
                        "index.html",
                    ],

                    "exam": [
                        "exam.html",
                    ],

                    "department": [
                        "department.html",
                    ],

                    "subject": [
                        "subject.html",
                    ],

                    "paper": [
                        "papers.html",
                        "practice.html",
                    ],

                    "mock_test": [
                        "mock_test.html",
                    ],

                    "blog": [
                        "blog.html",
                    ],

                    "search": [
                        "search.html",
                    ],

                    "errors": [
                        "404.html",
                    ],
                },

                "static": {
                    "css": [
                        "base.css",
                        "layout.css",
                        "navbar.css",
                        "footer.css",
                        "home.css",
                        "exam.css",
                        "subject.css",
                        "practice.css",
                        "mobile.css",
                    ],

                    "js": [
                        "main.js",
                        "search.js",
                        "practice.js",
                        "mock_test.js",
                    ],

                    "images": [],
                    "icons": [],
                },

                "main.py": None,
                "database.py": None,
                "config.py": None,
                "dependencies.py": None,
            },

            "alembic": {},
            "tests": {},
            "requirements.txt": None,
            ".env": None,
            ".gitignore": None,
        },

        "admin": {
            "templates": {},
            "static": {},
            "main.py": None,
        },

        "docs": {
            "README.md": None,
            "DATABASE.md": None,
            "ROADMAP.md": None,
        }
    }
}


def create(base, tree):
    for name, content in tree.items():
        path = os.path.join(base, name)

        if isinstance(content, dict):
            os.makedirs(path, exist_ok=True)
            create(path, content)

        elif isinstance(content, list):
            os.makedirs(path, exist_ok=True)
            for file in content:
                open(os.path.join(path, file), "a").close()

        elif content is None:
            os.makedirs(base, exist_ok=True)
            open(path, "a").close()


create(".", structure)

print("✅ LearnIn folder structure created successfully.")