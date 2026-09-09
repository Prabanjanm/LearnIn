"""
CLI wrapper around app.common.utils.gate_pyq_import.import_gate_paper - see
that module's docstring for the required input JSON shape and exactly how
idempotency/hierarchy-mapping/validation work.

This script does not source or upload PDFs itself - it expects the source
question paper (and, optionally, answer key) to already be uploaded via the
existing admin upload endpoint (POST /admin/upload), and the resulting
Drive file id passed in the input JSON's "question_pdf_file_id" /
"answer_pdf_file_id" fields. That keeps file storage on the one existing
path this app already uses (app/core/google_drive.py) - this script never
talks to Drive directly.

Defaults to a dry run: builds the same report, then rolls back instead of
committing. Pass --execute to actually commit.

Usage:
    cd backend
    python scripts/import_gate_pyq.py path/to/gate_cs_2023.json              # dry run
    python scripts/import_gate_pyq.py path/to/gate_cs_2023.json --execute    # commits
"""
import argparse
import json
import sys

sys.path.insert(0, ".")

import app.models  # noqa: E402, F401 - registers every model so relationship() strings resolve

from app.common.utils.gate_pyq_import import import_gate_paper  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json", help="Path to a payload matching the shape documented in app/common/utils/gate_pyq_import.py")
    parser.add_argument("--execute", action="store_true", help="Actually commit. Without this flag, changes are rolled back after reporting.")
    args = parser.parse_args()

    with open(args.input_json, encoding="utf-8") as fh:
        payload = json.load(fh)

    db = SessionLocal()
    try:
        report = import_gate_paper(db, payload)
        print(report.summary())

        if not report.ok:
            db.rollback()
            sys.exit(1)

        if args.execute:
            db.commit()
            print("\nCommitted.")
        else:
            db.rollback()
            print("\nDry run only - rolled back. Re-run with --execute to commit.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
