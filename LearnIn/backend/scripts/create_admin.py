"""
Bootstrap the first admin account (there is no public signup - by design).

Usage:
    cd backend
    python scripts/create_admin.py <email> <password> [full_name]
"""
import sys

sys.path.insert(0, ".")

from app.core.database import SessionLocal  # noqa: E402
from app.modules.admin.schema import AdminLogin  # noqa: E402, F401 - documents the login shape
from app.modules.admin.service import admin_service  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/create_admin.py <email> <password> [full_name]")
        raise SystemExit(1)

    email, password = sys.argv[1], sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else None

    db = SessionLocal()
    try:
        admin = admin_service.create_admin(db, email=email, password=password, full_name=full_name)
        print(f"Admin created: {admin.email} (id={admin.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
