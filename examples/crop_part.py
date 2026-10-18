"""Crop one part of an exam statement and write what to include it with.

    python examples/crop_part.py subject.pdf "Partie Physique"
    python examples/crop_part.py subject.pdf II --questions 1-5

Prints the \\includetoolargegraphics lines, the trims in cm for any other tool, and
writes a contact sheet of the crops next to the PDF, to check them at a glance.
"""

import argparse
from pathlib import Path

from enoncepdf import SelectionError, Statement
from enoncepdf.cli import parse_range


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("part", help="a heading number or a piece of its text")
    parser.add_argument("--questions", type=parse_range, help="only these questions of the part, e.g. 1-5")
    args = parser.parse_args()

    with Statement(args.pdf) as statement:
        try:
            heading = statement.heading(args.part)
            if args.questions:
                crops = statement.crop(questions=args.questions, within=heading)
            else:
                crops = statement.crop(heading, with_heading=False)
        except SelectionError as error:
            raise SystemExit(str(error)) from error

        print(f"{heading.label} {heading.text} — level {heading.level}, page {heading.page}")
        print(statement.latex(crops))
        for crop in crops:
            left, bottom, right, top = crop.trim_cm
            print(f"page {crop.page}: L={left} B={bottom} R={right} U={top} (cm)")
        sheet = args.pdf.with_name(f"{args.pdf.stem}-crops.png")
        statement.contact_sheet(crops).save(sheet)
        print(f"contact sheet: {sheet}")


if __name__ == "__main__":
    main()
