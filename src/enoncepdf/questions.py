"""The questions of a statement, found at their number at the start of a line.

An exam statement numbers its questions in a thousand ways: « 12) », « 12. »,
« 12 — », « Q12 », « Q 12. », « Question 12 : », « □ – 12. », « I.A.1) », « 1.a) » when
sub-questions carry a letter. A question is a line that starts with one of these forms
and goes on with text; a part heading, a line that starts with a Roman numeral followed
by a title (« II. Suspension », « I.A. — Champ uniforme ») or with « Partie ».

A question is at the size of the running text: a number at a larger size opens a
heading — « 6 – Corrigé », the number of an assignment under its title —, at a smaller
one a footnote or an index. The running size is the median of the long lines; without
enough lines to measure it, nothing is ruled out.

Shape is not enough: a section heading (« 1 - Énergie électrostatique »), a quantity at
the start of a line (« Q3 désigne la charge »), a caption look like questions. Real
questions follow one another: in the order of the statement, only the **longest
increasing run** of numbers is kept. Numbering may restart at 1 in each part: each
number is then preceded by that of the last part heading before it, and the run grows
part after part. At equal length, a question keeps as neighbour the one written like
it: « 2) » follows « 1) » rather than the heading « 1 - Énergie ».

This reads only the text of the lines, not their typography: it works on lines read by
``PdfDocument`` as by ``PdfiumDocument``, from a whole page or from a crop. The structure
analysis (structure.py) does more on a whole subject — heading levels, sub-questions,
numbering profile — from its typography; its grammar of questions is contained in this
one.

Finding the question a title names (``match``): by its reference (« I.A.1 » for
« I.A.1) », « 12 » for « Q12 »), otherwise by its number, if it names a single question.
"""

import dataclasses
import re
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from enoncepdf.models import Line, LocatedQuestion

__all__ = ["Mark", "comparable_ref", "locate", "marks", "match", "questions"]

# The Mines box and dash (« □ – 7. »: the box is an « o » in Dingbats), then the
# number, in one of its forms.
_QUESTION = re.compile(
    r"\s*(?P<label>(?:(?:[□❏❑■]|o(?=\s*[–—-]))\s*)?(?:[–—-]\s*)?"
    r"(?:"
    r"(?:Question|Q)\s*(?P<q>\d{1,3})\s*[.:)–—-]?"
    r"|(?P<roman>[IVX]{1,4})\.(?:(?P<letter>[A-Z])\.)?(?P<rnum>\d{1,2})"
    r"(?:\.(?P<rsub>[a-z]))?\s*\)?"
    r"|(?P<snum>\d{1,2})\s*\.\s*(?P<sub>[a-z])\s*\)"
    r"|(?P<num>\d{1,2})\s*(?P<sign>\)|\.(?!\d)|[–—-])"
    r"))"
)
_PART = re.compile(
    r"\s*(?:(?:Partie|PARTIE|Part|PART)\s+(?P<pnum>[IVX]{1,4}|\d{1,2})\b"
    r"|(?P<roman>[IVX]{1,4})\s*(?:\.\s*)?(?:[–—-]\s*)?(?=[A-ZÀ-Ý]))"
)
_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_LONG_LINE = 30  # characters: what counts to measure the running size
# The size of a question, around the running size: a point less (a footnote), a point
# and a half more (a heading at 12 pt over a text at 10 pt does not pass).
_SIZE_BELOW, _SIZE_ABOVE = 1.0, 1.5
_ROMANS = {"I": 1, "V": 5, "X": 10}
_ROMANS_BY_VALUE = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


@dataclass(frozen=True, slots=True)
class Mark:
    """A number read at the start of a line: a question or a part heading, its
    reference, its label as printed, its number, its rank in the reading order
    (``order``), its form — « 12) » and « 12 — » are not written alike — and its line."""

    kind: Literal["question", "part"]
    ref: str
    label: str
    number: int
    order: tuple[int, ...]
    form: str
    line: Line


def marks(lines: Iterable[Line]) -> list[Mark]:
    """The questions and part headings that open the lines, in their order."""
    lines = list(lines)
    size = _running_size(lines)
    found = []
    for line in lines:
        text = line.text
        question = _QUESTION.match(text)
        if (
            question is not None
            and _LETTER.search(text[question.end() : question.end() + 12])
            and _at_running_size(line, size)
        ):
            found.append(_question(question, line))
            continue
        part = _PART.match(text)
        if part is not None:
            if part.group("pnum"):
                raw = part.group("pnum")
                value = int(raw) if raw.isdigit() else _roman(raw)
            else:
                value = _roman(part.group("roman"))
            label = text[: part.end()].strip()
            found.append(Mark("part", _to_roman(value), label, value, (value,), "part", line))
    return found


def questions(found: Iterable[Mark]) -> list[LocatedQuestion]:
    """The questions of a statement — or of one of its problems — in order: the longest
    increasing run of numbers, part by part."""
    ranked: list[tuple[Mark, str | None]] = []
    part, ref = 0, None
    for mark in found:
        if mark.kind == "part":
            part, ref = mark.number, mark.ref
            continue
        ranked.append((dataclasses.replace(mark, order=(part, *mark.order)), ref))
    return [
        LocatedQuestion(
            part=part_ref,
            ref=mark.ref,
            label=mark.label,
            number=mark.number,
            page=mark.line.page,
            box=mark.line.box,
        )
        for mark, part_ref in _increasing(ranked)
    ]


def locate(lines: Iterable[Line]) -> list[LocatedQuestion]:
    """The questions some lines carry: ``questions(marks(lines))``."""
    return questions(marks(lines))


def comparable_ref(ref: str | None) -> str:
    """A reference to compare: without spaces or punctuation around, upper case, without
    the « Q » of a number (« Q12 » is « 12 », « I.A.1) » is « I.A.1 »)."""
    text = re.sub(r"\s+", "", ref or "").strip("().:").upper()
    return re.sub(r"^(?:QUESTION|Q)(?=\d)", "", text)


def match(title: str, located: Sequence[LocatedQuestion], other: str | None = None) -> LocatedQuestion | None:
    """The question a title names (« Q12 », « I.A.1 », « 2.6 ») among ``located``: by its
    reference — or that of ``other``, a second title to try —, otherwise by its number,
    the last number of the title, if it names a single question."""
    wanted = {comparable_ref(title), comparable_ref(other)} - {""}
    for question in located:
        if comparable_ref(question.ref) in wanted:
            return question
    numbers = re.findall(r"\d+", title)
    if not numbers:
        return None
    found = [question for question in located if question.number == int(numbers[-1])]
    return found[0] if len(found) == 1 else None


def _running_size(lines: Sequence[Line]) -> float | None:
    """The size of the running text: the median of the long lines, if there are enough."""
    long = [line.size for line in lines if len(line.text) > _LONG_LINE and line.size > 0]
    return statistics.median(long) if len(long) >= 3 else None


def _at_running_size(line: Line, size: float | None) -> bool:
    if size is None or line.size <= 0:
        return True
    return size - _SIZE_BELOW <= line.size <= size + _SIZE_ABOVE


def _question(found: re.Match[str], line: Line) -> Mark:
    label = found.group("label").strip()
    if found.group("q"):
        number = int(found.group("q"))
        return Mark("question", str(number), label, number, (number,), "q", line)
    if found.group("roman"):
        roman, letter = found.group("roman"), found.group("letter")
        number, sub = int(found.group("rnum")), found.group("rsub")
        order = (
            _roman(roman),
            ord(letter) - 64 if letter else 0,
            number,
            *((ord(sub) - 96,) if sub else ()),
        )
        ref = ".".join(piece for piece in (roman, letter, str(number), sub) if piece)
        return Mark("question", ref, label, number, order, "roman", line)
    if found.group("snum"):
        number, sub = int(found.group("snum")), found.group("sub")
        return Mark("question", f"{number}.{sub}", label, number, (number, ord(sub) - 96), "sub", line)
    number = int(found.group("num"))
    sign = found.group("sign")
    form = "num" + ("-" if sign in "–—-" else sign)
    return Mark("question", str(number), label, number, (number,), form, line)


def _increasing(ranked: Sequence[tuple[Mark, str | None]]) -> list[tuple[Mark, str | None]]:
    """The longest run of increasing orders, in order; at equal length, each question
    keeps as neighbour the one written like it."""
    best = [1] * len(ranked)
    before: list[int | None] = [None] * len(ranked)
    for i, (mark, _) in enumerate(ranked):
        for j in range(i):
            other = ranked[j][0]
            if other.order >= mark.order:
                continue
            length = best[j] + 1
            chosen = before[i]
            better = length > best[i] or (
                length == best[i]
                and chosen is not None
                and other.form == mark.form
                and ranked[chosen][0].form != mark.form
            )
            if better:
                best[i], before[i] = length, j
    if not ranked:
        return []
    end: int | None = max(range(len(ranked)), key=lambda i: (best[i], i))
    run = []
    while end is not None:
        run.append(ranked[end])
        end = before[end]
    return run[::-1]


def _roman(text: str) -> int:
    total = 0
    for digit, following in zip(text, [*text[1:], ""], strict=True):
        value = _ROMANS[digit]
        total += -value if following and _ROMANS[following] > value else value
    return total


def _to_roman(value: int) -> str:
    digits = []
    for weight, symbol in _ROMANS_BY_VALUE:
        count, value = divmod(value, weight)
        digits.append(symbol * count)
    return "".join(digits) or str(value)
