import os
import tempfile

# Must run before any `app.*` import - config/database read these at import time.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.gettempdir(), "learnin_test.db"
).replace("\\", "/")
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"
os.environ.setdefault("GOOGLE_DRIVE_FOLDER_ID", "test-folder-id")
os.environ.pop("GOOGLE_OAUTH_CLIENT_ID", None)
os.environ.pop("GOOGLE_OAUTH_CLIENT_SECRET", None)
os.environ.pop("GOOGLE_OAUTH_REFRESH_TOKEN", None)

import pytest  # noqa: E402

import app.models  # noqa: E402, F401 - registers every model on Base.metadata
from app.core.base import Base  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def admin_auth_headers(_tables):
    from app.core.security import create_access_token, hash_password
    from app.modules.admin.model import Admin

    session = SessionLocal()
    try:
        admin = Admin(
            email="fixture-admin@learnin.app",
            hashed_password=hash_password("FixtureAdminPass123!"),
            full_name="Fixture Admin",
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        token = create_access_token(subject=admin.email)
    finally:
        session.close()

    return {"Authorization": f"Bearer {token}"}
