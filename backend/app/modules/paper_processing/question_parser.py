"""
Question/option detection - stage 5 of the pipeline.

The single hard rule of this module: **it never invents text.** Every
question and option string it returns is a whitespace-normalized slice of
the text it was given. It does not paraphrase, complete, spell-correct or
"fix" anything, and it never fabricates an answer key. Where it is unsure,
it lowers `confidence` and raises `needs_review` so a human looks - it does
not guess and present the guess as fact.

Boundary detection works on character offsets: each question block runs
from its own start marker up to (but not including) the next detected
question start, or end of document. That is the guard against merging Q10
into Q11 or splitting one question in half.
"""
import re
import statistics
from dataclasses import dataclass, field

from app.core.enums import ExtractionConfidenceEnum

from .extraction import PAGE_BREAK_MARKER

OPTION_LABELS = ("A", "B", "C", "D")

MAX_OPTIONS = len(OPTION_LABELS)


# --------------------------------------------------------- question starts --
# Line-anchored, tolerant of the numbering styles real papers use.
# Ordered most-specific first; an explicit "Q"/"Question" marker is
# unambiguous, a bare number is not (see _accept_candidates).

_QUESTION_START_PATTERNS = [
    # "Question 1:", "Question 1."
    (re.compile(r"^[ \t]*Question[ \t]+(\d{1,3})[ \t]*[.:)\-]?[ \t]+", re.M | re.I), True),
    # "Q1.", "Q.1", "Q 1)", "Q1"
    (re.compile(r"^[ \t]*Q[ \t]*\.?[ \t]*(\d{1,3})[ \t]*[.:)\-]?[ \t]+", re.M), True),
    # "1.", "1)", "01."
    (re.compile(r"^[ \t]*(\d{1,3})[ \t]*[.)][ \t]+", re.M), False),
]


# ------------------------------------------------------------ option starts --
# Letter options may appear inline ("A) foo  B) bar" on one line), so they
# are matched at a start-of-line *or* after whitespace. The `(?:^|(?<=\s))`
# guard is what keeps "f(1) = 2" or "see (b) above" mid-sentence from being
# mistaken for a marker.
_LETTER_OPTION_RE = re.compile(
    r"(?:^|(?<=\s))(?:\(([A-Da-d])\)|([A-Da-d])[.)])[ \t]+",
    re.M,
)

# Numeric options are only ever recognised *inside* an already-delimited
# question block, and only at the start of a line - otherwise they would be
# indistinguishable from the outer "1." question numbering.
_NUMERIC_OPTION_RE = re.compile(
    r"^[ \t]*(?:\(([1-4])\)|([1-4])[.)])[ \t]+",
    re.M,
)


@dataclass
class ParsedOption:
    label: str
    option_text: str


@dataclass
class ParsedQuestion:
    question_number: int | None
    question_text: str
    raw_source_text: str
    options: list[ParsedOption] = field(default_factory=list)
    confidence: ExtractionConfidenceEnum = ExtractionConfidenceEnum.MEDIUM
    needs_review: bool = False
    # Character offsets [start, end) of this question's block within the
    # *original* text passed to `parse_questions` (the same string returned
    # by `extract_text`/`extract_text_with_positions`). Used only to
    # associate diagrams/images by page position - never shown to the admin
    # and irrelevant to the question/option text itself.
    start: int = 0
    end: int = 0


def normalize_whitespace(text: str) -> str:
    """
    Collapses runs of whitespace. This is the ONLY transformation applied to
    extracted content - the characters themselves are never altered.
    """
    return re.sub(r"[ \t\r\f\v]*\n[ \t\r\f\v]*", "\n", (text or "").strip())


def _flatten(text: str) -> str:
    """Single-line form, for fields that should not carry hard breaks."""
    return re.sub(r"\s+", " ", (text or "")).strip()


@dataclass
class _Candidate:
    start: int
    number: int
    explicit: bool          # had a "Q"/"Question" marker


def _find_candidates(text: str) -> list[_Candidate]:
    seen_starts: dict[int, _Candidate] = {}

    for pattern, explicit in _QUESTION_START_PATTERNS:
        for match in pattern.finditer(text):
            start = match.start()
            candidate = _Candidate(
                start=start,
                number=int(match.group(1)),
                explicit=explicit,
            )
            # An earlier (more specific) pattern wins for the same offset:
            # "Q1." should not also be read as the bare-number style.
            seen_starts.setdefault(start, candidate)

    return sorted(seen_starts.values(), key=lambda item: item.start)


def _accept_candidates(candidates: list[_Candidate]) -> list[_Candidate]:
    """
    Filters candidate starts down to a plausible question sequence.

    A bare "1)" is genuinely ambiguous: it is the standard style for both
    question numbering and numeric option lists. The disambiguator is
    monotonicity - a numeric option block inside question 7 reads 1),2),3),4),
    all of which are <= the last accepted question number and so are
    rejected. An explicit "Q7."/"Question 7:" marker is never ambiguous and
    is always accepted.
    """
    accepted: list[_Candidate] = []
    last_number = 0

    for candidate in candidates:
        if candidate.explicit:
            accepted.append(candidate)
            last_number = max(last_number, candidate.number)
            continue

        if not accepted:
            accepted.append(candidate)
            last_number = candidate.number
            continue

        if candidate.number > last_number:
            accepted.append(candidate)
            last_number = candidate.number

    return accepted


def _split_options(block_body: str) -> tuple[str, list[ParsedOption], bool]:
    """
    Splits one question block into (question_text, options, irregular).

    `irregular` flags a parse that succeeded but looked odd enough to be
    worth a human glance (e.g. lettered options that skip a letter).
    """
    letter_matches = list(_LETTER_OPTION_RE.finditer(block_body))
    numeric_matches = list(_NUMERIC_OPTION_RE.finditer(block_body))

    matches: list[re.Match] = []
    raw_labels: list[str] = []

    if len(letter_matches) >= 2:
        matches = letter_matches
        raw_labels = [(m.group(1) or m.group(2)) for m in letter_matches]
    elif len(numeric_matches) >= 2:
        matches = numeric_matches
        raw_labels = [(m.group(1) or m.group(2)) for m in numeric_matches]
    elif len(letter_matches) == 1:
        matches = letter_matches
        raw_labels = [(letter_matches[0].group(1) or letter_matches[0].group(2))]
    elif len(numeric_matches) == 1:
        matches = numeric_matches
        raw_labels = [(numeric_matches[0].group(1) or numeric_matches[0].group(2))]

    if not matches:
        # No option line found at all: the whole block is the question text.
        return normalize_whitespace(block_body), [], False

    question_text = normalize_whitespace(block_body[: matches[0].start()])

    # Everything after a marker, up to the next marker, is that option's text.
    bodies: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(block_body)
        bodies.append(_flatten(block_body[match.end():end]))

    irregular = False

    upper_labels = [label.upper() for label in raw_labels]
    letters_in_order = (
        all(label.isalpha() for label in upper_labels)
        and upper_labels == list(OPTION_LABELS[: len(upper_labels)])
    )

    if letters_in_order:
        # Genuine A/B/C/D in order - preserve the source's own mapping.
        labels = upper_labels
    else:
        # Numeric, lowercase-out-of-order, or a skipped letter: trusting a
        # literal "(c)" when "(b)" never appeared would silently mislabel
        # the answer key, so fall back to position.
        labels = list(OPTION_LABELS[: len(bodies)])
        if all(label.isalpha() for label in upper_labels):
            irregular = True

    options: list[ParsedOption] = []
    for label, body in zip(labels, bodies):
        if not body:
            # An empty option body is a parse artifact, not content. Skip it
            # rather than storing an empty "option".
            irregular = True
            continue
        options.append(ParsedOption(label=label, option_text=body))

    if len(options) > MAX_OPTIONS:
        # More than four markers means something was over-matched. Keep the
        # first four and flag it - the admin sees the raw block either way.
        options = options[:MAX_OPTIONS]
        irregular = True

    return question_text, options, irregular


def _grade(
    question_text: str,
    options: list[ParsedOption],
    irregular: bool,
    ocr_used: bool,
    is_length_outlier: bool,
) -> ExtractionConfidenceEnum:
    levels = [
        ExtractionConfidenceEnum.HIGH,
        ExtractionConfidenceEnum.MEDIUM,
        ExtractionConfidenceEnum.LOW,
    ]

    if len(options) <= 1 or not question_text.strip():
        return ExtractionConfidenceEnum.LOW

    if len(options) == MAX_OPTIONS and len(question_text) >= 15:
        index = 0                       # HIGH
    else:
        index = 1                       # MEDIUM (2-3 options, or terse text)

    if irregular:
        index += 1

    if ocr_used:
        # OCR output is inherently less reliable than a real text layer,
        # so an OCR'd block never reaches HIGH on its own.
        index += 1

    if is_length_outlier:
        # Far shorter or far longer than its neighbours usually means the
        # block boundary was wrong - a merge or a split.
        index += 1

    return levels[min(index, len(levels) - 1)]


def parse_questions(text: str, ocr_used: bool = False) -> list[ParsedQuestion]:
    """
    Segments extracted text into questions with options.

    Returns [] when nothing question-shaped is found - which is a real,
    reportable outcome, not an error to paper over.
    """
    if not text or not text.strip():
        return []

    # Candidates are found against the *original* text (marker intact), so
    # each ParsedQuestion's start/end offsets stay valid against whatever
    # PositionedBlock list the extractor produced for this same string - the
    # page-break marker contains no digits and is always on its own line, so
    # its presence never affects which lines match a question-start pattern.
    accepted = _accept_candidates(_find_candidates(text))

    if not accepted:
        return []

    # Slice each block by offsets: [this start, next start).
    blocks: list[tuple[_Candidate, int, str]] = []
    for index, candidate in enumerate(accepted):
        end = accepted[index + 1].start if index + 1 < len(accepted) else len(text)
        blocks.append((candidate, end, text[candidate.start:end]))

    lengths = [len(block) for _candidate, _end, block in blocks]
    median_length = statistics.median(lengths) if lengths else 0
    outlier_check = len(blocks) >= 3 and median_length > 0

    parsed: list[ParsedQuestion] = []

    for (candidate, block_end, raw_block), length in zip(blocks, lengths):
        # Page-break markers become ordinary newlines for content purposes
        # only, after offsets have already been captured above - a question
        # is allowed to continue across a page, and only the next question's
        # start pattern ends a block.
        block = raw_block.replace(PAGE_BREAK_MARKER, "\n")

        # Drop only the matched numbering prefix; the rest is untouched.
        body = block
        for pattern, _explicit in _QUESTION_START_PATTERNS:
            match = pattern.match(body)
            if match:
                body = body[match.end():]
                break

        question_text, options, irregular = _split_options(body)

        if not question_text and not options:
            continue

        is_outlier = bool(
            outlier_check
            and (length < median_length * 0.3 or length > median_length * 3)
        )

        confidence = _grade(
            question_text=question_text,
            options=options,
            irregular=irregular,
            ocr_used=ocr_used,
            is_length_outlier=is_outlier,
        )

        parsed.append(ParsedQuestion(
            question_number=candidate.number,
            question_text=question_text,
            raw_source_text=normalize_whitespace(block),
            options=options,
            confidence=confidence,
            needs_review=confidence == ExtractionConfidenceEnum.LOW,
            start=candidate.start,
            end=block_end,
        ))

    return parsed
