"""Headings and questions of a statement, found on its text and its typography.

Text alone is ambiguous: « 1 Le piège électrique » is a heading, « 1. On considère… »
a question, « 1. Il s'effectue par diffusion… » a footnote. Typography settles it:

- a **heading** is all bold, or bold at a size larger than the running text;
  « Partie Physique », in italics and without a number, is one too, and so is the title
  of the subject, unnumbered but centred and short — except on a cover page, which
  lines up several of them;
- a **question** starts with its number (« 7. », « Q 7. », « Question 7 : »), at the size
  of the running text, and the numbers follow one another — which rules out footnotes,
  at a small size, and the numbered lists of instructions;
- a **sub-question** starts with a letter (« a - », « b) »), at the start of a line or
  just after the number of the question.

The **level** of a heading comes from the shape of its number, not from its size,
which varies from one competition to the next: the subject's title at level −1,
« Partie … » at level 0, then the numbers ranked by depth (« 2 » before « 2.1 ») and,
at equal depth, Roman before Arabic before letter. A statement in « I, I.A, I.A.1 » and
another in « 1, 1.1, 1.1.1 » thus get the same levels 1, 2, 3.

The words recognised are those of French exam statements (« Partie », « Question »),
the documents this package was written for, with « Part » as well.
"""

import re
import statistics
import unicodedata
from collections import Counter

from enoncepdf.layout import LayoutAnalysis
from enoncepdf.models import Heading, Line, Question

__all__ = ["StructureAnalysis", "normalize"]

_ROMAN = re.compile(r"^(?=[IVXLC])M{0,3}(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")
_COMPONENT = r"(?:\d+|[IVXLC]+|[A-Z])"
_HEADING_NUMBER = re.compile(
    rf"^(?P<number>{_COMPONENT}(?:\.{_COMPONENT})*)(?P<sep>\s*(?:[.):]|[-–—](?=\s))?)\s+(?P<text>\S.*)$"
)
_PART = re.compile(
    r"^(?P<word>partie|part)\s+(?:(?P<number>\d+(?:\.\d+)*|[IVXLC]+|[A-Z])\b(?P<sep>\s*[.:–—-]?))?\s*(?P<text>.*)$",
    re.IGNORECASE,
)
# « 7. », « Q 7. », « Question 7 : », and at Mines « □ – 7. » (the box is an « o » in Dingbats)
_QUESTION = re.compile(
    r"^(?P<label>(?:(?:[o□❏■]\s+)?[–—-]\s*)?"
    r"(?:(?:Q(?:uestion)?\s*(?P<n1>\d+)\s*[.:)–—-]?)|(?:(?P<n2>\d+)\s*[.)])))\s+(?P<text>.*)$"
)
_SUBQUESTION = re.compile(r"^(?P<label>\(?[a-h]\s*[).]|[a-h]\s*[-–—](?=\s))\s*")


def normalize(text: str) -> str:
    """Lower case, without accents, repeated spaces or final punctuation — for comparing.

    Old TeX fonts extract the accent apart (« pi`ege ´electrique ») and ligatures as one
    character (« ﬂexion »): NFKD undoes the latter, the former are removed.
    """
    # before NFKD, which would make « ´ » a space followed by a combining accent
    without_lone = text.translate({ord(c): None for c in "`´¨ˆ˜¸^"} | {ord("’"): "'"})
    without_accents = "".join(
        c for c in unicodedata.normalize("NFKD", without_lone) if unicodedata.category(c) != "Mn"
    )
    return " ".join(without_accents.lower().split()).strip(" .:;–—-")


class StructureAnalysis:
    """Finds the headings and the questions of a document."""

    def __init__(self, layout: LayoutAnalysis) -> None:
        self.layout = layout
        self.document = layout.document
        self._headings: list[Heading] | None = None
        self._questions: list[Question] | None = None

    def headings(self) -> list[Heading]:
        if self._headings is None:
            self._analyse()
        return self._headings or []

    def questions(self) -> list[Question]:
        if self._questions is None:
            self._analyse()
        return self._questions or []

    # -- Analysis -----------------------------------------------------------------------------

    def _body_lines(self) -> list[Line]:
        lines = []
        for page in range(1, self.document.page_count + 1):
            margins = {m.box for m in self.layout.margins(page)}
            body = self.layout.body(page)
            lines += [
                line
                for line in self.document.lines(page)
                if line.box not in margins and body.y0 <= line.box.center_y <= body.y1
            ]
        return lines

    def _analyse(self) -> None:
        lines = self._body_lines()
        long = [line for line in lines if len(line.text) > 30] or lines
        size = statistics.median(line.size for line in long) if long else 10.0

        candidates: list[tuple[Line, str, str, str, str]] = []  # line, kind, number, label, text
        questions: list[Question] = []
        previous = 0
        for line in lines:
            heading = self._as_heading(line, size)
            if heading:
                candidates.append((line, *heading))
                continue
            question = self._as_question(line, size, previous)
            if question:
                questions.append(question)
                previous = question.number
                continue
            sub = _SUBQUESTION.match(line.text)
            if sub and questions and line.size >= size - 1:
                last = questions[-1]
                questions[-1] = Question(
                    last.number,
                    last.label,
                    last.page,
                    last.box,
                    (*last.subquestions, sub.group("label").strip()),
                )

        self._headings = self._level(candidates)
        self._questions = questions

    def _as_heading(self, line: Line, size: float) -> tuple[str, str, str, str] | None:
        text = line.text
        if len(text) > 120:
            return None
        part = _PART.match(text)
        if part and (line.bold or line.italic or line.size > size + 0.5):
            number = part.group("number") or ""
            label = text[: part.start("text")].strip()
            return ("part", number, label, part.group("text").strip())
        heading_style = line.all_bold or (line.bold and line.size >= size + 1)
        if not heading_style or (_QUESTION.match(text) and not line.size >= size + 1):
            return None
        m = _HEADING_NUMBER.match(text)
        if not m:
            # the title of the subject: unnumbered, all bold, centred and short — a justified
            # line of running text is centred too, but full width
            x0, x1 = self.layout.text_span()
            centred = abs(line.box.center_x - (x0 + x1) / 2) < 20
            if line.all_bold and centred and line.box.width < 0.8 * (x1 - x0):
                return ("title", "", "", text)
            return None
        number = m.group("number")
        if not all(_valid(c) for c in number.split(".")):
            return None
        label = (number + m.group("sep")).strip()
        return ("numbered", number, label, m.group("text").strip())

    def _as_question(self, line: Line, size: float, previous: int) -> Question | None:
        m = _QUESTION.match(line.text)
        if not m or line.size < size - 1:
            return None
        number = int(m.group("n1") or m.group("n2"))
        if number not in (previous + 1, 1):
            return None
        sub = _SUBQUESTION.match(m.group("text"))
        return Question(
            number,
            m.group("label").strip(),
            line.page,
            line.box,
            (sub.group("label").strip(),) if sub else (),
        )

    def _level(self, candidates: list[tuple[Line, str, str, str, str]]) -> list[Heading]:
        """The level of each heading, from the shape of its number."""
        shapes = Counter(_shape(number) for _, kind, number, _, _ in candidates if kind == "numbered")
        # a lone Roman « I », « V », « X »: letter or numeral? The document decides
        romans = any(len(c) > 1 and _ROMAN.match(c) for shape in shapes for c in shape)
        order = sorted(shapes, key=lambda s: (len(s), [_rank(c, romans) for c in s]))
        # a cover page lines up centred bold lines (competition, date, paper): they are not
        # titles of the subject
        per_page = Counter(line.page for line, kind, *_ in candidates if kind == "title")
        candidates = [c for c in candidates if not (c[1] == "title" and per_page[c[0].page] >= 3)]
        headings = []
        for line, kind, number, label, text in candidates:
            if kind == "title":
                level = -1
            elif kind == "part":
                level = number.count(".") if number and number[0].isdigit() else 0
            else:
                level = 1 + order.index(_shape(number))
            headings.append(Heading(level, number, label, text, line.page, line.box))
        return headings


def _valid(component: str) -> bool:
    return component.isdigit() or bool(_ROMAN.match(component)) or len(component) == 1


def _shape(number: str) -> tuple[str, ...]:
    """``II.A`` → ``("R", "A")``; ``2.1`` → ``("1", "1")``."""
    return tuple("1" if c.isdigit() else "R" if len(c) > 1 or c in "IVX" else "A" for c in number.split("."))


def _rank(component: str, romans: bool) -> int:
    return {"R": 0 if romans else 2, "1": 1, "A": 2}[component]
