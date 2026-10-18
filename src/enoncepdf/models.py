"""The data the modules exchange: boxes, lines, margins, headings, questions, crops.

Every coordinate is in **bp** (PostScript points, 1/72 in), with the origin at the top
left of the visible page and y pointing down — the frame of an image rendered at 72 dpi,
one pixel per bp, so that text and ink masks line up without conversion. Pages are
numbered **from 1**, like the ``page=`` option of ``\\includegraphics``.
"""

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "BP_PER_CM",
    "Block",
    "BlockKind",
    "Box",
    "Crop",
    "Heading",
    "Line",
    "LocatedQuestion",
    "Margin",
    "MarginKind",
    "Position",
    "Question",
]

BP_PER_CM = 72 / 2.54


@dataclass(frozen=True, slots=True)
class Box:
    """A rectangle on a page: left, top, right, bottom, in bp."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    def union(self, other: "Box") -> "Box":
        return Box(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )


@dataclass(frozen=True, slots=True)
class Line:
    """A visual line of text: its page, its box, its text as one reads it, the effective
    size of its first character in points, and its style — of the first character
    (``bold``, ``italic``) and of all of them (``all_bold``)."""

    page: int
    box: Box
    text: str
    size: float
    bold: bool
    italic: bool
    all_bold: bool


class MarginKind(StrEnum):
    HEADER = "header"
    FOOTER = "footer"
    LINE_NUMBER = "line number"


@dataclass(frozen=True, slots=True)
class Margin:
    """Something outside the running text, which no crop keeps: a header, a footer, a
    line number. ``text`` is empty for a repeated rule or logo, found on the ink alone."""

    page: int
    box: Box
    kind: MarginKind
    text: str


class BlockKind(StrEnum):
    TEXT = "text"
    FIGURE = "figure"
    FIGURE_TEXT = "figure and text"
    MARGIN = "margin"


@dataclass(frozen=True, slots=True)
class Block:
    """A horizontal band of ink, separated from its neighbours by white space; ``text``
    is the start of the first line it holds, empty for a figure."""

    page: int
    box: Box
    kind: BlockKind
    text: str


@dataclass(frozen=True, slots=True)
class Position:
    """A point in the flow of a document: a height on a page."""

    page: int
    y: float


@dataclass(frozen=True, slots=True)
class Heading:
    """A heading, numbered or not (« Partie Physique »).

    ``level`` is −1 for the title of the subject, 0 for the « Partie … » headings, then
    1, 2, 3 by the shape of the number; ``number`` is the bare number (``II``, ``2.1``,
    ``I.A``), ``label`` the number as printed (``II.``, ``I.A –``).
    """

    level: int
    number: str
    label: str
    text: str
    page: int
    box: Box


@dataclass(frozen=True, slots=True)
class Question:
    """A question found by the structure analysis: its number, its label as printed
    (« 1. », « Q 7. », « Question 3 : »), its line, and the labels of its
    sub-questions (« a - », « b) »)."""

    number: int
    label: str
    page: int
    box: Box
    subquestions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LocatedQuestion:
    """A question found at its number at the start of a line (``enoncepdf.questions``):
    its part — the Roman numeral of the part heading before it, None without one —,
    its reference (« 12 », « I.A.1 », « 1.a »), its label as printed (« Q 12. »,
    « 12 — »), its number, its page and the box of its line."""

    part: str | None
    ref: str
    label: str
    number: int
    page: int
    box: Box


@dataclass(frozen=True, slots=True)
class Crop:
    """A slice of a page to include, described by the box it keeps."""

    page: int
    kept: Box
    page_width: float
    page_height: float

    @property
    def raw_trim_cm(self) -> tuple[float, float, float, float]:
        """What to cut from each edge, in cm, unrounded: left, bottom, right, top — the
        order of ``trim`` for ``\\includegraphics``."""
        return (
            self.kept.x0 / BP_PER_CM,
            (self.page_height - self.kept.y1) / BP_PER_CM,
            (self.page_width - self.kept.x1) / BP_PER_CM,
            self.kept.y0 / BP_PER_CM,
        )

    @property
    def trim_cm(self) -> tuple[float, float, float, float]:
        """The trim as it is written: ``raw_trim_cm`` to the hundredth, never negative.
        The LaTeX line and ``enoncepdf trims`` both read it, so that they give the same
        numbers."""
        left, bottom, right, top = (round(max(v, 0.0), 2) for v in self.raw_trim_cm)
        return left, bottom, right, top

    @property
    def trim_option(self) -> str:
        """``trim=L B R U`` in cm, as graphicx reads it."""
        return "trim=" + " ".join(f"{v:.2f}cm" for v in self.trim_cm)

    def latex(self, file: str, text_height: float = 666.8) -> str:
        """The ``\\includetoolargegraphics`` line of the crop.

        ``\\includetoolargegraphics`` centres on the width but does not bound the height:
        a slice taller than the text height makes the pagination loop. The scale that
        makes it fit is then set, with a 3 % margin. ``text_height`` is in bp.
        """
        options = f"page={self.page}, {self.trim_option}, clip"
        if self.kept.height > text_height:
            scale = int(text_height / self.kept.height * 0.97 * 100) / 100
            options += f", scale={scale:.2f}"
        return f"\\includetoolargegraphics[{options}]{{{file}}}"
