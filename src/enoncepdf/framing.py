"""The frame of a document: the four margins its pages share.

A typeset paper has one text block, the same on every page: left, right and top
margins come back from page to page to the tenth of a millimetre, and are often round
numbers (2 cm, 2.5 cm, 5/8 in). The bottom does not: running text stops wherever the
next question or figure no longer fits. So:

- the left and right edges are **those most pages share** — the edges of the text
  column, which full lines reach page after page — and not a mean, which short lines
  would pull inwards, nor an extreme, which one figure wider than the text would pull
  outwards;
- the top and bottom are the outermost ink of the pages: a crop is tightened on the ink
  vertically anyway, so the frame only has to bound it, and must not make an exception
  of every page that ends early.

Then:

- each margin is **rounded** to the half-centimetre when the ink lies within 2 mm
  inside it, or one pixel outside (2.01 cm and 1.98 cm → 2 cm: the margin the author
  chose, measured to the pixel), otherwise to the millimetre with 1 mm of white. A
  rounding must cut nothing, and the 72 dpi mask the ink is measured on cannot tell a
  rule 0.4 bp outside a 2 cm margin from one 0.4 bp inside: a thin strip outside each
  edge is rendered at 576 dpi on every page that decides, and the half-centimetre is
  kept only if it cuts no ink there — on a tenth of them at most, two at most, which
  then get an exception;
- a page whose ink goes beyond the frame — a wide figure, an annex in another layout —
  gets an **exception** on the sides it overflows, and those only, at the millimetre
  outside its ink;
- a scanned document (no text on most pages) has no common frame: the sheet moves from
  page to page in the scanner, so every page gets its own frame.

The pages that decide are those with text whose ink covers a tenth of their height at
least, the first page left out when there are three or more: a title page has its own
layout, a page that is a picture (an annex scanned into a typeset paper) none.

A ``Framing`` is plain data — margins in cm — so that a caller can show it, let it be
edited, and pass it back to ``Statement.crop``.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import numpy as np

from enoncepdf.models import BP_PER_CM, Box, MarginKind

if TYPE_CHECKING:
    from enoncepdf.layout import LayoutAnalysis

__all__ = ["Frame", "Framing", "estimate_framing", "round_margin"]

SIDES = ("left", "top", "right", "bottom")
_SHARED = 3.0 / 10 * BP_PER_CM  # 3 mm: pages whose edge lies this close share it
_OVERFLOW = 1.0  # bp: ink beyond the frame by more than a pixel makes an exception
_STRIP = 1.5  # bp outside each edge of the frame, checked at a finer resolution
_FINE_DPI = 576
_PAD = 1.5  # bp around a margin element, as the ink mask erases it
_DARK = 200  # grey level below which a pixel of the fine rendering is ink
_PIXEL = 2.54 / 72  # cm: one pixel of the rendering the ink is measured on
_FULL = 0.1  # a page whose ink covers less than this share of its rows does not decide


def round_margin(margin: float) -> float:
    """A margin in cm, measured on the ink, rounded as it was meant: the half-centimetre
    when the ink starts at most 2 mm inside it — or one pixel of the 72 dpi rendering
    (0.35 mm) outside it, which is the precision of the measure: 1.98 and 2.01 are both
    2 cm —, otherwise the millimetre with 1 mm of white."""
    return _candidates(margin)[0]


def _candidates(margin: float) -> list[float]:
    """The roundings of a measured margin, the roundest first: the half-centimetre when it
    is close (see ``round_margin``), then the millimetre with 1 mm of white."""
    if margin <= 0:
        return [0.0]
    millimetre = max(math.floor((margin - 0.1) * 10 + 1e-9) / 10, 0.0)
    half = math.floor((margin + _PIXEL) * 2 + 1e-9) / 2
    return [half, millimetre] if margin - half <= 0.2 + 1e-9 and half != millimetre else [millimetre]


def _outside(box: Box, width: float, height: float) -> "Frame":
    """The frame at the millimetre outside ``box``."""
    margins = (box.x0, box.y0, width - box.x1, height - box.y1)
    return Frame(*(_floor_margin(m / BP_PER_CM) for m in margins))


def _floor_margin(margin: float) -> float:
    """The millimetre at or outside the ink, with half a millimetre of white: the margin of
    a page that overflows the frame, which must not cut what overflows."""
    return max(math.floor((margin - 0.05) * 10 + 1e-9) / 10, 0.0)


@dataclass(frozen=True, slots=True)
class Frame:
    """Four margins in cm, measured from the edges of the page: what is cut on each side.

    In an exception, ``None`` is a side that follows the common frame.
    """

    left: float | None = None
    top: float | None = None
    right: float | None = None
    bottom: float | None = None

    def over(self, common: "Frame") -> "Frame":
        """The frame with its ``None`` sides taken from ``common``."""
        return Frame(*(getattr(common, s) if getattr(self, s) is None else getattr(self, s) for s in SIDES))

    def box(self, width: float, height: float) -> Box:
        """The kept area of a page of this size, in bp."""
        left, top, right, bottom = (getattr(self, s) or 0.0 for s in SIDES)
        return Box(
            left * BP_PER_CM,
            top * BP_PER_CM,
            max(width - right * BP_PER_CM, left * BP_PER_CM),
            max(height - bottom * BP_PER_CM, top * BP_PER_CM),
        )

    def as_list(self) -> list[float | None]:
        return [getattr(self, s) for s in SIDES]

    @classmethod
    def of_list(cls, values: list[float | None] | tuple[float | None, ...]) -> "Frame":
        if len(values) != 4:
            raise ValueError("a frame has four margins: left, top, right, bottom")
        return cls(*(None if v is None else float(v) for v in values))


@dataclass(frozen=True)
class Framing:
    """The common frame of a document, and the pages that have their own.

    ``pages`` maps a page to an exception: a ``Frame`` whose ``None`` sides follow
    ``common``. ``scanned`` says that the document is a scan, every page framed alone.
    """

    common: Frame
    pages: Mapping[int, Frame] = field(default_factory=dict)
    scanned: bool = False

    def frame(self, page: int) -> Frame:
        """The frame applied to ``page``, every side given."""
        own = self.pages.get(page)
        return own.over(self.common) if own else self.common

    def with_common(self, common: Frame) -> "Framing":
        return replace(self, common=common)

    def as_dict(self) -> dict[str, object]:
        """Plain data, for JSON: ``{"common": [l, t, r, b], "pages": {"3": [l, t, r, b]}}``."""
        return {
            "common": self.common.as_list(),
            "pages": {str(p): f.as_list() for p, f in sorted(self.pages.items())},
            "scanned": self.scanned,
        }

    @classmethod
    def of_dict(cls, data: Mapping[str, object]) -> "Framing":
        """The inverse of ``as_dict``; raises ``ValueError`` on what it cannot read."""
        common = Frame.of_list(data["common"])  # type: ignore[arg-type]
        if any(v is None or v < 0 for v in common.as_list()):  # type: ignore[operator]
            raise ValueError("the common frame needs four margins, none negative")
        pages = {int(p): Frame.of_list(v) for p, v in dict(data.get("pages") or {}).items()}  # type: ignore[call-overload]
        return cls(common, pages, bool(data.get("scanned", False)))


def _shared_edge(margins: list[float]) -> float:
    """The margin most pages share: the one with the most others within 3 mm inside it,
    the outermost of equals. It is the edge of the text column, which full lines reach
    page after page, whatever a few figures wider than the text, or a document réponse
    framed to the edge of the sheet, do."""

    def support(m: float) -> int:
        return sum(0 <= w - m <= _SHARED for w in margins)

    return min(margins, key=lambda m: (-support(m), m))


def estimate_framing(layout: "LayoutAnalysis") -> Framing:
    """The frame the pages of the document share, and its exceptions."""
    doc = layout.document
    boxes: dict[int, tuple[Box, float]] = {}
    for page in range(1, doc.page_count + 1):
        mask = layout.free_ink(page)
        rows = np.where(mask.any(axis=1))[0]
        if rows.size == 0:
            continue
        columns = np.where(mask.any(axis=0))[0]
        box = Box(float(columns[0]), float(rows[0]), float(columns[-1] + 1), float(rows[-1] + 1))
        boxes[page] = (box, rows.size / mask.shape[0])

    if not boxes:
        return Framing(Frame(0.0, 0.0, 0.0, 0.0))

    with_text = {p for p in range(1, doc.page_count + 1) if doc.lines(p)}
    scanned = len(with_text) < doc.page_count / 2
    deciding = [
        p
        for p, (_, share) in boxes.items()
        if share >= _FULL and (scanned or p in with_text) and not (p == 1 and doc.page_count >= 3)
    ]
    deciding = deciding or list(boxes)

    def margins(page: int) -> tuple[float, float, float, float]:
        box, _ = boxes[page]
        width, height = doc.size(page)
        return box.x0, box.y0, width - box.x1, height - box.y1

    measured = [margins(p) for p in deciding]
    # left and right: the text column. Top and bottom only bound the crops, which are
    # tightened on the ink: the outermost ink of the deciding pages, so that none of them
    # is an exception for a short page or a figure low on the page.
    left = _shared_edge([m[0] for m in measured])
    right = _shared_edge([m[2] for m in measured])
    # a page wider than the column — a document réponse framed to the edge — has its own
    # layout, and does not say where the text block starts or stops
    inside = [m for m in measured if m[0] >= left - _OVERFLOW and m[2] >= right - _OVERFLOW] or measured
    top = min(m[1] for m in inside)
    bottom = min(m[3] for m in inside)
    # the roundest margin that cuts no ink of the pages that decide, but for a tenth of them
    # (two at most) that become exceptions; the fine check settles what the mask cannot
    tolerated = min(2, len(deciding) // 10)
    chosen = {}
    measures = {"left": left, "right": right, "top": top, "bottom": bottom}  # the column first
    for side, measure in measures.items():
        options = _candidates(measure / BP_PER_CM)
        chosen[side] = options[-1]
        index = SIDES.index(side)
        for option in options:
            trial = Frame(**{s: chosen.get(s, 0.0) for s in SIDES} | {side: option})
            # a page the mask already shows overflowing is an exception anyway
            within = [p for p in deciding if margins(p)[index] >= option * BP_PER_CM - _OVERFLOW]
            cut = sum(side in _spills(layout, p, trial, (side,)) for p in within)
            if cut <= tolerated:
                chosen[side] = option
                break
    common = Frame(**chosen)

    if scanned:
        own = {p: _outside(boxes[p][0], *doc.size(p)) for p in boxes}
        return Framing(common, own, scanned=True)

    exceptions: dict[int, Frame] = {}
    for page in boxes:
        sides = {}
        for side, measure, limit in zip(SIDES, margins(page), common.as_list(), strict=True):
            if measure < (limit or 0.0) * BP_PER_CM - _OVERFLOW:
                sides[side] = _floor_margin(measure / BP_PER_CM)
        sides |= {s: v for s, v in _spills(layout, page, common).items() if s not in sides}
        if sides:
            exceptions[page] = Frame(**sides)
    return Framing(common, exceptions)


def _spills(
    layout: "LayoutAnalysis", page: int, frame: Frame, sides: tuple[str, ...] = SIDES
) -> dict[str, float]:
    """The sides where ink lies just outside ``frame``, closer than the 72 dpi mask can
    tell — a table's top rule 0.4 bp above a 2 cm margin —, seen on a strip rendered at
    576 dpi; each with the margin that keeps it."""
    doc = layout.document
    width, height = doc.size(page)
    kept = frame.box(width, height)
    top, bottom = 0.0, height
    for m in layout.margins(page):
        if m.kind is MarginKind.HEADER:
            top = max(top, m.box.y1 + 1)
        elif m.kind is MarginKind.FOOTER:
            bottom = min(bottom, m.box.y0 - 1)
    y0, y1 = max(kept.y0, top), min(kept.y1, bottom)
    if y1 - y0 < 2:
        return {}
    # the strip stops a fine pixel short of the edge: ink set exactly on it is inside
    near = 72 / _FINE_DPI
    strips = {
        "left": Box(kept.x0 - _STRIP, y0, kept.x0 - near, y1),
        "right": Box(kept.x1 + near, y0, kept.x1 + _STRIP, y1),
        "top": Box(kept.x0, kept.y0 - _STRIP, kept.x1, kept.y0 - near) if kept.y0 - _STRIP > top else None,
        "bottom": (
            Box(kept.x0, kept.y1 + near, kept.x1, kept.y1 + _STRIP) if kept.y1 + _STRIP < bottom else None
        ),
    }
    found = {}
    for side, strip in strips.items():
        if side not in sides or strip is None:
            continue
        if strip.x0 < 0 or strip.y0 < 0 or strip.x1 > width or strip.y1 > height:
            continue
        dark = np.asarray(doc.image(page, _FINE_DPI, strip).convert("L")) < _DARK
        scale = _FINE_DPI / 72
        for m in layout.margins(page):  # line numbers, headers: not text of the subject
            b = m.box
            dark[
                max(int((b.y0 - _PAD - strip.y0) * scale), 0) : max(int((b.y1 + _PAD - strip.y0) * scale), 0),
                max(int((b.x0 - _PAD - strip.x0) * scale), 0) : max(int((b.x1 + _PAD - strip.x0) * scale), 0),
            ] = False
        if not dark.any():
            continue
        if side == "left":
            edge = strip.x0 + np.where(dark.any(axis=0))[0][0] / scale
        elif side == "right":
            edge = width - (strip.x0 + (np.where(dark.any(axis=0))[0][-1] + 1) / scale)
        elif side == "top":
            edge = strip.y0 + np.where(dark.any(axis=1))[0][0] / scale
        else:
            edge = height - (strip.y0 + (np.where(dark.any(axis=1))[0][-1] + 1) / scale)
        found[side] = _floor_margin(edge / BP_PER_CM)
    return found
