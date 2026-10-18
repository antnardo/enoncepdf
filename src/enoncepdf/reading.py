"""The lines of a PDF as pdfium breaks them, for finding questions in any PDF.

``PdfiumDocument`` reads the same ``Line`` objects as ``PdfDocument``, in bp from the top
left of the visible page (its CropBox), pages from 1, text as one reads it (text.py),
but it is built for another use:

- its lines are those pdfium breaks itself, at its line feeds: to find a number at the
  start of a line, safer than fragments glued back by baseline, which the descender of
  a « g » or an index can shift from one line to the next;
- ``area`` keeps only the lines most of whose characters fall inside it: a cropped page
  — a crop, a page included with ``trim`` — keeps all the text of its original page,
  including what the crop hides;
- it holds nothing open. pdfium is not thread-safe: a caller with several threads (a
  web server) takes its own lock around each call. Each reading opens the document,
  reads it and closes it, and returns only values that owe nothing to pdfium.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pypdfium2

from enoncepdf._pdfium import CharReader
from enoncepdf.models import Box, Line
from enoncepdf.text import readable_text

__all__ = ["PdfiumDocument"]

_TOLERANCE = 1.0  # bp: a character on the edge of the area still falls inside


class PdfiumDocument:
    """A PDF read by pdfium: its pages, their visible size, their lines of text."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._visible: list[tuple[float, float, float, float]] = []
        self._media: list[tuple[float, float, float, float]] = []
        with self._open() as pdf:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    # get_bbox inherits the boxes from the page tree; get_cropbox does
                    # not, and falls back to US Letter for a page that inherits them.
                    visible = tuple(page.get_bbox())
                    media = page.get_mediabox(fallback_ok=False)
                    self._visible.append(visible)
                    self._media.append(tuple(media) if media else visible)
                finally:
                    page.close()

    @property
    def page_count(self) -> int:
        return len(self._visible)

    def size(self, page: int) -> tuple[float, float]:
        """Width and height of the visible page (its CropBox), in bp."""
        left, bottom, right, top = self._visible[page - 1]
        return right - left, top - bottom

    def media(self, page: int) -> Box:
        """The whole page (its MediaBox) in the frame of the visible page: what overflows
        the CropBox, hidden but still there — a crop trimmed by its CropBox keeps the rest
        of its original page."""
        left, _bottom, _right, top = self._visible[page - 1]
        m_left, m_bottom, m_right, m_top = self._media[page - 1]
        return Box(m_left - left, top - m_top, m_right - left, top - m_bottom)

    def lines(self, page: int, area: Box | None = None) -> list[Line]:
        """The lines of the page, top to bottom; with ``area``, those most of whose
        characters fall inside it."""
        left, _bottom, _right, top = self._visible[page - 1]
        with self._open() as pdf:
            sheet = pdf[page - 1]
            textpage = sheet.get_textpage()
            try:
                chars = _chars(textpage, left, top)
            finally:
                textpage.close()
                sheet.close()
        lines = []
        for group in _by_line(chars):
            visible = [c for c in group if c.char.strip()]
            if not visible:
                continue
            inside = visible if area is None else [c for c in visible if _inside(c.box, area)]
            if 2 * len(inside) < len(visible):
                continue
            box = visible[0].box
            for char in visible[1:]:
                box = box.union(char.box)
            first = visible[0]
            lines.append(
                Line(
                    page=page,
                    box=box,
                    text=readable_text(" ".join("".join(c.char for c in group).split())),
                    size=round(first.size, 1),
                    bold=first.bold,
                    italic=first.italic,
                    all_bold=all(c.bold for c in visible),
                )
            )
        lines.sort(key=lambda line: (line.box.y0, line.box.x0))
        return lines

    @contextmanager
    def _open(self) -> Iterator[pypdfium2.PdfDocument]:
        pdf = pypdfium2.PdfDocument(self.path)
        try:
            yield pdf
        finally:
            pdf.close()


class _Char:
    __slots__ = ("bold", "box", "char", "italic", "size")

    def __init__(self, box: Box, char: str, size: float, bold: bool, italic: bool) -> None:
        self.box = box
        self.char = char
        self.size = size
        self.bold = bold
        self.italic = italic


def _chars(textpage: pypdfium2.PdfTextPage, left: float, top: float) -> list[_Char]:
    """The characters of the page in pdfium's order, line feeds included, each with its
    box in the frame of the visible page, its effective size and its style."""
    reader = CharReader(textpage.raw)
    chars: list[_Char] = []
    for index in range(textpage.count_chars()):
        char = textpage.get_text_range(index, 1)
        x0, y0, x1, y1 = textpage.get_charbox(index)
        font = reader.font(index)
        bold, italic = reader.style(index, font)
        box = Box(x0 - left, top - y1, x1 - left, top - y0)
        chars.append(_Char(box, char, reader.size(index), bold, italic))
    return chars


def _by_line(chars: list[_Char]) -> Iterator[list[_Char]]:
    """The characters grouped at the line feeds pdfium placed."""
    group: list[_Char] = []
    for char in chars:
        if char.char == "\n":
            yield group
            group = []
        elif char.char != "\r":
            group.append(char)
    yield group


def _inside(box: Box, area: Box) -> bool:
    return (
        box.x0 >= area.x0 - _TOLERANCE
        and box.x1 <= area.x1 + _TOLERANCE
        and box.y0 >= area.y0 - _TOLERANCE
        and box.y1 <= area.y1 + _TOLERANCE
    )
