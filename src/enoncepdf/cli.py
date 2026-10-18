"""Command line: ``enoncepdf <command> <pdf> …`` (or ``python -m enoncepdf``).

structure  subject.pdf                                headings, questions, margins found
crop       subject.pdf --part "Partie Physique" --without-heading
crop       subject.pdf --part 2.1 --within "Partie Physique"
crop       subject.pdf --part "NASA" --without-heading --intro    the introduction alone
crop       subject.pdf --questions 1-17 --sheet crops.png
trims      subject.pdf --questions Q1-10                 trim of each page, in cm
trims      subject.pdf --part II --json
blocks     subject.pdf 5 [--from 2 --to 5] [--gap 2]
sheet      subject.pdf [--pages 3-8] [-o sheet.png]
numbering  subject.pdf [--within "Partie Physique"]
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from enoncepdf.cropping import SelectionError
from enoncepdf.models import Crop
from enoncepdf.statement import Statement

__all__ = ["main", "parse_range"]

# « 1-10 », « Q1-10 », « Q1-Q10 », « p3 »: a range as one types it
_RANGE = re.compile(r"[qQpP]?\s*(\d+)(?:\s*-\s*[qQpP]?\s*(\d+))?")


def parse_range(text: str) -> tuple[int, int]:
    """« 1-10 », « Q1-Q10 », « p9 », « 12-4 » → ``(first, last)``, in increasing order."""
    found = _RANGE.fullmatch(text.strip())
    if found is None:
        raise argparse.ArgumentTypeError(f"unreadable range: « {text} » (e.g. 1-10, Q1-10)")
    first, last = int(found.group(1)), int(found.group(2) or found.group(1))
    return min(first, last), max(first, last)


def _selection_options(parser: argparse.ArgumentParser) -> None:
    """The ways of selecting an extract, shared by ``crop`` and ``trims``."""
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--part", help="a heading number or a piece of its text")
    parser.add_argument("--without-heading", action="store_true", help="leave the heading line out")
    parser.add_argument("--intro", action="store_true", help="only the text that opens the part")
    parser.add_argument("--within", help="enclosing part, to remove an ambiguity")
    parser.add_argument("--questions", type=parse_range, help="range, e.g. 1-17 or Q1-17")
    parser.add_argument("--pages", type=parse_range, help="range, e.g. 3-9")


def _crops(statement: Statement, args: argparse.Namespace) -> list[Crop]:
    return statement.crop(
        args.part,
        with_heading=not args.without_heading,
        intro=args.intro,
        within=args.within,
        questions=args.questions,
        pages=args.pages,
    )


def _structure(statement: Statement, _: argparse.Namespace) -> None:
    print(f"{statement.path.name} — {statement.document.page_count} pages")
    print("\nHeadings")
    for h in statement.headings:
        print(f"  {'  ' * max(h.level, 0)}L{h.level}  p.{h.page:<3} {h.label:<10} {h.text[:60]}")
    questions = statement.questions
    print(f"\nQuestions: {len(questions)}", end="")
    if questions:
        print(f" — from « {questions[0].label} » to « {questions[-1].label} »")
        for q in questions[1:]:
            if q.number == 1:
                print(f"  numbering restarts at 1 on page {q.page}")
    else:
        print()
    count: dict[str, int] = {}
    for m in statement.margins:
        count[m.kind.value] = count.get(m.kind.value, 0) + 1
    print("\nMargins left out: " + (", ".join(f"{n} × {k}" for k, n in count.items()) or "none"))


def _crop(statement: Statement, args: argparse.Namespace) -> None:
    crops = _crops(statement, args)
    print(statement.latex(crops))
    if args.sheet:
        statement.contact_sheet(crops).save(args.sheet)
        print(f"contact sheet: {args.sheet}", file=sys.stderr)


def _trims(statement: Statement, args: argparse.Namespace) -> None:
    """The trim of each page, without LaTeX: for whoever crops the PDF with another tool.

    The order is that of ``trim`` — left, bottom, right, top (LBRU) — in cm, measured
    from the edges of the page; headers, footers and line numbers are already outside
    the kept area.
    """
    crops = _crops(statement, args)
    if args.json:
        print(json.dumps([{"page": c.page, **dict(zip("LBRU", c.trim_cm, strict=True))} for c in crops]))
        return
    for c in crops:
        left, bottom, right, top = c.trim_cm
        print(f"page {c.page:<3} L={left:.2f}cm B={bottom:.2f}cm R={right:.2f}cm U={top:.2f}cm")


def _blocks(statement: Statement, args: argparse.Namespace) -> None:
    if args.first:
        print(statement.latex(statement.crop_blocks(args.page, args.first, args.last, args.gap)))
        return
    width, height = statement.document.size(args.page)
    blocks = statement.blocks(args.page, args.gap)
    print(f"{statement.path.name} p.{args.page} — {width:.0f}×{height:.0f} bp, {len(blocks)} blocks")
    for k, b in enumerate(blocks, 1):
        print(
            f"  {k:>2}  y {b.box.y0:>4.0f}–{b.box.y1:<4.0f}"
            f" x {b.box.x0:>3.0f}–{b.box.x1:<4.0f} {b.kind.value:<16} {b.text[:56]}"
        )


def _sheet(statement: Statement, args: argparse.Namespace) -> None:
    output = args.output or Path(tempfile.gettempdir()) / f"sheet-{statement.path.stem}.png"
    crops = statement.crop(pages=args.pages) if args.pages else None
    statement.contact_sheet(crops).save(output)
    print(output)


def _numbering(statement: Statement, args: argparse.Namespace) -> None:
    profile = statement.numbering(args.within)
    for name in ("part", "subpart", "subsubpart", "question", "subquestion", "restart"):
        print(f"  {name:<12} {getattr(profile, name) or '—'}")
    print(f"  {'examples':<12} {' · '.join(profile.examples)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="enoncepdf",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sub = commands.add_parser("structure", help="headings, questions and margins found")
    sub.add_argument("pdf", type=Path)

    sub = commands.add_parser("crop", help="\\includetoolargegraphics lines")
    _selection_options(sub)
    sub.add_argument("--sheet", type=Path, help="also write the contact sheet of the crops")

    sub = commands.add_parser("trims", help="trim of each cropped page: L B R U in cm")
    _selection_options(sub)
    sub.add_argument("--json", action="store_true", help="a list of {page, L, B, R, U}")

    sub = commands.add_parser("blocks", help="blocks of a page, and crops of blocks")
    sub.add_argument("pdf", type=Path)
    sub.add_argument("page", type=int)
    sub.add_argument("--from", dest="first", type=int, help="first block to crop")
    sub.add_argument("--to", dest="last", type=int, help="last block to crop")
    sub.add_argument(
        "--gap", type=int, default=6, help="white space between blocks, in bp; 2: one line per block"
    )

    sub = commands.add_parser("sheet", help="pages as thumbnails")
    sub.add_argument("pdf", type=Path)
    sub.add_argument("--pages", type=parse_range, help="range, e.g. 3-9: sheet of the cropped pages")
    sub.add_argument("-o", "--output", type=Path)

    sub = commands.add_parser("numbering", help="numbering patterns of the statement")
    sub.add_argument("pdf", type=Path)
    sub.add_argument("--within", help="restrict to one part")

    args = parser.parse_args(argv)
    actions = {
        "structure": _structure,
        "crop": _crop,
        "trims": _trims,
        "blocks": _blocks,
        "sheet": _sheet,
        "numbering": _numbering,
    }
    with Statement(args.pdf) as statement:
        try:
            actions[args.command](statement, args)
        except SelectionError as error:
            print(error, file=sys.stderr)
            return 1
    return 0
