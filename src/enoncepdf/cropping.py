"""Crops of a document: from one point of its flow to another, without header or footer.

Everything comes down to a single operation, ``between(start, end)``: on each page
crossed, keep the body between the two positions, then **tighten it on the ink** — a
slice that ends mid-page drags no white space along, an almost empty page gives
nothing. A part, a range of questions, whole pages or blocks are only ways of naming
the two positions.

The width kept is the same for all the crops of one call: the extent of the ink over
all the pages crossed. Stacked, the slices keep the same scale and the same alignment,
and a figure wider than the text is never cut.
"""

import numpy as np

from enoncepdf.layout import LayoutAnalysis
from enoncepdf.models import Box, Crop, Heading, Position
from enoncepdf.structure import StructureAnalysis, normalize

__all__ = ["Cropper", "SelectionError"]

Bounds = tuple[tuple[int, float], tuple[int, float] | None]


class SelectionError(ValueError):
    """A part or a question that cannot be found, or that the selection names ambiguously.
    The message lists what was found."""


class Cropper:
    """Turns « this part », « these questions », « these pages » into crops."""

    def __init__(self, layout: LayoutAnalysis, structure: StructureAnalysis, margin: float = 3.0) -> None:
        self.layout = layout
        self.structure = structure
        self.document = layout.document
        self.margin = margin

    # -- Ways of selecting ----------------------------------------------------------------------

    def part(
        self,
        selection: str | Heading,
        with_heading: bool = True,
        within: str | Heading | None = None,
        intro: bool = False,
    ) -> list[Crop]:
        """A part, up to the next heading of the same level or higher.

        ``selection`` is a heading already found, a number (« 2 », « II », « 2.1 »,
        « I.A ») or a piece of the heading (« Partie Physique », « Flexion »); ``within``
        restricts the search to an enclosing part, when a number comes back (the « 1 » of
        the engineering part and that of the physics part).

        ``intro`` keeps only the text that opens the part, up to the first heading that
        follows whatever its level: the introduction of a subject one takes a part of.
        """
        heading = selection if isinstance(selection, Heading) else self.find_heading(selection, within)
        start = (
            Position(heading.page, self._white_above(heading.page, heading.box.y0))
            if with_heading
            else Position(heading.page, self._white_below(heading.page, heading.box.y1))
        )
        return self.between(start, self._next(heading) if intro else self._end_of(heading))

    def questions(self, first: int, last: int, within: str | Heading | None = None) -> list[Crop]:
        """Questions ``first`` to ``last`` included, up to whatever follows the last one."""
        span_start, span_end = self.span(within)
        inside = [
            q
            for q in self.structure.questions()
            if span_start <= (q.page, q.box.y0) and (span_end is None or (q.page, q.box.y0) < span_end)
        ]
        by_number = {q.number: q for q in inside}
        if first not in by_number or last not in by_number:
            raise SelectionError(
                f"questions {first} to {last} not found"
                f" (found: {', '.join(str(q.number) for q in inside) or 'none'})"
            )
        q0, q1 = by_number[first], by_number[last]
        after = (q1.page, q1.box.y0)
        following = [(q.page, q.box.y0) for q in inside if (q.page, q.box.y0) > after] + [
            (h.page, h.box.y0) for h in self.structure.headings() if (h.page, h.box.y0) > after
        ]
        end = min(following, default=None)
        return self.between(
            Position(q0.page, self._white_above(q0.page, q0.box.y0)),
            Position(end[0], self._white_above(end[0], end[1])) if end else None,
        )

    def pages(self, first: int, last: int | None = None) -> list[Crop]:
        """The body of whole pages."""
        last = last or first
        end = Position(last + 1, 0) if last < self.document.page_count else None
        return self.between(Position(first, 0), end)

    def blocks(self, page: int, first: int, last: int | None = None, gap: int = 6) -> list[Crop]:
        """Blocks of a page, numbered from 1 as in ``LayoutAnalysis.blocks``."""
        found = self.layout.blocks(page, gap)
        last = last or first
        if not 1 <= first <= last <= len(found):
            raise SelectionError(f"blocks {first} to {last}: page {page} has {len(found)}")
        kept = found[first - 1 : last]
        return self.between(Position(page, kept[0].box.y0 - 0.5), Position(page, kept[-1].box.y1 + 0.5))

    # -- The one operation ----------------------------------------------------------------------

    def between(self, start: Position, end: Position | None) -> list[Crop]:
        """The content of the flow from ``start`` to ``end`` (the end of the document if
        None), one crop per page."""
        last = end.page if end else self.document.page_count
        slices: list[tuple[int, int, int, np.ndarray]] = []
        for page in range(start.page, min(last, self.document.page_count) + 1):
            body = self.layout.body(page)
            top = max(start.y if page == start.page else body.y0, body.y0)
            bottom = min(end.y if end and page == end.page else body.y1, body.y1)
            if bottom - top < 2:
                continue
            mask = self.layout.body_ink(page, vertical_only=True)
            i0, i1 = max(int(top), 0), int(np.ceil(bottom))
            rows = np.where(mask[i0:i1].any(axis=1))[0]
            if rows.size == 0:
                continue
            y0, y1 = i0 + int(rows[0]), i0 + int(rows[-1]) + 1
            columns = np.where(mask[y0:y1].any(axis=0))[0]
            slices.append((page, y0, y1, columns))

        if not slices:
            return []
        x0 = min(int(c[0]) for *_, c in slices)
        x1 = max(int(c[-1]) + 1 for *_, c in slices)
        crops = []
        for page, y0, y1, _ in slices:
            width, height = self.document.size(page)
            body = self.layout.body(page)
            # the margin never spills beyond the positions asked for: it would take back the
            # descender of the heading just left out, or the top of the next one
            top = start.y if page == start.page else body.y0
            bottom = end.y if end and page == end.page else body.y1
            kept = Box(
                max(x0 - self.margin, 0),
                max(y0 - self.margin, body.y0, top),
                min(x1 + self.margin, width),
                min(y1 + self.margin, body.y1, bottom),
            )
            crops.append(Crop(page, kept, width, height))
        return crops

    # -- Finding headings -----------------------------------------------------------------------

    def find_heading(self, selection: str, within: str | Heading | None = None) -> Heading:
        """The heading a number or a piece of text names; raises ``SelectionError``."""
        span_start, span_end = self.span(within)
        headings = [
            h
            for h in self.structure.headings()
            if span_start <= (h.page, h.box.y0) and (span_end is None or (h.page, h.box.y0) < span_end)
        ]
        wanted = normalize(selection)
        exact = [
            h
            for h in headings
            if h.number
            and wanted in {normalize(h.number), normalize(h.label), normalize(f"partie {h.number}")}
        ]
        # a heading quoted in full wins over those that contain it: « Flexion » names the
        # part « III. Flexion », not « Relation de dispersion des ondes de flexion »
        whole = [h for h in headings if wanted in {normalize(h.text), normalize(f"{h.label} {h.text}")}]
        textual = [
            h
            for h in headings
            if wanted in normalize(h.text) or normalize(f"{h.label} {h.text}").startswith(wanted)
        ]
        found = exact or whole or textual
        if not found:
            known = "; ".join(f"{h.label} {h.text[:40]}" for h in headings) or "no heading found"
            raise SelectionError(f"« {selection} » names no heading ({known})")
        if len(found) > 1:
            choices = "; ".join(f"p. {h.page}: {h.label} {h.text[:40]}" for h in found)
            raise SelectionError(
                f"« {selection} » names several headings ({choices}):"
                " be more precise, or restrict with within="
            )
        return found[0]

    def span(self, within: str | Heading | None) -> Bounds:
        """The bounds, in document order, of the part ``within`` (the whole document if None)."""
        if within is None:
            return (0, 0.0), None
        enclosing = within if isinstance(within, Heading) else self.find_heading(within)
        end = self._end_of(enclosing)
        return (enclosing.page, enclosing.box.y0), (end.page, end.y) if end else None

    def _end_of(self, heading: Heading) -> Position | None:
        headings = self.structure.headings()
        rank = headings.index(heading)
        for following in headings[rank + 1 :]:
            if following.level <= heading.level:
                return Position(following.page, self._white_above(following.page, following.box.y0))
        return None

    def _next(self, heading: Heading) -> Position | None:
        headings = self.structure.headings()
        rank = headings.index(heading)
        if rank + 1 == len(headings):
            return None
        following = headings[rank + 1]
        return Position(following.page, self._white_above(following.page, following.box.y0))

    # The box of a line of text comes from the font's metrics, not from the ink: a
    # descender (« y », « p ») goes below it, an accent above. The first blank row of
    # pixels beyond the edge, within a few bp, is used instead.

    def _white_below(self, page: int, y: float, reach: int = 8) -> float:
        mask = self.document.ink(page)
        for row in range(int(y), min(int(y) + reach, mask.shape[0])):
            if not mask[row].any():
                return float(row)
        return y

    def _white_above(self, page: int, y: float, reach: int = 8) -> float:
        mask = self.document.ink(page)
        for row in range(int(y), max(int(y) - reach, -1), -1):
            if 0 <= row < mask.shape[0] and not mask[row].any():
                return float(row)
        return y - 1
