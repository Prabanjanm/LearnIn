"""
Pure unit tests for the question/option parser - no DB, no PDFs, just
strings in and structured questions out.
"""
from app.core.enums import ExtractionConfidenceEnum
from app.modules.paper_processing.extraction import PAGE_BREAK_MARKER
from app.modules.paper_processing.question_parser import parse_questions

HIGH = ExtractionConfidenceEnum.HIGH
MEDIUM = ExtractionConfidenceEnum.MEDIUM
LOW = ExtractionConfidenceEnum.LOW


def test_dotted_numbering_style():
    text = """1. What is the capital of France?
A) Paris
B) Rome
C) Madrid
D) Berlin
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    assert questions[0].question_number == 1
    assert questions[0].question_text == "What is the capital of France?"
    assert [option.label for option in questions[0].options] == ["A", "B", "C", "D"]
    assert questions[0].options[0].option_text == "Paris"
    assert questions[0].confidence == HIGH


def test_q_prefixed_numbering_style():
    text = """Q1. Which planet is closest to the Sun?
(a) Venus
(b) Mercury
(c) Mars
(d) Earth
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    assert questions[0].question_text == "Which planet is closest to the Sun?"
    assert [option.option_text for option in questions[0].options] == [
        "Venus", "Mercury", "Mars", "Earth",
    ]


def test_question_word_numbering_style():
    text = """Question 5: Which gas do plants absorb?
A. Oxygen
B. Carbon dioxide
C. Nitrogen
D. Helium
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    assert questions[0].question_number == 5
    assert questions[0].question_text == "Which gas do plants absorb?"
    assert len(questions[0].options) == 4


def test_question_text_spanning_multiple_lines_is_kept_together():
    text = """1. A train travelling at 60 km/h covers a certain distance
in 3 hours. How long would the same journey take at 90 km/h,
assuming constant speed throughout?
A) 1 hour
B) 2 hours
C) 2.5 hours
D) 3 hours
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    question_text = questions[0].question_text
    assert "A train travelling at 60 km/h" in question_text
    assert "assuming constant speed throughout?" in question_text
    assert len(questions[0].options) == 4


def test_adjacent_consecutive_questions_are_not_merged():
    text = """10. First question here?
A) one
B) two
C) three
D) four

11. Second question here?
A) five
B) six
C) seven
D) eight
"""
    questions = parse_questions(text)

    assert len(questions) == 2
    assert [question.question_number for question in questions] == [10, 11]
    assert questions[0].question_text == "First question here?"
    assert questions[1].question_text == "Second question here?"
    assert "Second question here?" not in questions[0].question_text


def test_numeric_options_are_not_mistaken_for_new_questions():
    text = """7. Which of these is prime?
1) 4
2) 6
3) 7
4) 9
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    assert questions[0].question_number == 7
    # Numeric source labels are normalized to A/B/C/D by position.
    assert [option.label for option in questions[0].options] == ["A", "B", "C", "D"]
    assert [option.option_text for option in questions[0].options] == ["4", "6", "7", "9"]


def test_two_option_block_is_medium_confidence():
    text = """1. Is the Earth round?
A) Yes
B) No
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    assert len(questions[0].options) == 2
    assert questions[0].confidence == MEDIUM
    assert questions[0].needs_review is False


def test_block_without_parseable_options_is_low_confidence_and_flagged():
    text = """1. Describe in your own words how a hash table resolves collisions
using separate chaining, with an example.
"""
    questions = parse_questions(text)

    assert len(questions) == 1
    assert questions[0].options == []
    assert questions[0].confidence == LOW
    assert questions[0].needs_review is True


def test_ocr_flavoured_block_never_silently_reaches_high_confidence():
    # Typos/artifacts are exactly what OCR produces; the parser must not
    # present this as a clean, high-confidence parse.
    text = """1. Wh1ch of these is a prlme number?
A) 4
B) 6
C) 7
D) 9
"""
    questions = parse_questions(text, ocr_used=True)

    assert len(questions) == 1
    assert questions[0].confidence in (MEDIUM, LOW)
    # The text is still verbatim - the parser corrected nothing.
    assert "Wh1ch" in questions[0].question_text


def test_question_may_continue_across_a_page_break():
    text = (
        "1. A long question that begins on the first page and"
        + PAGE_BREAK_MARKER
        + "continues onto the second page?\nA) one\nB) two\nC) three\nD) four\n"
    )
    questions = parse_questions(text)

    assert len(questions) == 1
    assert "begins on the first page" in questions[0].question_text
    assert "continues onto the second page?" in questions[0].question_text
    assert PAGE_BREAK_MARKER.strip() not in questions[0].question_text


def test_next_question_start_wins_over_a_page_break():
    text = (
        "1. First?\nA) a\nB) b\nC) c\nD) d\n"
        + PAGE_BREAK_MARKER
        + "2. Second?\nA) e\nB) f\nC) g\nD) h\n"
    )
    questions = parse_questions(text)

    assert len(questions) == 2
    assert questions[0].question_text == "First?"
    assert questions[1].question_text == "Second?"


def test_parser_returns_nothing_for_text_with_no_questions():
    assert parse_questions("Just a paragraph of prose with no numbering at all.") == []
    assert parse_questions("") == []


def test_extracted_text_is_verbatim():
    source = "3. What is 2 + 2 (in base 10)?\nA) 3\nB) 4\nC) 5\nD) 6\n"
    questions = parse_questions(source)

    assert questions[0].question_text in source.replace("\n", " ") or \
        questions[0].question_text == "What is 2 + 2 (in base 10)?"
    for option in questions[0].options:
        assert option.option_text in source


def test_skipped_option_letter_falls_back_to_positional_labels():
    text = """1. Pick one.
A) alpha
B) beta
D) delta
"""
    questions = parse_questions(text)

    # The source skipped "C"; trusting the literal "D" would mislabel the
    # third option, so labelling falls back to position.
    assert [option.label for option in questions[0].options] == ["A", "B", "C"]
    assert questions[0].options[2].option_text == "delta"
