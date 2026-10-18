"""A statement compiled from crops: its questions, found and placed in its PDF.

An assignment is often not typed but pasted together from pages of past exam papers,
trimmed — ``\\includegraphics[page=2, trim=…, clip]{paper}``, the lines ``Crop.format``
writes. Its questions are in those papers, and that is where they are looked for:

- the source of the statement gives, in order, each included page — its file, its page,
  its trim, its scale — and the problem it falls in (``\\section``); latexdetok reads it
  and skips commented-out inclusions; ``\\includepdf`` includes whole pages;
- the file is found in the log of the compilation (``<./DS2/paper.pdf>`` in
  ``DS2.log``), which says where LaTeX took it among the folders of its
  ``\\graphicspath``;
- the text of the page is read there, in its visible part only: a trimmed PDF keeps all
  the text of the original page, and so does the compiled statement — searching there
  would also find the text the trim hides, twice when a page is included in two pieces;
- its place in the compiled statement comes from SyncTeX: the box of the image is
  recorded between the line of the inclusion and the end of its paragraph, where TeX
  breaks the lines; it is recognised by its proportions, those of the visible part, and
  by its width, that of the requested scale — a command that shrinks an image to fit
  the page measures it first at its natural size, a box recorded as well. The
  ``synctex`` tool refuses those records (« Ignored record »): the file, simple, is
  read here;
- the text LaTeX typesets itself — a typed question, a problem written by hand — is
  read in the PDF of the statement, outside the extent of the images, hidden part
  included;
- the questions are found as anywhere else (questions.py), problem by problem.

A page included as an image (a PNG, or a PDF without text) has nothing to read: its
questions are not found.

The commands read as inclusions are ``\\includegraphics`` and ``\\includepdf``; a
document that wraps them in a command of its own passes its name in ``commands``. Such a
command is read like ``\\includegraphics``: an optional argument with ``page``, ``trim``
and ``scale``, then the file. Reading the source takes latexdetok, hence Python 3.13 or
later; without it, ``CompiledStatement.questions()`` returns an empty list.

Coordinates are those of the package (models.py): bp, origin at the top left of the
page.
"""

import gzip
import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from enoncepdf.models import BP_PER_CM, Box, Line, LocatedQuestion
from enoncepdf.questions import marks, questions
from enoncepdf.reading import PdfiumDocument

__all__ = [
    "INCLUSION_COMMANDS",
    "CompiledStatement",
    "Inclusion",
    "StatementQuestion",
    "SyncTeXBox",
    "inclusions",
    "synctex_boxes",
]

#: The inclusion commands read by default; ``commands=`` adds a document's own.
INCLUSION_COMMANDS = ("includegraphics", "includepdf")
_SYNCTEX_SUFFIXES = (".synctex.gz", ".synctex")
# The lengths of graphicx, in bp: a trim without unit counts in bp.
_UNITS = {
    "cm": BP_PER_CM,
    "mm": BP_PER_CM / 10,
    "in": 72.0,
    "pt": 72 / 72.27,
    "pc": 12 * 72 / 72.27,
    "bp": 1.0,
    "": 1.0,
}
_LENGTH = re.compile(r"(-?\d*\.?\d+)\s*([a-z]*)")
_PT_PER_BP = 72.27 / 72  # SyncTeX counts in TeX points
_READ = re.compile(r"<(?:use )?([^<>,]+?\.(?:pdf|png|jpe?g))\b")
_RECORD = re.compile(r"[\[(hvxkg$](\d+),(\d+)(?:,-?\d+)?:(-?\d+),(-?\d+):(-?\d+),(-?\d+),(-?\d+)")
# A SyncTeX box is that of an image when its proportions are those of the visible part,
# within 15 %: enough for rounding, not enough to confuse two neighbouring pieces.
_PROPORTION_TOLERANCE = 0.15
_PARAGRAPH_REACH = 30  # source lines where to look for the box of an image, at most


@dataclass(frozen=True, slots=True)
class Inclusion:
    """A page of a paper included in the statement: its problem (the rank of its
    ``\\section``, 0 before the first), the line of the source, the file as written, its
    page, its trim — left, bottom, right, top, in bp, in the order of ``trim`` —, the
    last line where to look for its box, the end of its paragraph, and its scale, if
    it has one."""

    problem: int
    line: int
    file: str
    page: int = 1
    trim: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    end: int = 0
    scale: float | None = None


@dataclass(frozen=True, slots=True)
class SyncTeXBox:
    """A box SyncTeX recorded: its page and its edges, in TeX points from the top left
    corner of the page."""

    page: int
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class StatementQuestion:
    """A question of the compiled statement: its problem (the rank of its ``\\section``)
    and where it is — page and box in the statement's PDF —, with the top of its line as
    a fraction of the page height."""

    problem: int
    question: LocatedQuestion
    top: float


class CompiledStatement:
    """A compiled statement: its source, its PDF, its SyncTeX, the log of its compilation.

    The PDF, the SyncTeX and the log are found next to the source, under the same name,
    unless given; the included pages, from the log, otherwise in the folder named after
    the statement (``DS2/``), otherwise in the folder of the compilation.

    ``directory`` is that folder of the compilation, the source's by default: the source
    may be a copy, taken when the PDF was read, so that an edit made since without
    recompiling does not shift its lines from those of the SyncTeX — the original folder
    is what says where the inclusions are and which file the SyncTeX names.

    ``commands`` are the inclusion commands to read, without backslash: graphicx's and
    pdfpages' by default, plus any the document defines around them.
    """

    def __init__(
        self,
        tex: Path | str,
        pdf: Path | str | None = None,
        synctex: Path | str | None = None,
        log: Path | str | None = None,
        directory: Path | str | None = None,
        commands: Iterable[str] = INCLUSION_COMMANDS,
    ) -> None:
        self.tex = Path(tex)
        self.commands = tuple(commands)
        self.directory = Path(directory) if directory is not None else self.tex.parent
        self.pdf = Path(pdf) if pdf is not None else self.tex.with_suffix(".pdf")
        if synctex is not None:
            self.synctex: Path | None = Path(synctex)
        else:
            candidates = [self.pdf.with_name(self.pdf.stem + s) for s in _SYNCTEX_SUFFIXES]
            self.synctex = next((c for c in candidates if c.is_file()), None)
        self.log = Path(log) if log is not None else self.tex.with_suffix(".log")

    def inclusions(self) -> list[Inclusion]:
        return inclusions(self.tex.read_text(encoding="utf-8", errors="replace"), self.commands)

    def questions(self) -> list[StatementQuestion]:
        """The questions of the statement, problem by problem, where they fall in its PDF;
        nothing without source, PDF or SyncTeX, nor without latexdetok (Python 3.13+)."""
        if self.synctex is None or not self.synctex.is_file():
            return []
        if not self.tex.is_file() or not self.pdf.is_file():
            return []
        source = self.tex.read_text(encoding="utf-8", errors="replace")
        boxes = synctex_boxes(self.synctex, self.directory / self.tex.name)
        statement = PdfiumDocument(self.pdf)
        heights = [statement.size(page)[1] * _PT_PER_BP for page in range(1, statement.page_count + 1)]
        read = _read_files(self.log, self.directory)
        by_problem: dict[int, list[Line]] = {}
        extents: list[SyncTeXBox] = []  # each image whole, hidden part included
        previous: tuple[int, float] = (0, -math.inf)
        for inclusion in inclusions(source, self.commands):
            path = _find(inclusion.file, self.directory, self.tex.stem, read)
            if path is None or path.suffix.lower() != ".pdf":
                continue
            paper = PdfiumDocument(path)
            if not 1 <= inclusion.page <= paper.page_count:
                continue
            area = _visible(paper.size(inclusion.page), inclusion.trim)
            if area.width < 1 or area.height < 1:
                continue
            box = _image_box(inclusion, boxes, heights, area, previous)
            if box is None:
                continue
            previous = (box.page, box.bottom)
            extents.append(_extent(box, area, paper.media(inclusion.page)))
            lines = by_problem.setdefault(inclusion.problem, [])
            lines.extend(_place(line, area, box) for line in paper.lines(inclusion.page, area))
        for problem, line in self._typeset(source, boxes, statement, extents):
            by_problem.setdefault(problem, []).append(line)
        found = []
        for problem, lines in sorted(by_problem.items()):
            lines.sort(key=lambda line: (line.page, line.box.y0))
            for question in questions(marks(lines)):
                height = heights[question.page - 1] / _PT_PER_BP
                top = min(1.0, max(0.0, question.box.y0 / height))
                found.append(StatementQuestion(problem, question, top))
        return found

    @staticmethod
    def _typeset(
        source: str,
        boxes: dict[int, list[SyncTeXBox]],
        statement: PdfiumDocument,
        extents: list[SyncTeXBox],
    ) -> Iterator[tuple[int, Line]]:
        """The lines LaTeX typesets itself, outside the extent of the images, each with
        the problem of the last ``\\section`` before it."""
        starts = []
        for source_line in _sections(source):
            candidates = [
                box
                for number in (source_line, source_line + 1)
                for box in boxes.get(number, [])
                if box.height > 0 and 1 <= box.page <= statement.page_count
            ]
            if candidates:
                first = min(candidates, key=lambda box: (box.page, box.top))
                starts.append((first.page, first.top / _PT_PER_BP))
        if not starts:
            return
        for page in range(1, statement.page_count + 1):
            hidden = [e for e in extents if e.page == page]
            for line in statement.lines(page):
                if any(_covers(line.box, extent) for extent in hidden):
                    continue
                problem = sum(1 for start in starts if start <= (page, line.box.y0 + 1))
                if problem:
                    yield problem, line


def inclusions(source: str, commands: Iterable[str] = INCLUSION_COMMANDS) -> list[Inclusion]:
    """The pages a statement's source includes with ``commands``, in order; nothing
    without latexdetok.

    A ``\\section`` in the options of an ``\\includepdf`` (``pagecommand``) opens the
    problem of its pages.
    """
    lines = source.splitlines()
    problem = 0
    found: list[Inclusion] = []
    last_pages: list[int] = []  # the pages of the last inclusion
    last_end: tuple[int, int] = (0, 0)
    for start, end, command, nodes in _commands(source, tuple(commands)):
        if command.name == "section":
            if command.star:
                continue
            problem += 1
            if start < last_end:  # inside the options of the inclusion before
                for rank in last_pages:
                    found[rank] = replace(found[rank], problem=problem)
            continue
        option = next((str(n) for n in nodes[1:] if str(n).startswith("[")), "[]")
        argument = next((str(n) for n in nodes[1:] if str(n).startswith("{")), "")
        file = argument.strip()[1:-1].strip()
        if not file:
            continue
        options = _options(option)
        if command.name == "includepdf":
            pages = _pages(options.get("pages", "1"))
        else:
            requested = options.get("page", "1").strip("{} ")
            pages = [int(requested)] if requested.isdigit() and int(requested) >= 1 else [1]
        trim = _trim(options.get("trim", "").strip("{} ").split())
        scale = _number(options.get("scale", ""))
        paragraph = _paragraph_end(lines, start[0])
        last_pages = []
        for page in pages:
            last_pages.append(len(found))
            found.append(Inclusion(problem, start[0], file, page, trim, paragraph, scale))
        last_end = end
    return found


def synctex_boxes(path: Path | str, source: Path | str) -> dict[int, list[SyncTeXBox]]:
    """The boxes SyncTeX recorded for each line of the file ``source``."""
    path, source = Path(path), Path(source)
    opener: Any = gzip.open if path.name.endswith(".gz") else open
    tags: set[int] = set()
    unit, magnification = 1.0, 1.0
    page = 0
    boxes: dict[int, list[SyncTeXBox]] = {}
    with opener(path, "rt", encoding="utf-8", errors="replace") as stream:
        for raw in stream:
            line = raw.rstrip("\n")
            if line.startswith("Input:"):
                _, number, name = line.split(":", 2)
                if _same_file(name, source):
                    tags.add(int(number))
            elif line.startswith("Unit:"):
                unit = float(line[5:])
            elif line.startswith("Magnification:"):
                magnification = float(line[14:]) / 1000
            elif line.startswith("{"):
                page = int(line[1:]) if line[1:].isdigit() else page
            else:
                found = _RECORD.match(line)
                if found is None or int(found.group(1)) not in tags:
                    continue
                scale = unit * magnification / 65536
                h, v, width, height, depth = (int(found.group(i)) * scale for i in range(3, 8))
                boxes.setdefault(int(found.group(2)), []).append(
                    SyncTeXBox(page, h, v - height, h + width, v + depth)
                )
    return boxes


# -- internals ----------------------------------------------------------------------------


def _commands(
    source: str, images: tuple[str, ...] = ()
) -> list[tuple[tuple[int, int], tuple[int, int], Any, list[Any]]]:
    """The ``\\section`` commands and the image inclusions, in order: their start and end
    (line, column), the command and its arguments; latexdetok skips what is commented."""
    try:
        from latexdetok import TexCommand, TexFile
    except ImportError:
        return []
    tree = TexFile(source.splitlines(keepends=True)).analyse()
    found = tree.get_commands_arguments(["section", *images], nargs=1, nopt=1)
    commands = []
    for group in found.content:
        nodes = [node for node in group.content if str(node).strip()]
        if nodes and isinstance(nodes[0], TexCommand):
            end = group.end_position or group.start_position
            commands.append((tuple(group.start_position), tuple(end), nodes[0], nodes))
    return commands


def _sections(source: str) -> list[int]:
    """The lines where each problem starts: its unstarred ``\\section``."""
    return [
        start[0]
        for start, _end, command, _nodes in _commands(source)
        if command.name == "section" and not command.star
    ]


def _options(text: str) -> dict[str, str]:
    """The options of an inclusion: ``[page=2, trim=1cm 2cm 1cm 2cm, clip]``; a comma
    inside braces (``pagecommand={…}``) does not separate them. A repeated key keeps its
    last value, as graphicx does."""
    pieces: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text.strip().removeprefix("[").removesuffix("]"):
        if char == "," and depth == 0:
            pieces.append("".join(current))
            current = []
            continue
        depth += {"{": 1, "}": -1}.get(char, 0)
        current.append(char)
    pieces.append("".join(current))
    options = {}
    for piece in pieces:
        key, _, value = piece.partition("=")
        if key.strip():
            options[key.strip()] = value.strip()
    return options


def _pages(text: str) -> list[int]:
    """The pages of an ``\\includepdf``: « {1} », « 1,3 », « 2-4 »; nothing for « - »
    (all of them) or what cannot be read."""
    pages: list[int] = []
    for piece in text.strip("{} ").split(","):
        first, dash, last = piece.strip().partition("-")
        if first.isdigit() and not dash:
            pages.append(int(first))
        elif first.isdigit() and last.isdigit() and int(first) <= int(last):
            pages.extend(range(int(first), int(last) + 1))
        else:
            return []
    return [page for page in pages if page >= 1]


def _trim(values: list[str]) -> tuple[float, float, float, float]:
    """The graphicx trim in bp: left, bottom, right, top; zero if it cannot be read."""
    lengths = []
    for value in values:
        found = _LENGTH.fullmatch(value)
        if found is None or found.group(2) not in _UNITS:
            return (0.0, 0.0, 0.0, 0.0)
        lengths.append(float(found.group(1)) * _UNITS[found.group(2)])
    if len(lengths) != 4:
        return (0.0, 0.0, 0.0, 0.0)
    left, bottom, right, top = lengths
    return (left, bottom, right, top)


def _number(text: str) -> float | None:
    """A number option (``scale=.91``); None for what is not one, or is worth nothing."""
    try:
        value = float(text.strip("{} "))
    except ValueError:
        return None
    return value if value > 0 else None


def _paragraph_end(lines: list[str], line: int) -> int:
    """The last line where to look for the box of an image on line ``line``: the one
    after the first blank line, where its paragraph ends."""
    for number in range(line, min(len(lines), line + _PARAGRAPH_REACH) + 1):
        if not lines[number - 1].strip():
            return number + 1
    return line + _PARAGRAPH_REACH


def _same_file(recorded: str, source: Path) -> bool:
    """Does the name SyncTeX records name the source? An absolute path, or one relative
    to the folder of the compilation (``./DS2.tex``)."""
    path = Path(recorded)
    if path.is_absolute():
        try:
            return path.resolve() == source.resolve()
        except OSError:
            return path.name == source.name
    return path.name == source.name


def _read_files(log: Path, directory: Path) -> dict[str, Path]:
    """The images the compilation read, by name, with and without extension, from its
    log: ``<./DS2/paper.pdf>``."""
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    read: dict[str, Path] = {}
    for found in _READ.finditer(text):
        path = Path(found.group(1).strip())
        if not path.is_absolute():
            path = directory / path
        read.setdefault(path.name, path)
        read.setdefault(path.stem, path)
    return read


def _find(file: str, directory: Path, name: str, read: dict[str, Path]) -> Path | None:
    """The file of an inclusion: the one the compilation read, otherwise the one in the
    folder named after the statement, or in the folder of the source."""
    candidates = [read.get(file), read.get(Path(file).name)]
    for base in (directory / name, directory):
        candidates.extend([base / file, base / f"{file}.pdf"])
    return next((c for c in candidates if c is not None and c.is_file()), None)


def _visible(size: tuple[float, float], trim: tuple[float, float, float, float]) -> Box:
    """The visible part of a trimmed page, in the frame of the page."""
    width, height = size
    left, bottom, right, top = trim
    return Box(left, top, width - right, height - bottom)


def _image_box(
    inclusion: Inclusion,
    boxes: dict[int, list[SyncTeXBox]],
    heights: list[float],
    area: Box,
    previous: tuple[int, float],
) -> SyncTeXBox | None:
    """The box of the image in the statement: recorded between the line of the inclusion
    and the end of its paragraph, with the proportions of the visible part, the first
    after that of the previous inclusion (``previous``: its page and its bottom).

    It is no wider than the visible part at the requested scale — a command may shrink
    it further, to fit the page —, nor tiny, like a
    figure in a margin with the same proportions. A shrunk image leaves two boxes on the
    same baseline: its natural size and the printed one, the smaller.
    """
    proportions = area.width / area.height
    expected = area.width * _PT_PER_BP * (inclusion.scale or 1.0)
    widest = expected * 1.05 if inclusion.scale is not None else math.inf
    narrowest = expected * (0.5 if inclusion.scale is not None else 0.3)
    candidates = {
        box
        for number in range(inclusion.line, max(inclusion.end, inclusion.line + 1) + 1)
        for box in boxes.get(number, [])
        if box.height > 5
        and 1 <= box.page <= len(heights)
        and box.top >= -1
        and box.bottom <= heights[box.page - 1] + 1
        and (box.page, box.bottom) > previous
        and narrowest <= box.width <= widest
        and abs(math.log(box.width / box.height / proportions)) < _PROPORTION_TOLERANCE
    }
    return min(candidates, key=lambda box: (box.page, round(box.bottom), box.height), default=None)


def _place(line: Line, area: Box, box: SyncTeXBox) -> Line:
    """A line of the included page, carried into the statement, in place of the image."""
    scale_x = box.width / area.width / _PT_PER_BP
    scale_y = box.height / area.height / _PT_PER_BP
    x0 = box.left / _PT_PER_BP + (line.box.x0 - area.x0) * scale_x
    y0 = box.top / _PT_PER_BP + (line.box.y0 - area.y0) * scale_y
    placed = Box(x0, y0, x0 + line.box.width * scale_x, y0 + line.box.height * scale_y)
    return replace(line, page=box.page, box=placed)


def _extent(box: SyncTeXBox, area: Box, media: Box) -> SyncTeXBox:
    """The whole image in the statement, hidden part included — everything ``trim``
    removes, everything that overflows the CropBox of a crop: where its hidden text is
    too, which the reading of the statement's PDF must skip."""
    scale_x = box.width / area.width  # TeX pt per bp
    scale_y = box.height / area.height
    return SyncTeXBox(
        box.page,
        box.left + (media.x0 - area.x0) * scale_x,
        box.top + (media.y0 - area.y0) * scale_y,
        box.left + (media.x1 - area.x0) * scale_x,
        box.top + (media.y1 - area.y0) * scale_y,
    )


def _covers(box: Box, extent: SyncTeXBox) -> bool:
    """Does a line of the statement's PDF (in bp) fall within the extent of an image?"""
    center_x = box.center_x * _PT_PER_BP
    center_y = box.center_y * _PT_PER_BP
    return extent.left <= center_x <= extent.right and extent.top <= center_y <= extent.bottom
