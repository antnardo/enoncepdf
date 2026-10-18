"""Exam statements drawn with reportlab, in the styles of three French competitions.

Real papers are under copyright and never ship with the tests: these imitate what the
analyses rely on — fonts, sizes, positions, repeated headers and footers, line
numbers — with invented text. ``scripts/survey.py`` measures the package on real ones.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from enoncepdf import Statement

WIDTH, HEIGHT = A4
LEFT = 70.0  # left edge of the text column, in bp
BODY = "Times-Roman"
# Long enough to fill the column, as justified text does: the title is centred on it.
FILLER = (
    "On considère un dispositif de laboratoire dont on étudie avec soin le comportement en régime permanent.",
    "Les grandeurs utiles sont définies sur la figure ci-contre et rappelées dans le tableau des données.",
    "On néglige tout frottement ici et l'on suppose que le référentiel du laboratoire est galiléen.",
    "Cette partie peut être traitée indépendamment des autres, en s'aidant des résultats admis plus haut.",
)


class Writer:
    """Writes a statement line by line, top to bottom, in the top-left frame of the package."""

    def __init__(
        self,
        path: Path,
        footer: Callable[[int, int], list[tuple[float, str]]] | None = None,
        header: str | None = None,
        line_numbers: bool = False,
        pages: int = 1,
    ) -> None:
        self.canvas = Canvas(str(path), pagesize=A4)
        self.footer = footer
        self.header = header
        self.line_numbers = line_numbers
        self.page_total = pages
        self.page = 1
        self.y = 90.0
        self.count = 0

    def line(
        self, text: str, font: str = BODY, size: float = 10.0, x: float = LEFT, step: float = 14.0
    ) -> None:
        self.canvas.setFont(font, size)
        self.canvas.drawString(x, HEIGHT - self.y, text)
        self.count += 1
        if self.line_numbers and self.count % 5 == 0:
            self.canvas.setFont(BODY, 6)
            self.canvas.drawString(LEFT - 25, HEIGHT - self.y, str(self.count))
        self.y += step

    def centred(self, text: str, font: str, size: float) -> None:
        self.canvas.setFont(font, size)
        self.canvas.drawCentredString(WIDTH / 2, HEIGHT - self.y, text)
        self.y += 2 * size

    def filler(self, lines: int = 3) -> None:
        for k in range(lines):
            self.line(FILLER[k % len(FILLER)])

    def question(self, label: str, text: str = "Déterminer l'expression de la grandeur demandée.") -> None:
        self.line(f"{label} {text}")

    def heading(self, text: str, font: str = "Times-Bold", size: float = 12.0) -> None:
        self.y += 6
        self.line(text, font, size, step=20)

    def new_page(self) -> None:
        self._decorate()
        self.canvas.showPage()
        self.page += 1
        self.y = 90.0

    def save(self) -> None:
        self._decorate()
        self.canvas.showPage()
        self.canvas.save()

    def _decorate(self) -> None:
        if self.header and self.page > 1:
            self.canvas.setFont("Times-Italic", 9)
            self.canvas.drawString(LEFT, HEIGHT - 40, self.header)
        if self.footer:
            self.canvas.setFont(BODY, 9)
            for x, text in self.footer(self.page, self.page_total):
                self.canvas.drawString(x, HEIGHT - 815, text)


def draw_polytechnique(path: Path) -> None:
    """Two parts, « Partie Physique » then « Partie Sciences de l’Ingénieur », unnumbered and
    in italics; numbered headings « 1 », « 2.1 »; questions « 1. » with sub-questions
    « a - »; numbering restarts in the second part; line numbers every five lines; footer
    « – Page n/4 – »."""
    w = Writer(
        path, footer=lambda n, total: [(WIDTH / 2 - 30, f"– Page {n}/{total} –")], line_numbers=True, pages=4
    )
    w.centred("Le piège électrique et ses ondes", "Times-Bold", 16)
    w.filler(4)
    w.heading("Partie Physique", "Times-Italic", 14)
    w.heading("1 Le piège électrique")
    w.filler(3)
    w.question("1.", "Établir l'équation du mouvement de la particule.")
    w.line("a - Exprimer la force subie.")
    w.line("b - En déduire l'accélération.")
    w.filler(2)
    w.question("2.", "Déterminer la position d'équilibre.")
    w.filler(6)
    w.new_page()
    w.heading("2 Les ondes de compression")
    w.filler(2)
    w.heading("2.1 Relation de dispersion")
    w.filler(3)
    w.question("3.", "Établir la relation de dispersion.")
    w.filler(3)
    w.heading("2.2 Vitesse de groupe")
    w.filler(3)
    w.question("4.", "Calculer la vitesse de groupe.")
    w.filler(8)
    w.new_page()
    w.heading("Partie Sciences de l’Ingénieur", "Times-Italic", 14)
    w.heading("1 Le moteur")
    w.filler(3)
    w.question("1.", "Déterminer le couple moteur.")
    w.filler(3)
    w.heading("2 La commande")
    w.heading("2.1 Le correcteur")
    w.filler(3)
    w.question("2.", "Choisir le gain du correcteur.")
    w.filler(8)
    w.new_page()
    w.filler(5)
    w.question("3.", "Conclure sur les performances.")
    w.filler(3)
    w.line("1. Une note de bas de page en petit corps, qui n'est pas une question.", size=7)
    w.save()


def draw_centrale(path: Path) -> None:
    """Headings « I », « I.A – », « I.A.1) »; questions « Q 1. »; footers « Page n/3 »
    and a timestamp."""
    footer = lambda n, total: [(LEFT, "P043/2026-03-18 09:59:09"), (WIDTH - 120, f"Page {n}/{total}")]  # noqa: E731
    w = Writer(path, footer=footer, pages=3)
    w.centred("Un voyage vers la planète rouge", "Times-Bold", 16)
    w.filler(4)
    w.heading("I Le voyage entre la Terre et Mars")
    w.filler(2)
    w.heading("I.A – L’orbite de transfert")
    w.filler(3)
    for n in (1, 2, 3):
        w.question(f"Q {n}.")
        w.filler(2)
    w.heading("I.B – La durée du voyage")
    w.question("Q 4.")
    w.filler(3)
    w.new_page()
    w.heading("I.C – La fenêtre de tir")
    w.filler(3)
    w.question("Q 5.")
    w.filler(2)
    w.heading("II L’atterrissage")
    w.heading("II.A – Le bouclier thermique")
    w.heading("II.A.1) Le flux reçu")
    w.filler(3)
    w.question("Q 6.")
    w.question("Q 7.")
    w.filler(4)
    w.new_page()
    w.heading("II.A.2) La température")
    w.filler(3)
    w.question("Q 8.")
    w.filler(6)
    w.save()


def draw_mines(path: Path) -> None:
    """Questions « □ – 1. », the box an « o » in Dingbats; a header repeated from page 2;
    bare page numbers as footers."""
    w = Writer(path, header="Physique I, année 2026 — MP", footer=lambda n, _: [(WIDTH / 2, str(n))], pages=4)
    w.centred("Autour de la diffusion thermique", "Times-Bold", 16)
    w.filler(4)
    number = 0
    for page in range(4):
        w.heading(f"{['I', 'II', 'III', 'IV'][page]}. — Une partie du problème")
        for _ in range(3):
            number += 1
            w.canvas.setFont("ZapfDingbats", 10)
            w.canvas.drawString(LEFT, HEIGHT - w.y, "o")
            w.line(f"– {number}. Exprimer le flux thermique à travers la paroi.", x=LEFT + 12)
            w.filler(2)
        if page < 3:
            w.new_page()
    w.save()


def _statement(
    tmp_path_factory: pytest.TempPathFactory, draw: Callable[[Path], None], name: str
) -> Statement:
    path = tmp_path_factory.mktemp("statements") / f"{name}.pdf"
    draw(path)
    return Statement(path)


@pytest.fixture(scope="session")
def polytechnique(tmp_path_factory: pytest.TempPathFactory) -> Statement:
    return _statement(tmp_path_factory, draw_polytechnique, "polytechnique")


@pytest.fixture(scope="session")
def centrale(tmp_path_factory: pytest.TempPathFactory) -> Statement:
    return _statement(tmp_path_factory, draw_centrale, "centrale")


@pytest.fixture(scope="session")
def mines(tmp_path_factory: pytest.TempPathFactory) -> Statement:
    return _statement(tmp_path_factory, draw_mines, "mines")
