"""The text of a PDF read by pdfium: lines, their size, the visible page."""

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from enoncepdf.models import Box
from enoncepdf.reading import PdfiumDocument

WIDTH, HEIGHT = A4


def test_size_is_the_effective_size(tmp_path):
    """A text at size 1 enlarged ten times by its matrix, as in some crops, reads at
    size 10: comparable with that of another PDF."""
    path = tmp_path / "matrix.pdf"
    sheet = Canvas(str(path), pagesize=A4)
    text = sheet.beginText()
    text.setTextTransform(10, 0, 0, 10, 72, 700)
    text.setFont("Helvetica", 1)
    text.textOut("1) Une question en corps 1, agrandie dix fois.")
    sheet.drawText(text)
    sheet.setFont("Helvetica-Bold", 12)
    sheet.drawString(72, 600, "II. Un titre en gras")
    sheet.showPage()
    sheet.save()
    question, heading = PdfiumDocument(path).lines(1)
    assert question.size == pytest.approx(10, abs=0.1)
    assert question.text == "1) Une question en corps 1, agrandie dix fois."
    assert (heading.size, heading.bold, heading.all_bold) == (12.0, True, True)


def test_cropbox_is_the_visible_page_and_area_filters_lines(tmp_path):
    path = tmp_path / "crop.pdf"
    sheet = Canvas(str(path), pagesize=A4)
    sheet.setCropBox((50, 300, 545, 700))
    sheet.setFont("Helvetica", 11)
    for y, text in (
        (650, "2) Déterminer le courant."),
        (500, "3) En déduire la puissance."),
        (200, "8) Hors."),
    ):
        sheet.drawString(72, y, text)
    sheet.showPage()
    sheet.save()
    document = PdfiumDocument(path)
    assert document.size(1) == pytest.approx((495, 400))
    visible = document.lines(1, Box(0, 0, 495, 400))
    assert [line.text for line in visible] == ["2) Déterminer le courant.", "3) En déduire la puissance."]
    # the whole page, in the frame of the crop: 50 bp to its left, 300 below it
    media = document.media(1)
    assert (media.x0, media.y0, media.x1, media.y1) == pytest.approx((-50, 700 - HEIGHT, WIDTH - 50, 700))


def _inherited_mediabox_pdf() -> bytes:
    """A PDF whose page inherits its MediaBox (A4) from the page tree, as some producers
    write it; pypdfium2's get_cropbox would fall back to US Letter."""
    stream = b"BT /F1 12 Tf 72 700 Td (1\\) Une question.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 595 842] >>",
        b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return out


def test_inherited_mediabox_is_read(tmp_path):
    path = tmp_path / "inherited.pdf"
    path.write_bytes(_inherited_mediabox_pdf())
    document = PdfiumDocument(path)
    assert document.size(1) == pytest.approx((595, 842))
    [line] = document.lines(1)
    # the top of « 1 », 8.6 bp above its baseline at 700 bp from the bottom of A4; with
    # a US Letter page it would fall 50 bp higher
    assert line.box.y0 == pytest.approx(842 - 700 - 8.6, abs=1)
