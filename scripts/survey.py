"""Run enoncepdf over a set of real PDFs and dump what it finds, as JSON.

Real exam papers are under copyright and never ship with the tests: this script is how
a change to the reading or the analyses is measured on them. Run it on the same files
with two versions of the package, then compare the two dumps::

    uv run python scripts/survey.py files.txt before.json   # one PDF path per line
    git switch my-branch
    uv run python scripts/survey.py files.txt after.json
    uv run python scripts/survey.py --compare before.json after.json

The dump holds, per file: page count, headings, questions, margins, the crops of the
whole document and of each heading of level 1 or less, the crop of questions 1 to 3,
the numbering profile and the blocks of page 1.
"""

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from enoncepdf import Box, Crop, SelectionError, Statement


def _box(box: Box) -> list[float]:
    return [round(box.x0, 1), round(box.y0, 1), round(box.x1, 1), round(box.y1, 1)]


def _crops(crops: list[Crop]) -> list[list[object]]:
    return [[c.page, _box(c.kept)] for c in crops]


def survey(path: str) -> tuple[str, dict[str, object]]:
    try:
        with Statement(path) as s:
            out: dict[str, object] = {"pages": s.document.page_count}
            out["headings"] = [[h.level, h.number, h.label, h.text, h.page, _box(h.box)] for h in s.headings]
            out["questions"] = [
                [q.number, q.label, q.page, _box(q.box), list(q.subquestions)] for q in s.questions
            ]
            out["margins"] = [[m.page, m.kind.value, m.text] for m in s.margins]
            out["all"] = _crops(s.crop())
            parts: dict[str, object] = {}
            for h in s.headings:
                if h.level <= 1:
                    try:
                        parts[f"{h.page}:{h.label}:{h.text[:30]}"] = _crops(s.crop(h))
                    except SelectionError as error:
                        parts[f"{h.page}:{h.label}:{h.text[:30]}"] = str(error)
            out["parts"] = parts
            if len(s.questions) >= 3:
                try:
                    out["q1-3"] = _crops(s.crop(questions=(1, 3)))
                except SelectionError as error:
                    out["q1-3"] = str(error)
            p = s.numbering()
            out["profile"] = [p.part, p.subpart, p.subsubpart, p.question, p.subquestion, p.restart]
            out["blocks1"] = [[b.kind.value, _box(b.box)] for b in s.blocks(1)]
            return path, out
    except Exception as error:  # a survey reports every failure and carries on
        return path, {"error": repr(error)}


def compare(before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]) -> None:
    changed: Counter[str] = Counter()
    for path, old in before.items():
        new = after.get(path, {})
        for key in old.keys() | new.keys():
            if old.get(key) != new.get(key):
                changed[key] += 1
    print(f"{len(before)} files; changed: {dict(changed) or 'nothing'}")
    for path, old in before.items():
        new = after.get(path, {})
        n_old, n_new = len(old.get("questions", [])), len(new.get("questions", []))  # type: ignore[arg-type]
        if n_old != n_new:
            print(f"  {Path(path).name}: {n_old} → {n_new} questions")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--compare", action="store_true", help="compare two dumps instead")
    parser.add_argument("first", type=Path, help="list of PDFs, or the first dump")
    parser.add_argument("second", type=Path, help="output dump, or the second dump")
    parser.add_argument("-j", "--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.compare:
        compare(json.loads(args.first.read_text()), json.loads(args.second.read_text()))
        return 0
    files = [line for line in args.first.read_text().splitlines() if line.strip()]
    with ProcessPoolExecutor(args.jobs) as pool:
        results = dict(pool.map(survey, files))
    args.second.write_text(json.dumps(results, ensure_ascii=False, indent=0))
    errors = sum("error" in r for r in results.values())
    print(f"{len(results)} files, {errors} errors", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
