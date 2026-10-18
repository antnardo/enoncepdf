"""What is not the text of the subject: headers, footers, line numbers.

No crop may keep them. They are found over the whole document rather than page by
page, because a footer is defined by its **repetition**: « – Page 3/12 – »,
« Page 2/6 » and its timestamp, a bare number, the name of the competition at the top.
Three rules:

- a line in the top or bottom band of the page (12 % of its height) whose text, digits
  aside, comes back at the same place on several pages — three at least when it is a
  bare number, which a figure's graduation can mimic on two;
- a line of those bands that reads « Page 3/12 » or « 3/12 », even in a one-page
  document (a bare number is not enough: a heading number at the top of a page, a
  graduation);
- a column of small numbers alone in the left or right margin: the line numbers some
  competitions print every five lines.

A rule or a logo repeated at the top, which is not text, is caught the same way on the
ink mask: a band of ink in the top or bottom band, at the same height on half the pages
at least.

The **body** of a page is what remains between header and footer. Its width is that of
the whole document, so that the crops of one statement all have the same width, hence
the same scale once stacked.
"""

import re
import statistics
from collections import defaultdict

import numpy as np

from enoncepdf.document import PdfDocument
from enoncepdf.models import Block, BlockKind, Box, Line, Margin, MarginKind

__all__ = ["LayoutAnalysis"]

_BAND = 0.12  # share of the page height where headers and footers are looked for
# « Page 3/12 », « – 3/12 – »: unambiguous even alone. A bare number is not — a heading
# number at the top of a page, a graduation — and only counts when it repeats.
_PAGE_NUMBER = re.compile(r"^[-–—\s]*(page\s*#+(\s*/\s*#+)?|#+\s*/\s*#+)[-–—\s]*$", re.IGNORECASE)
_BARE_NUMBER = re.compile(r"^\d{1,4}$")
_Y_TOLERANCE = 6  # bp: the same height from one page to the next
_MARGIN_PADDING = 1.5  # bp around a margin element, to erase all its ink


def _signature(text: str) -> str:
    return re.sub(r"\d+", "#", " ".join(text.lower().split()))


class LayoutAnalysis:
    """Finds the margins of a document and derives the body of each page."""

    def __init__(self, document: PdfDocument) -> None:
        self.document = document
        self._margins: list[Margin] | None = None
        self._text_span: tuple[float, float] | None = None

    # -- Margins ------------------------------------------------------------------------------

    def margins(self, page: int | None = None) -> list[Margin]:
        """The margins of one page, or of the whole document."""
        if self._margins is None:
            self._margins = self._find_margins()
        if page is None:
            return self._margins
        return [m for m in self._margins if m.page == page]

    def _find_margins(self) -> list[Margin]:
        doc = self.document
        numbers = self._line_numbers()
        excluded = {(m.page, m.box) for m in numbers}
        candidates: list[tuple[Line, MarginKind]] = []
        for page in range(1, doc.page_count + 1):
            _, height = doc.size(page)
            for line in doc.lines(page):
                if (page, line.box) in excluded:
                    continue
                if line.box.y1 <= height * _BAND:
                    candidates.append((line, MarginKind.HEADER))
                elif line.box.y0 >= height * (1 - _BAND):
                    candidates.append((line, MarginKind.FOOTER))

        # a signature that comes back at the same height on several pages
        occurrences: dict[tuple[MarginKind, str], list[Line]] = defaultdict(list)
        for line, kind in candidates:
            occurrences[kind, _signature(line.text)].append(line)
        threshold = 2 if doc.page_count <= 4 else max(2, round(0.3 * doc.page_count))
        margins = list(numbers)
        for line, kind in candidates:
            signature = _signature(line.text)
            same = [
                other
                for other in occurrences[kind, signature]
                if abs(other.box.y0 - line.box.y0) <= _Y_TOLERANCE
            ]
            needed = max(threshold, 3) if signature == "#" else threshold
            repeated = len({other.page for other in same}) >= needed
            if repeated or _PAGE_NUMBER.match(signature):
                margins.append(Margin(line.page, line.box, kind, line.text))

        margins += self._repeated_rules(margins)
        return margins

    def _line_numbers(self) -> list[Margin]:
        """Small numbers alone, left or right of the column of text."""
        doc = self.document
        every = [line for p in range(1, doc.page_count + 1) for line in doc.lines(p)]
        long = [line for line in every if len(line.text) > 40]
        if not long:
            return []
        left = statistics.median(line.box.x0 for line in long)
        right = statistics.median(line.box.x1 for line in long)
        size = statistics.median(line.size for line in long)
        found = [
            line
            for line in every
            if _BARE_NUMBER.match(line.text)
            and line.size < size
            and (line.box.x1 <= left - 3 or line.box.x0 >= right + 3)
        ]
        if len(found) < 3:
            return []
        return [Margin(line.page, line.box, MarginKind.LINE_NUMBER, line.text) for line in found]

    def _repeated_rules(self, known: list[Margin]) -> list[Margin]:
        """Bands of ink without text, at the top or bottom, repeated from page to page."""
        doc = self.document
        bands: list[tuple[int, int, int, MarginKind]] = []
        for page in range(1, doc.page_count + 1):
            _, height = doc.size(page)
            mask = doc.ink(page).copy()
            for line in doc.lines(page):
                b = line.box
                mask[int(b.y0) : int(np.ceil(b.y1)) + 1, int(b.x0) : int(np.ceil(b.x1)) + 1] = 0
            for y0, y1 in _bands(np.asarray(mask.any(axis=1)), gap=3):
                if y1 <= height * _BAND:
                    bands.append((page, y0, y1, MarginKind.HEADER))
                elif y0 >= height * (1 - _BAND):
                    bands.append((page, y0, y1, MarginKind.FOOTER))
        if doc.page_count < 3:
            return []
        rules = []
        for page, y0, y1, kind in bands:
            pages = {p for p, top, _, k in bands if k == kind and abs(top - y0) <= 3}
            if len(pages) >= doc.page_count / 2:
                width, _ = doc.size(page)
                rules.append(Margin(page, Box(0, y0, width, y1 + 1), kind, ""))
        return rules

    # -- Body ---------------------------------------------------------------------------------

    def body(self, page: int) -> Box:
        """The area of the page between header and footer, across the document's text width."""
        _, height = self.document.size(page)
        top, bottom = 0.0, height
        for m in self.margins(page):
            if m.kind is MarginKind.HEADER:
                top = max(top, m.box.y1 + 1)
            elif m.kind is MarginKind.FOOTER:
                bottom = min(bottom, m.box.y0 - 1)
        x0, x1 = self.text_span()
        return Box(x0, top, x1, bottom)

    def text_span(self) -> tuple[float, float]:
        """The leftmost and rightmost abscissae of the body's ink, over the whole document."""
        if self._text_span is None:
            lefts, rights = [], []
            for page in range(1, self.document.page_count + 1):
                columns = np.where(self.body_ink(page, vertical_only=True).any(axis=0))[0]
                if columns.size:
                    lefts.append(columns[0])
                    rights.append(columns[-1] + 1)
            width, _ = self.document.size(1)
            self._text_span = (float(min(lefts)), float(max(rights))) if lefts else (0.0, width)
        return self._text_span

    def body_ink(self, page: int, vertical_only: bool = False) -> np.ndarray:
        """The ink mask of the page, margins erased and everything outside the body blank;
        ``vertical_only`` keeps the full width."""
        mask = self.document.ink(page).copy()
        for m in self.margins(page):
            b = m.box
            mask[
                max(int(b.y0 - _MARGIN_PADDING), 0) : int(np.ceil(b.y1 + _MARGIN_PADDING)),
                max(int(b.x0 - _MARGIN_PADDING), 0) : int(np.ceil(b.x1 + _MARGIN_PADDING)),
            ] = 0
        _, height = self.document.size(page)
        top, bottom = 0, int(height)
        for m in self.margins(page):
            if m.kind is MarginKind.HEADER:
                top = max(top, int(np.ceil(m.box.y1 + 1)))
            elif m.kind is MarginKind.FOOTER:
                bottom = min(bottom, int(m.box.y0 - 1))
        mask[:top] = 0
        mask[bottom:] = 0
        if not vertical_only:
            x0, x1 = self.text_span()
            mask[:, : int(x0)] = 0
            mask[:, int(np.ceil(x1)) :] = 0
        return mask

    # -- Blocks -------------------------------------------------------------------------------

    def blocks(self, page: int, gap: int = 6) -> list[Block]:
        """The bands of ink of the page, separated by at least ``gap`` bp of white."""
        ink = self.document.ink(page)
        lines = self.document.lines(page)
        margins = self.margins(page)
        blocks = []
        for y0, y1 in _bands(np.asarray(ink.any(axis=1)), gap):
            columns = np.where(ink[y0 : y1 + 1].any(axis=0))[0]
            box = Box(float(columns[0]), float(y0), float(columns[-1] + 1), float(y1 + 1))
            inside = [line for line in lines if line.box.y1 > box.y0 and line.box.y0 < box.y1]
            text = inside[0].text if inside else ""
            if any(m.box.y1 > box.y0 and m.box.y0 < box.y1 for m in margins) and all(
                any(m.box == line.box for m in margins) for line in inside
            ):
                kind = BlockKind.MARGIN
            elif not inside:
                kind = BlockKind.FIGURE
            elif sum(line.box.height for line in inside) < 0.5 * box.height and box.height > 25:
                kind = BlockKind.FIGURE_TEXT
            else:
                kind = BlockKind.TEXT
            blocks.append(Block(page, box, kind, text))
        return blocks


def _bands(inked_rows: np.ndarray, gap: int) -> list[tuple[int, int]]:
    """Intervals ``[y0, y1]`` of inked rows separated by at least ``gap`` blank rows."""
    ys = np.where(inked_rows)[0]
    if ys.size == 0:
        return []
    bands, start, previous = [], int(ys[0]), int(ys[0])
    for y in ys[1:]:
        if y - previous > gap:
            bands.append((start, previous))
            start = int(y)
        previous = int(y)
    bands.append((start, previous))
    return bands
