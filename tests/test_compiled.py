"""A statement compiled from crops: its questions, found and placed.

The statement is made here in full: pages of a paper (reportlab), the source that
includes them, a « compiled » statement of four pages, its SyncTeX written by hand — the
box of each image, the line of each ``\\section`` — and the log that says where LaTeX
took the papers. Neither TeX nor the ``synctex`` tool is needed; latexdetok is (Python
3.13 or later).
"""

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from enoncepdf.compiled import CompiledStatement, inclusions, synctex_boxes

pytest.importorskip("latexdetok")

WIDTH, HEIGHT = A4
CM = 72 / 2.54
PT = 72.27 / 72  # TeX points per bp
SP = 65536
SOURCE = (
    "\\documentclass{book}\n"
    "\\begin{document}\n"
    "\\section{Premier problème}\n"
    "\\includetoolargegraphics[page=1, trim=0cm 3cm 0cm 2cm, clip, scale=0.9]{paper}\n"
    "% \\includetoolargegraphics[page=1]{other}\n"
    "\\includetoolargegraphics{crop}\n"
    "\n"
    "\\section{Second problème}\n"
    "4) Une question tapée par LaTeX.\n"
    "\\end{document}\n"
)
# The page of the paper, trimmed by trim: what it prints, at the height of its baseline.
PAPER = [
    (800, "9) Une question cachée par le rognage du haut."),
    (700, "I. Mécanique"),
    (650, "1) Calculer la vitesse du point."),
    (600, "Q3 désigne la charge de l'armature."),
    (500, "2) En déduire l'énergie cinétique."),
    (400, "II. Électricité"),
    (350, "1) Exprimer la tension aux bornes."),
    (50, "5) Une question cachée par le rognage du bas."),
]
# The crop, trimmed by its CropBox: the rest of part II, and text outside the box.
CROPBOX = (50, 300, 545, 700)
CROP = [
    (650, "2) Déterminer le courant."),
    (500, "3) En déduire la puissance."),
    (200, "8) Une question hors de la découpe."),
]
PAPER_TOP = 100.0  # the top of each image in its page of the statement, in TeX points
SECTIONS_TOP = 60.0


def paper_height():
    return HEIGHT - 3 * CM - 2 * CM


def draw_paper(path: Path, lines, cropbox=None) -> None:
    sheet = Canvas(str(path), pagesize=A4)
    if cropbox is not None:
        sheet.setCropBox(cropbox)
    sheet.setFont("Helvetica", 11)
    for y, text in lines:
        sheet.drawString(72, y, text)
    sheet.showPage()
    sheet.save()


def record(line: int, top: float, width: float, height: float, left: float = 0):
    """A SyncTeX box: line of the source, top, width and height in TeX points."""
    return (
        f"({1},{line}:{round(left * SP)},{round((top + height) * SP)}:"
        f"{round(width * SP)},{round(height * SP)},0"
    )


def write_statement(directory: Path, name: str = "DS9") -> CompiledStatement:
    """The statement ``name`` in ``directory``: source, PDF, SyncTeX, log, and its papers
    in the folder named after it."""
    (directory / name).mkdir(parents=True, exist_ok=True)
    draw_paper(directory / name / "paper.pdf", PAPER)
    draw_paper(directory / name / "crop.pdf", CROP, cropbox=CROPBOX)
    tex = directory / f"{name}.tex"
    tex.write_text(SOURCE, encoding="utf-8")
    # The first image, shrunk to 0.9, on page 2; the crop at its size, on page 3, its box
    # recorded one line lower, as TeX sometimes does; the second problem, typed, on page 4.
    width1, height1 = WIDTH * 0.9 * PT, paper_height() * 0.9 * PT
    width2 = (CROPBOX[2] - CROPBOX[0]) * PT
    height2 = (CROPBOX[3] - CROPBOX[1]) * PT
    statement = Canvas(str(directory / f"{name}.pdf"), pagesize=A4)
    statement.showPage()  # the cover page
    statement.showPage()
    statement.setFont("Helvetica", 11)
    # The hidden text of the crop, below its box: the compiled PDF keeps it too.
    hidden_y = (PAPER_TOP + (CROPBOX[3] - 208) * PT) / PT
    statement.drawString(72, HEIGHT - hidden_y, "8) Une question hors de la découpe.")
    statement.showPage()
    statement.setFont("Helvetica", 11)
    statement.drawString(72, HEIGHT - 100, "4) Une question tapée par LaTeX.")
    statement.showPage()
    statement.save()
    records = [
        "{1",
        "}1",
        "{2",
        record(3, SECTIONS_TOP, 400, 14),
        record(4, PAPER_TOP, width1, height1),
        "}2",
        "{3",
        record(7, PAPER_TOP, width2, height2),
        "}3",
        "{4",
        record(8, SECTIONS_TOP, 400, 14),
        "}4",
    ]
    (directory / f"{name}.synctex").write_text(
        "SyncTeX Version:1\n"
        f"Input:1:{tex}\n"
        "Output:pdf\nMagnification:1000\nUnit:1\nX Offset:0\nY Offset:0\nContent:\n"
        + "\n".join(records)
        + "\nPostamble:\n",
        encoding="utf-8",
    )
    (directory / f"{name}.log").write_text(
        f"<./{name}/paper.pdf, id=1, 597.5pt x 845.0pt>\n<use ./{name}/paper.pdf>\n",
        encoding="utf-8",
    )
    return CompiledStatement(tex)


@pytest.fixture
def statement(tmp_path):
    return write_statement(tmp_path)


def test_visible_and_typed_questions_problem_by_problem(statement):
    found = statement.questions()
    assert [(q.problem, q.question.part, q.question.ref, q.question.page) for q in found] == [
        (1, "I", "1", 2),
        (1, "I", "2", 2),
        (1, "II", "1", 2),
        (1, "II", "2", 3),
        (1, "II", "3", 3),
        (2, None, "4", 4),
    ]
    order = [(q.question.page, q.top) for q in found]
    assert order == sorted(order)


def test_a_question_falls_on_its_line(statement):
    """« 1) Calculer »: its baseline at 650 bp in the paper, 2 cm below the visible top."""
    first = statement.questions()[0]
    line_top = HEIGHT - 2 * CM - 650 - 8  # the top of the characters, from the visible top
    expected = (PAPER_TOP / PT + line_top * 0.9) / HEIGHT
    assert first.top == pytest.approx(expected, abs=0.01)
    assert first.question.box.x0 == pytest.approx(72 * 0.9, abs=2)


def test_a_copied_source_reads_with_its_original_directory(statement, tmp_path):
    """The source and the SyncTeX copied elsewhere, as when a caller freezes them at the
    moment it renders the pages: the original folder says where the papers are."""
    copies = tmp_path / "copies"
    copies.mkdir()
    for path in (statement.tex, statement.synctex, statement.log):
        (copies / path.name).write_bytes(path.read_bytes())
    copy = CompiledStatement(
        copies / statement.tex.name,
        statement.pdf,
        copies / statement.synctex.name,
        copies / statement.log.name,
        directory=statement.tex.parent,
    )
    assert copy.questions() == statement.questions()


def test_without_synctex_no_question(statement):
    statement.synctex.unlink()
    assert CompiledStatement(statement.tex).questions() == []


class TestSource:
    def test_commented_inclusion_skipped_and_trim_in_bp(self):
        first, second = inclusions(SOURCE)
        assert (first.problem, first.line, first.file, first.page) == (1, 4, "paper", 1)
        assert first.trim == pytest.approx((0, 3 * CM, 0, 2 * CM))
        assert (first.scale, first.end) == (0.9, 8)
        assert (second.line, second.file, second.scale) == (6, "crop", None)

    def test_includepdf_opens_the_problem_of_its_options(self):
        source = (
            "\\begin{document}\n"
            "\\includepdf[pages={2-3},pagecommand={\\section{Amortisseurs}},trim=0 0 0 0]{p.pdf}\n"
            "\\section{Deep Impact}\n"
            "\\includegraphics[page=4]{q}\n"
            "\\end{document}\n"
        )
        found = [(i.problem, i.file, i.page) for i in inclusions(source)]
        assert found == [(1, "p.pdf", 2), (1, "p.pdf", 3), (2, "q", 4)]


def test_synctex_read_by_line(tmp_path):
    tex = tmp_path / "e.tex"
    path = tmp_path / "e.synctex"
    path.write_text(
        "SyncTeX Version:1\nInput:1:./e.tex\nInput:2:/other/class.cls\nUnit:1\n"
        f"{{2\n{record(5, 100, 200, 50, left=10)}\n"
        f"{record(5, 0, 1, 1).replace('(1,', '(2,')}\n}}2\n",
        encoding="utf-8",
    )
    [box] = synctex_boxes(path, tex)[5]
    assert (box.page, box.left, box.top, box.width, box.height) == pytest.approx(
        (2, 10, 100, 200, 50), abs=1e-3
    )
