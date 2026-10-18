"""A PDF read for cropping: lines of text with their style, and the ink mask of each page.

Both are needed. Text alone misses a vector figure, an image or a rule; the image
alone does not say what is a heading. The analyses cross the two, so both live in the
same frame: bp from the top left of the visible page, one pixel per bp at 72 dpi.

Lines are glued back **by baseline**: a printed line is cut into fragments wherever
the font changes — the number of a heading and its text, the pieces of a formula — and
« 1 » and « Le piège électrique » must become « 1 Le piège électrique ». Not when the
sizes differ too much, though: a line number at size 6, set on the baseline of a text
at size 11, must stay apart to be recognised as a margin.

pdfium reads every character the content stream draws, some of which nobody sees.
What a reader of the page does not see is dropped, as PyMuPDF did:

- a character whose box falls outside the visible page (an imposed sheet keeps the
  footer of its neighbour there);
- a fragment with no ink under any of its characters — clipped away, or white on
  white. The test is per fragment, not per character: some PDFs declare widths that
  drift from the glyphs drawn, and the box of a last digit can miss its own ink;
- the second copy of a character drawn twice at the same place, a fake bold by
  overprinting — but not the two « f » that pdfium makes of a « ﬀ » ligature, which
  share one box;
- a fragment made only of combining marks, such as the arrows over vectors, which
  pdfium sets on a baseline of their own.

Each line's text is assembled character by character, in reading order: a spacing
accent that old TeX fonts draw after its letter is put back before it, a space goes
wherever the gap between two characters exceeds 1.2 bp — pdfium's own generated
spaces land after such an accent and would split the word — and rotated text keeps the
order it was drawn in.

Measured against the PyMuPDF reader this replaces, on 185 real exam statements
(scripts/survey.py): the same questions everywhere but on three statements, which gain
some; headings gained on 31 statements, lost on 8 (figure captions and stray numbers
the old reader took for headings); crops within 1 bp on 144 statements.
"""

import ctypes
import math
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

import numpy as np
import pypdfium2
import pypdfium2.raw as pdfium_c
from PIL import Image

from enoncepdf._pdfium import CharReader
from enoncepdf.models import Box, Line
from enoncepdf.text import readable_text

__all__ = ["PdfDocument"]

_BASELINE_TOLERANCE = 1.5  # bp: two fragments on the same baseline, give or take this
_SPACE = 1.2  # bp: a gap wider than this between two characters is a space
_SIZE_RATIO = 0.7  # two sizes further apart than this do not make one line
_SAME_RUN = 0.5  # bp: how far the baseline of one fragment may wander
_ASCENT, _DESCENT = 1.25, 0.6  # bounds of a character box around its baseline, in sizes
_INK_WHITE = 250  # a pixel lighter than this is no ink, for the visibility test
_ACCENTS = frozenset("´`ˆ¨˜¸˚˘ˇ˙")
_LIGATURE_LETTERS = frozenset("filt")
_ANGLE = 0.01  # radians: a character turned by more than this is rotated text


@dataclass
class _Fragment:
    """A run of characters with one font, one size, one direction and one baseline."""

    baseline: float
    size: float
    bold: bool
    italic: bool
    angle: float
    origin_x: float
    font: str
    chars: list[tuple[Box, str]] = field(default_factory=list)
    inked: bool = False

    @property
    def rotated(self) -> bool:
        return _ANGLE < self.angle < 2 * math.pi - _ANGLE

    @property
    def box(self) -> Box:
        return _union(box for box, _ in self.chars)


class PdfDocument:
    """An open PDF, read page by page on demand and cached.

    It holds the file open until ``close()`` — or the end of a ``with`` block — and is
    not safe to share between threads.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._pdf = pypdfium2.PdfDocument(self.path)
        self._lines: dict[int, list[Line]] = {}
        self._ink: dict[tuple[int, int], np.ndarray] = {}
        self._sizes: dict[int, tuple[float, float]] = {}

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._pdf.close()

    @property
    def page_count(self) -> int:
        return len(self._pdf)

    def size(self, page: int) -> tuple[float, float]:
        """Width and height of the visible page, in bp."""
        if page not in self._sizes:
            sheet = self._pdf[page - 1]
            try:
                width, height = sheet.get_size()
            finally:
                sheet.close()
            self._sizes[page] = (float(width), float(height))
        return self._sizes[page]

    def lines(self, page: int) -> list[Line]:
        """The visual lines of the page, top to bottom, then left to right."""
        if page not in self._lines:
            self._lines[page] = self._read_lines(page)
        return self._lines[page]

    def ink(self, page: int, white: int = 245) -> np.ndarray:
        """Boolean mask ``[y, x]`` of the pixels darker than ``white``, at 72 dpi."""
        key = (page, white)
        if key not in self._ink:
            sheet = self._pdf[page - 1]
            try:
                grey = sheet.render(scale=1, grayscale=True).to_numpy()
            finally:
                sheet.close()
            self._ink[key] = grey.reshape(grey.shape[0], grey.shape[1]) < white
        return self._ink[key]

    def image(self, page: int, dpi: int = 72, area: Box | None = None) -> Image.Image:
        """An RGB rendering of a page, or of an area of it."""
        width, height = self.size(page)
        crop = (area.x0, height - area.y1, width - area.x1, area.y0) if area else (0, 0, 0, 0)
        sheet = self._pdf[page - 1]
        try:
            return sheet.render(scale=dpi / 72, crop=crop).to_pil().convert("RGB")
        finally:
            sheet.close()

    # -- Reading ------------------------------------------------------------------------------

    def _fragments(self, page: int) -> list[_Fragment]:
        sheet = self._pdf[page - 1]
        textpage = sheet.get_textpage()
        try:
            left, bottom, right, top = sheet.get_bbox()
            return _fragments(textpage.raw, left, top, right - left, top - bottom, self.ink(page, _INK_WHITE))
        finally:
            textpage.close()
            sheet.close()

    def _read_lines(self, page: int) -> list[Line]:
        fragments = [
            f
            for f in self._fragments(page)
            if f.inked and any(unicodedata.category(c) not in ("Mn", "Me") for _, c in f.chars)
        ]
        fragments.sort(key=lambda f: (round(f.baseline, 1), f.box.x0))

        groups: list[list[_Fragment]] = []
        for fragment in fragments:
            for group in groups:
                sizes = sorted((group[0].size, fragment.size))
                if (
                    group[0].rotated == fragment.rotated
                    and abs(group[0].baseline - fragment.baseline) <= _BASELINE_TOLERANCE
                    and sizes[0] >= _SIZE_RATIO * sizes[1]
                ):
                    group.append(fragment)
                    break
            else:
                groups.append([fragment])

        lines = []
        for group in groups:
            group.sort(key=lambda f: f.box.x0)
            first = group[0]
            lines.append(
                Line(
                    page=page,
                    box=_union(f.box for f in group),
                    text=readable_text(_surrogates(_text(group))),
                    size=round(first.size, 1),
                    bold=first.bold,
                    italic=first.italic,
                    all_bold=all(f.bold for f in group),
                )
            )
        lines.sort(key=lambda line: (line.box.y0, line.box.x0))
        return lines


def _fragments(
    raw: ctypes.c_void_p, left: float, top: float, width: float, height: float, ink: np.ndarray
) -> list[_Fragment]:
    """The page's characters, cut into fragments, with what nobody sees left out."""
    reader = CharReader(raw)
    fragments: list[_Fragment] = []
    current: _Fragment | None = None
    loose = pdfium_c.FS_RECTF()
    ox, oy = ctypes.c_double(), ctypes.c_double()
    tight = [ctypes.c_double() for _ in range(4)]
    seen: set[tuple[str, int, int]] = set()
    previous: tuple[str, Box] | None = None
    for index in range(pdfium_c.FPDFText_CountChars(raw)):
        code = pdfium_c.FPDFText_GetUnicode(raw, index)
        # pdfium marks a hyphenation hyphen as 0x02
        char = "-" if code == 2 else chr(code) if code > 2 else ""
        if not char or char.isspace():
            if char in ("\n", "\r", ""):
                current = None
            continue
        size = reader.size(index)
        font = reader.font(index)
        pdfium_c.FPDFText_GetCharOrigin(raw, index, ctypes.byref(ox), ctypes.byref(oy))
        pdfium_c.FPDFText_GetLooseCharBox(raw, index, ctypes.byref(loose))
        angle = pdfium_c.FPDFText_GetCharAngle(raw, index)
        rotated = _ANGLE < angle < 2 * math.pi - _ANGLE
        baseline = top - oy.value
        origin_x = ox.value - left
        box = Box(loose.left - left, top - loose.top, loose.right - left, top - loose.bottom)
        if not rotated:
            # the loose box follows the font's ascent and descent, absurd in some math
            # fonts: one such character would make its line 60 bp tall
            box = Box(
                box.x0,
                max(box.y0, baseline - _ASCENT * size),
                box.x1,
                min(box.y1, baseline + _DESCENT * size),
            )
        if not (0 <= box.center_x <= width and 0 <= box.center_y <= height):
            continue
        key = (char, round(box.x0), round(baseline))
        ligature = previous == (char, box) and char in _LIGATURE_LETTERS
        if not ligature and any(
            (char, key[1] + i, key[2] + j) in seen for i in (-1, 0, 1) for j in (-1, 0, 1)
        ):
            continue
        seen.add(key)
        previous = (char, box)
        if (
            current is None
            or current.font != font
            or abs(current.size - size) > 0.05
            or abs(current.angle - angle) > _ANGLE
            or (not rotated and abs(current.baseline - baseline) > _SAME_RUN)
            or (rotated and abs(current.origin_x - origin_x) > _SAME_RUN)
        ):
            bold, italic = reader.style(index, font)
            current = _Fragment(baseline, size, bold, italic, angle, origin_x, font)
            fragments.append(current)
        current.chars.append((box, char))
        if not current.inked:
            pdfium_c.FPDFText_GetCharBox(raw, index, *(ctypes.byref(v) for v in tight))
            x0, x1, y0, y1 = (v.value for v in tight)  # left, right, bottom, top
            current.inked = _has_ink(ink, x0 - left, top - y1, x1 - left, top - y0)
    return fragments


def _has_ink(ink: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> bool:
    """Is there ink in this box, half a pixel around? A box with no area counts as inked."""
    i0, i1 = max(int(x0 - 0.5), 0), max(math.ceil(x1 + 0.5), 0)
    j0, j1 = max(int(y0 - 0.5), 0), max(math.ceil(y1 + 0.5), 0)
    if i1 <= i0 or j1 <= j0:
        return True
    return bool(ink[j0:j1, i0:i1].any())


def _text(group: list[_Fragment]) -> str:
    """The text of a line, its characters in reading order."""
    if group[0].rotated:
        return " ".join("".join(c for _, c in f.chars) for f in group)
    chars = [c for f in group for c in f.chars]
    letters = sorted((c for c in chars if c[1] not in _ACCENTS), key=lambda c: c[0].center_x)
    accents: dict[int, list[str]] = {}
    for box, accent in (c for c in chars if c[1] in _ACCENTS):
        if letters:
            nearest = min(range(len(letters)), key=lambda i: abs(letters[i][0].center_x - box.center_x))
            accents.setdefault(nearest, []).append(accent)
    text, end = "", None
    for rank, (box, char) in enumerate(letters):
        if end is not None and box.x0 - end > _SPACE:
            text += " "
        text += "".join(accents.get(rank, ())) + char
        end = box.x1 if end is None else max(end, box.x1)
    return " ".join(text.split())


def _union(boxes: Iterable[Box]) -> Box:
    iterator = iter(boxes)
    box = next(iterator)
    for other in iterator:
        box = box.union(other)
    return box


def _surrogates(text: str) -> str:
    """pdfium hands UTF-16 over one unit at a time: surrogate pairs are glued back."""
    return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
