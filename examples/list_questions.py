"""List the questions of any PDF, page by page, as their numbers open the lines.

    python examples/list_questions.py assignment.pdf

Works on any PDF with text — a subject, a model answer, a scanned copy with OCR —
because it reads only the text of the lines, not their typography, and opens the file
only for the time of each reading (safe behind a lock in a threaded server).
"""

import argparse
from pathlib import Path

from enoncepdf import PdfiumDocument, locate


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()

    document = PdfiumDocument(args.pdf)
    lines = [line for page in range(1, document.page_count + 1) for line in document.lines(page)]
    for question in locate(lines):
        part = f"part {question.part}, " if question.part else ""
        print(f"{part}question {question.ref:<8} p. {question.page:<3} {question.label}")


if __name__ == "__main__":
    main()
