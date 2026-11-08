"""The frame the pages share: found, rounded, with its exceptions, and given back by hand."""

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from enoncepdf import BP_PER_CM, Frame, Framing, Statement, round_margin
from enoncepdf.cli import main, parse_frame

WIDTH, HEIGHT = A4
CM = BP_PER_CM


WORDS = ["onde", "champ", "masse", "charge", "force", "énergie", "tension", "courant", "flux", "pression"]


def _page(canvas: Canvas, page: int, lines: int = 40) -> None:
    """A page of justified text with 2 cm margins, each line spaced out to reach the right
    margin. No two lines say the same, or they would be taken for headers repeated from
    page to page."""
    x0, x1 = 2 * CM, WIDTH - 2 * CM
    canvas.setFont("Times-Roman", 10)
    for k in range(lines):
        y = HEIGHT - 3 * CM - 14 * k
        text = "Mesurer " + " ".join(WORDS[(page * 7 + k * 3 + j) % len(WORDS)] for j in range(6)) + " E"
        spacing = (x1 - x0 - canvas.stringWidth(text, "Times-Roman", 10)) / (len(text) - 1)
        canvas.drawString(x0, y, text, charSpace=spacing)


@pytest.fixture(scope="module")
def typeset(tmp_path_factory) -> Statement:
    """Six pages with 2 cm side margins; page 4 has a figure 1 cm from each side, page 6
    is short."""
    path = tmp_path_factory.mktemp("framing") / "typeset.pdf"
    canvas = Canvas(str(path), pagesize=A4)
    for page in range(1, 7):
        _page(canvas, page, lines=12 if page == 6 else 40)
        if page == 4:
            canvas.rect(1 * CM, 8 * CM, WIDTH - 2 * CM, 3 * CM, stroke=1, fill=0)
        canvas.showPage()
    canvas.save()
    return Statement(path)


@pytest.mark.parametrize(
    ("measured", "rounded"),
    [(2.01, 2.0), (1.98, 2.0), (2.15, 2.0), (2.5, 2.5), (2.35, 2.2), (1.5875, 1.5), (0.0, 0.0)],
)
def test_margin_rounded_to_the_half_centimetre_when_close(measured, rounded):
    assert round_margin(measured) == rounded


def test_common_frame_is_the_text_column_in_round_numbers(typeset):
    common = typeset.framing.common
    assert (common.left, common.right) == (2.0, 2.0)
    assert not typeset.framing.scanned


def test_a_figure_wider_than_the_text_makes_an_exception_on_its_sides_only(typeset):
    framing = typeset.framing
    assert set(framing.pages) == {4}
    exception = framing.pages[4]
    assert exception.top is None and exception.bottom is None
    assert exception.left is not None and exception.left <= 1.0
    assert exception.right is not None and exception.right <= 1.0


def test_crops_share_the_frame_width_and_keep_the_figure(typeset):
    crops = typeset.crop()
    widths = {c.page: round(c.kept.width, 1) for c in crops}
    assert len({w for p, w in widths.items() if p != 4}) == 1
    assert widths[4] > widths[1]
    assert all(c.trim_cm[0] == 2.0 for c in crops if c.page != 4)


def test_a_short_page_is_still_tightened_on_its_ink(typeset):
    short = next(c for c in typeset.crop() if c.page == 6)
    assert short.height_cm < 8


def test_a_frame_given_by_hand_replaces_the_one_found(typeset):
    framing = typeset.framing.with_common(Frame(1.5, 1.0, 1.5, 1.0))
    crops = typeset.crop(pages=(2, 2), framing=framing)
    assert crops[0].trim_cm[0] == 1.5 and crops[0].trim_cm[2] == 1.5


def test_an_exception_given_by_hand_follows_the_common_frame_elsewhere(typeset):
    framing = Framing(Frame(2.0, 1.0, 2.0, 1.0), {3: Frame(left=3.0)})
    assert framing.frame(3) == Frame(3.0, 1.0, 2.0, 1.0)
    [crop] = typeset.crop(pages=(3, 3), framing=framing)
    assert crop.trim_cm[0] == 3.0 and crop.trim_cm[2] == 2.0


def test_framing_travels_as_plain_data(typeset):
    data = typeset.framing.as_dict()
    assert data["pages"] and all(isinstance(k, str) for k in data["pages"])
    assert Framing.of_dict(data) == typeset.framing


@pytest.mark.parametrize(
    "data", [{"common": [2, 2, 2]}, {"common": [2, -1, 2, 2]}, {"common": [None, 2, 2, 2]}]
)
def test_unreadable_framing_refused(data):
    with pytest.raises(ValueError):
        Framing.of_dict(data)


def test_a_hairline_just_outside_the_margin_is_never_cut(tmp_path):
    """A rule 0.4 bp left of a 2 cm margin: the 72 dpi mask sees it in the same pixel
    as the text, the check at 576 dpi does not let the rounding cut it."""
    path = tmp_path / "hairline.pdf"
    canvas = Canvas(str(path), pagesize=A4)
    for page in range(1, 5):
        _page(canvas, page)
        if page == 2:
            canvas.setLineWidth(0.3)
            canvas.line(2 * CM - 0.4, 10 * CM, 2 * CM - 0.4, 20 * CM)
        canvas.showPage()
    canvas.save()
    with Statement(path) as statement:
        crop = next(c for c in statement.crop() if c.page == 2)
        assert crop.kept.x0 <= 2 * CM - 0.6


def test_a_scan_has_one_frame_per_page(tmp_path):
    path = tmp_path / "scan.pdf"
    canvas = Canvas(str(path), pagesize=A4)
    for shift in (0.0, 0.8, 0.3):
        canvas.rect((2 + shift) * CM, 3 * CM, 15 * CM, 22 * CM, stroke=0, fill=1)
        canvas.showPage()
    canvas.save()
    with Statement(path) as statement:
        framing = statement.framing
        assert framing.scanned and set(framing.pages) == {1, 2, 3}
        lefts = [framing.frame(p).left for p in (1, 2, 3)]
        assert lefts[1] - lefts[0] == pytest.approx(0.8, abs=0.11)


def test_frame_read_on_the_command_line():
    assert parse_frame("2,2.5,2,3") == Frame(2.0, 2.5, 2.0, 3.0)
    assert parse_frame("2 2.5 2 3") == Frame(2.0, 2.5, 2.0, 3.0)


def test_structure_shows_the_frame_and_crop_takes_one(typeset, capsys):
    assert main(["structure", str(typeset.path)]) == 0
    assert "Frame (cm, left top right bottom): 2 " in capsys.readouterr().out
    assert main(["crop", str(typeset.path), "--pages", "2", "--frame", "1.5,1,1.5,1", "--json"]) == 0
    assert '"L": 1.5' in capsys.readouterr().out
