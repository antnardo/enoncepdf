"""The numbering profile of a statement: the shape of its part and question numbers.

Numbers are reduced to **patterns** where each counter becomes a token — ``{1}`` Arabic,
``{R}`` upper-case Roman, ``{r}`` lower-case Roman, ``{A}`` upper-case letter, ``{a}``
lower-case letter — and the rest is kept as is: « II.A – » gives ``{R}.{A} -``, « Q 7. »
gives ``Q {1}.``. Comparing patterns rather than labels is what lets a statement be
matched against a house style, whatever its actual numbers.

Is a lone « I » a Roman numeral or a letter? The document decides: at a given position
of the number, if there is a « II » or a « IV » elsewhere, it is Roman.
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from enoncepdf.models import Heading, Question
from enoncepdf.structure import StructureAnalysis

__all__ = ["NumberingAnalysis", "NumberingProfile", "Restart", "pattern"]

_ROMAN = re.compile(r"^(?=[IVXLC])M{0,3}(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")
_TOKENS = re.compile(r"\d+|[A-Za-z]+|\s+|.")
_DASHES = str.maketrans({"–": "-", "—": "-", "o": "□", "❏": "□", "■": "□"})
_PRINTED_WORDS = ("Q", "Question", "Partie", "PARTIE", "Part")

Restart = Literal["none", "part", "subpart"]


def _counters(label: str) -> list[str]:
    """The alphanumeric tokens of a label, in order."""
    return [t for t in _TOKENS.findall(label) if t.isalnum()]


def pattern(label: str, romans: frozenset[int] = frozenset()) -> str:
    """The pattern of a label; ``romans``: ranks of the counters to read as Roman numerals."""
    tokens = _TOKENS.findall(label)
    out, rank = [], 0
    for i, token in enumerate(tokens):
        following = next((t for t in tokens[i + 1 :] if not t.isspace()), "")
        if token.isdigit():
            out.append("{1}")
            rank += 1
        elif token.isalpha():
            if token in _PRINTED_WORDS or (len(token) > 1 and not _ROMAN.match(token.upper())):
                out.append(token)  # a printed word: « Q », « Partie »
            elif token == "o" and following in "–—-":
                out.append("□")  # the Mines check box, an « o » in Dingbats
            else:
                roman = bool(_ROMAN.match(token.upper())) and (len(token) > 1 or rank in romans)
                if token.isupper():
                    out.append("{R}" if roman else "{A}")
                else:
                    out.append("{r}" if roman else "{a}")
                rank += 1
        elif token.isspace():
            out.append(" ")
        else:
            out.append(token.translate(_DASHES))
    return " ".join("".join(out).split())


@dataclass(frozen=True, slots=True)
class NumberingProfile:
    """The patterns of a statement's numbers, level by level; empty when a level is not
    numbered. ``restart`` says where questions start again at 1, and ``examples`` holds
    a few real labels, for display."""

    part: str
    subpart: str
    subsubpart: str
    question: str
    subquestion: str
    restart: Restart
    examples: tuple[str, ...]


class NumberingAnalysis:
    """Derives the numbering profile from a list of headings and questions.

    The lists are those of a whole document or of one part only: the physics part of a
    physics-and-engineering paper need not be numbered like the engineering part.
    """

    def __init__(self, headings: list[Heading], questions: list[Question]) -> None:
        self.headings = headings
        self.questions = questions

    @classmethod
    def from_structure(cls, structure: StructureAnalysis) -> "NumberingAnalysis":
        return cls(structure.headings(), structure.questions())

    def levels(self) -> list[int]:
        """The levels of the numbered headings, highest first: parts, subparts…

        A « Partie 1 » set above « 1.1 » headings does not count: those are what a house
        style numbers.
        """
        numbered = [h for h in self.headings if h.number]
        return sorted({h.level for h in numbered if h.level >= 1}) or sorted({h.level for h in numbered})

    def profile(self) -> NumberingProfile:
        headings = [h for h in self.headings if h.number]
        questions = self.questions
        by_level = [[h for h in headings if h.level == n] for n in self.levels()]
        patterns = [self._dominant([h.label for h in group]) for group in by_level]
        patterns += [""] * (3 - len(patterns))
        examples = [group[0].label for group in by_level[:3]]
        examples += [q.label for q in questions[:2]]
        return NumberingProfile(
            part=patterns[0],
            subpart=patterns[1],
            subsubpart=patterns[2],
            question=self._dominant([q.label for q in questions]),
            subquestion=self._dominant([s for q in questions for s in q.subquestions]),
            restart=self._restart(by_level, questions),
            examples=tuple(examples),
        )

    @staticmethod
    def _dominant(labels: list[str]) -> str:
        if not labels:
            return ""
        romans = frozenset(
            rank
            for label in labels
            for rank, token in enumerate(_counters(label))
            if len(token) > 1 and _ROMAN.match(token.upper())
        )
        return Counter(pattern(label, romans) for label in labels).most_common(1)[0][0]

    @staticmethod
    def _restart(by_level: list[list[Heading]], questions: list[Question]) -> Restart:
        """The heading level after which the question numbers start again at 1."""

        def restarts_after(group: list[Heading]) -> bool:
            for heading in group:
                here = (heading.page, heading.box.y0)
                before = [q for q in questions if (q.page, q.box.y0) < here]
                after = [q for q in questions if (q.page, q.box.y0) > here]
                if before and after and after[0].number == 1 and before[-1].number > 1:
                    return True
            return False

        if len(by_level) > 1 and restarts_after(by_level[1]):
            return "subpart"
        if by_level and restarts_after(by_level[0]):
            return "part"
        return "none"
