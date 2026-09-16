"""
Unit coverage for the GATE-style answer-key table parser
(app/modules/paper_processing/answer_key_parser.py) - a separate, optional
enrichment stage that reads a "Answer Key" PDF (Q.No/Session/Q.Type/Section/
Key-or-Range/Marks columns) and fills in question_type/marks/correct_answer
for the matching extracted questions.
"""
import fitz

from app.core.enums import QuestionType
from app.modules.paper_processing.answer_key_parser import (
    gate_negative_marks,
    parse_answer_key,
)


def test_parses_every_row_of_the_real_gate_sample_format():
    text = (
        "Answer Key for Computer Science and Information Technology 1 (CS1)\n"
        "Q. No.\nSession\nQ. Type\nSection\nKey/Range\nMarks\n"
        "1\n1\nMCQ\nGA\nA\n1\n"
        "2\n1\nMCQ\nGA\nB\n1\n"
        "21\n1\nMSQ\nCS-1\nB;D\n1\n"
        "27\n1\nMSQ\nCS-1\nA;B;C\n1\n"
        "31\n1\nNAT\nCS-1\n-2.1 to -1.9\n1\n"
        "32\n1\nNAT\nCS-1\n0.49 to 0.51\n1\n"
        "65\n1\nNAT\nCS-1\n10 to 11\n2\n"
    )

    entries = parse_answer_key(text)

    assert len(entries) == 7
    assert entries[0].q_no == 1
    assert entries[0].question_type == QuestionType.MCQ
    assert entries[0].key_or_range == "A"
    assert entries[0].marks == 1.0

    msq = next(e for e in entries if e.q_no == 21)
    assert msq.question_type == QuestionType.MSQ
    assert msq.key_or_range == "B;D"

    nat = next(e for e in entries if e.q_no == 31)
    assert nat.question_type == QuestionType.NAT
    assert nat.key_or_range == "-2.1 to -1.9"

    last = entries[-1]
    assert last.q_no == 65
    assert last.marks == 2.0


def test_parses_the_actual_sample_pdf_shipped_in_assets():
    import pathlib

    pdf_path = pathlib.Path(__file__).resolve().parents[1] / "assets" / "GATE-CS-2025-Set-1-Answer-Key.pdf"
    if not pdf_path.exists():
        import pytest
        pytest.skip("sample GATE answer key PDF not present in this checkout")

    document = fitz.open(str(pdf_path))
    text = "\n".join(page.get_text() for page in document)
    document.close()

    entries = parse_answer_key(text)

    assert len(entries) == 65
    assert entries[0].q_no == 1 and entries[0].key_or_range == "A"
    assert entries[-1].q_no == 65 and entries[-1].key_or_range == "10 to 11"


def test_a_malformed_row_is_skipped_not_raised():
    text = (
        "1\n1\nMCQ\nGA\nA\n1\n"
        # Row 2's Marks column is garbled text, not a number.
        "2\n1\nMCQ\nGA\nB\nN/A\n"
        "3\n1\nMCQ\nGA\nC\n1\n"
    )

    entries = parse_answer_key(text)

    assert [e.q_no for e in entries] == [1, 3]


def test_nat_row_missing_the_to_joiner_is_skipped():
    text = "1\n1\nNAT\nCS-1\n5 and 5\n1\n2\n1\nMCQ\nCS-1\nA\n1\n"

    entries = parse_answer_key(text)

    assert [e.q_no for e in entries] == [2]


def test_gate_negative_marks_follows_the_official_rule():
    assert gate_negative_marks(QuestionType.MCQ, 1.0) == round(1 / 3, 4)
    assert gate_negative_marks(QuestionType.MCQ, 2.0) == round(2 / 3, 4)
    assert gate_negative_marks(QuestionType.MSQ, 2.0) == 0.0
    assert gate_negative_marks(QuestionType.NAT, 2.0) == 0.0


def test_empty_text_parses_to_no_entries():
    assert parse_answer_key("") == []
