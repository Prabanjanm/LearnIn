"""
Deletes abandoned MockTestSession rows - sessions a student started but
never submitted, and whose deadline passed a long time ago (default: more
than 24 hours past the mock test's own duration). Cascades to their
MockTestSessionAnswer rows via the model's cascade="all, delete-orphan".

This never touches MockTestAttempt/MockTestAttemptAnswer (the actual
scored results) - a session is purely the in-progress "what did the
student answer so far" scratch state; deleting an old, abandoned one has
no effect on anyone's score or result history.

There is no scheduler in this project (no Celery/cron worker), so this is
a standalone script to run manually or wire into whatever job runner the
deployment environment already has - matching scripts/create_admin.py and
scripts/seed_mock_data.py, the existing pattern for one-off maintenance
tasks here.

Usage:
    cd backend
    python scripts/cleanup_expired_mock_test_sessions.py [--hours 24] [--dry-run]
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

import app.models  # noqa: E402, F401 - registers every model so relationship() strings resolve

from app.core.database import SessionLocal  # noqa: E402
from app.modules.mock_test.model import MockTest  # noqa: E402
from app.modules.mock_test_attempt.model import MockTestSession  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24, help="Grace period past a session's own deadline before it's deleted (default: 24)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be deleted without deleting")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        candidates = (
            db.query(MockTestSession)
            .join(MockTest, MockTestSession.mock_test_id == MockTest.id)
            .filter(MockTestSession.submitted_at.is_(None))
            .all()
        )

        stale = [
            session for session in candidates
            if now >= session.started_at + timedelta(minutes=session.mock_test.duration) + timedelta(hours=args.hours)
        ]

        if args.dry_run:
            print(f"Would delete {len(stale)} abandoned session(s) (of {len(candidates)} still-unsubmitted total).")
            return

        for session in stale:
            db.delete(session)
        db.commit()

        print(f"Deleted {len(stale)} abandoned session(s) (of {len(candidates)} still-unsubmitted total).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
