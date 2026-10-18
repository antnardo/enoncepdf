"""What PdfDocument reads of a page, and what it leaves out because nobody sees it."""

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from enoncepdf.document import PdfDocument
from enoncepdf.models import Box

WIDTH, HEIGHT = A4


@pytest.fixture
def draw(tmp_path):
    """Draws one page with ``paint(canvas)`` and returns its PdfDocument."""

    def make(paint):
        path = tmp_path / "page.pdf"
        sheet = Canvas(str(path), pagesize=A4)
        paint(sheet)
        sheet.showPage()
        sheet.save()
        return PdfDocument(path)

    return make


def texts(document):
    return [line.text for line in document.lines(1)]


def test_fragments_on_one_baseline_make_one_line(draw):
    def paint(c):
        c.setFont("Times-Bold", 12)
        c.drawString(72, 700, "1")
        c.setFont("Times-Roman", 12)
        c.drawString(84, 700, "Le piège électrique")

    [line] = draw(paint).lines(1)
    assert (line.text, line.bold, line.all_bold) == ("1 Le piège électrique", True, False)


def test_a_small_number_on_the_baseline_stays_apart(draw):
    """A line number at size 6 on the baseline of a text at size 11 must be recognised
    as a margin: it is not glued to the line."""

    def paint(c):
        c.setFont("Times-Roman", 6)
        c.drawString(40, 700, "15")
        c.setFont("Times-Roman", 11)
        c.drawString(72, 700, "Une ligne du texte courant.")

    assert sorted(texts(draw(paint))) == ["15", "Une ligne du texte courant."]


def test_style_read_from_the_font_name(draw):
    def paint(c):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, 700, "Gras")
        c.setFont("Times-Italic", 12)
        c.drawString(72, 650, "Italique")

    bold, italic = draw(paint).lines(1)
    assert (bold.bold, bold.italic, italic.bold, italic.italic) == (True, False, False, True)


def test_overprinted_fake_bold_read_once(draw):
    def paint(c):
        c.setFont("Times-Roman", 12)
        for dx in (0, 0.3):
            c.drawString(72 + dx, 700, "Titre surimprimé")

    assert texts(draw(paint)) == ["Titre surimprimé"]


def test_clipped_text_is_not_read(draw):
    def paint(c):
        c.setFont("Times-Roman", 12)
        c.drawString(72, 700, "Visible")
        c.saveState()
        path = c.beginPath()
        path.rect(300, 300, 10, 10)
        c.clipPath(path, stroke=0, fill=0)
        c.drawString(72, 500, "Rogné par un chemin de découpe")
        c.restoreState()

    assert texts(draw(paint)) == ["Visible"]


def test_white_text_is_not_read(draw):
    def paint(c):
        c.setFont("Times-Roman", 12)
        c.drawString(72, 700, "Visible")
        c.setFillColorRGB(1, 1, 1)
        c.drawString(72, 500, "Blanc sur blanc")

    assert texts(draw(paint)) == ["Visible"]


def test_text_outside_the_page_is_not_read(draw):
    def paint(c):
        c.setFont("Times-Roman", 12)
        c.drawString(72, 700, "Visible")
        c.drawString(-200, 500, "Hors page")

    assert texts(draw(paint)) == ["Visible"]


def test_accent_drawn_after_its_letter_is_put_back(draw):
    """Old TeX fonts draw the accent as a glyph of its own, after the letter it sits on."""

    def paint(c):
        c.setFont("Times-Roman", 12)
        x = 72.0
        for char in "Pr":
            c.drawString(x, 700, char)
            x += c.stringWidth(char, "Times-Roman", 12)
        c.drawString(x, 700, "e")
        c.drawString(x + 1, 700, "´")
        x += c.stringWidth("e", "Times-Roman", 12)
        c.drawString(x, 700, "ambule")

    assert texts(draw(paint)) == ["Préambule"]


def test_rotated_text_makes_one_line(draw):
    def paint(c):
        c.setFont("Times-Roman", 6)
        c.saveState()
        c.translate(560, 200)
        c.rotate(90)
        c.drawString(0, 0, "IMPRIMERIE 2026")
        c.restoreState()

    [line] = draw(paint).lines(1)
    assert line.text.replace(" ", "") == "IMPRIMERIE2026"
    assert line.box.height > 40


def test_ink_and_image_share_the_frame_of_the_lines(draw):
    def paint(c):
        c.rect(100, HEIGHT - 300, 50, 100, fill=1)

    document = draw(paint)
    ink = document.ink(1)
    assert ink.shape[0] == round(HEIGHT) and ink.shape[1] in (595, 596)  # pdfium rounds up
    assert ink[250, 125] and not ink[150, 125]
    image = document.image(1, dpi=144, area=Box(100, 200, 150, 300))
    assert image.size == (100, 200)
    assert image.getpixel((50, 100)) == (0, 0, 0)


def test_closes_in_a_with_block(draw):
    document = draw(lambda c: c.drawString(72, 700, "x"))
    with document as opened:
        assert opened.page_count == 1
