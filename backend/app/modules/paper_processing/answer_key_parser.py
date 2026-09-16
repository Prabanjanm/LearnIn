"""
Answer-key table parsing - an optional enrichment stage that runs when the
admin also uploads a separate "Answer Key" PDF alongside the source question
paper.

This is a different document shape from the question paper itself: a plain
table (`Q.No / Session / Q.Type / Section / Key-or-Range / Marks`), one value
per line once text-extracted, e.g. the standard format GATE publishes its
answer keys in. Like `question_parser.py`, this module never invents
anything - it only reads literal table values already stated in the PDF: an
official Q.Type/Key/Marks column is not a guess, unlike inferring those same
things from a question paper's prose (which the pipeline deliberately never
does - see `service.py`'s `DEFAULT_QUESTION_TYPE` et al.).

Row grammar (anchored on the Q.Type token, which is always literally
"MCQ"/"MSQ"/"NAT"):

    <Q.No int> <Session int> <Q.Type> <Section token> <answer> <Marks int>

`<answer>` is a single token for MCQ/MSQ (e.g. "A", "B;D", "A;B;C" - already
one whitespace-free token as extracted) and three tokens "<num> to <num>" for
NAT (e.g. "-2.1 to -1.9"). Any row that does not fit this shape is skipped
and logged, never raised - a partially-unreadable key must not lose the rest
of it, nor fail the pipeline.
"""
import logging
import re
from dataclasses import dataclass

from app.core.enums import QuestionType

logger = logging.getLogger(__name__)

_QUESTION_TYPE_TOKENS = {"MCQ": QuestionType.MCQ, "MSQ": QuestionType.MSQ, "NAT": QuestionType.NAT}

# One value per line once PyMuPDF/pytesseract have extracted the table text -
# blank lines and stray whitespace are dropped, everything else kept as a
# token in reading order.
_TOKEN_RE = re.compile(r"\S+")


@dataclass
class ParsedAnswerKeyEntry:

    q_no: int
    question_type: QuestionType
    key_or_range: str
    marks: float


def gate_negative_marks(question_type: QuestionType, marks: float) -> float:
    """
    The standard, published GATE negative-marking rule - not an inference,
    a fixed official rule applied uniformly: MCQ loses a third of its marks
    per wrong answer (1 mark -> -1/3, 2 marks -> -2/3); MSQ and NAT never
    carry negative marking.
    """
    if question_type == QuestionType.MCQ:
        return round(marks / 3, 4)
    return 0.0


def parse_answer_key(text: str) -> list[ParsedAnswerKeyEntry]:
    tokens = _TOKEN_RE.findall(text)
    entries: list[ParsedAnswerKeyEntry] = []

    i = 0
    while i < len(tokens):
        # Scan forward for the next Q.Type token - it is the one reliable,
        # unambiguous anchor in the row (Q.No/Session/Marks are all plain
        # integers and cannot be told apart from each other on their own).
        if tokens[i] not in _QUESTION_TYPE_TOKENS:
            i += 1
            continue

        q_type_index = i
        try:
            q_no = int(tokens[q_type_index - 2])
            # tokens[q_type_index - 1] is the Session column - not used.
            question_type = _QUESTION_TYPE_TOKENS[tokens[q_type_index]]
            # tokens[q_type_index + 1] is the Section column - not used here
            # (a paper's subject is chosen once on the upload form, not
            # re-derived per row - see the pipeline's plan notes).

            if question_type == QuestionType.NAT:
                lo = tokens[q_type_index + 2]
                joiner = tokens[q_type_index + 3]
                hi = tokens[q_type_index + 4]
                if joiner.lower() != "to":
                    raise ValueError(f"expected 'to' between NAT range bounds, got {joiner!r}")
                float(lo)
                float(hi)
                key_or_range = f"{lo} to {hi}"
                marks_token = tokens[q_type_index + 5]
            else:
                key_or_range = tokens[q_type_index + 2]
                marks_token = tokens[q_type_index + 3]

            marks = float(marks_token)
        except (IndexError, ValueError) as exc:
            logger.warning("Answer key: could not parse row near token %d (%s) - skipping", q_type_index, exc)
            i = q_type_index + 1
            continue

        entries.append(ParsedAnswerKeyEntry(
            q_no=q_no, question_type=question_type, key_or_range=key_or_range, marks=marks,
        ))
        i = q_type_index + (6 if question_type == QuestionType.NAT else 4)

    return entries
