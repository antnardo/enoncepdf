from enoncepdf import BlockKind, MarginKind


def test_line_numbers_found(polytechnique):
    numbers = [m for m in polytechnique.margins if m.kind is MarginKind.LINE_NUMBER]
    assert len(numbers) >= 10
    assert all(m.text.isdigit() for m in numbers)


def test_numbered_footer_found(polytechnique):
    footers = [m.text for m in polytechnique.layout.margins(3) if m.kind is MarginKind.FOOTER]
    assert footers == ["– Page 3/4 –"]


def test_timestamped_footer_found(centrale):
    assert [m.text for m in centrale.layout.margins(2)] == ["P043/2026-03-18 09:59:09 Page 2/3"]


def test_repeated_header_and_bare_page_numbers_found(mines):
    margins = mines.layout.margins(3)
    assert {(m.kind, m.text) for m in margins} == {
        (MarginKind.HEADER, "Physique I, année 2026 — MP"),
        (MarginKind.FOOTER, "3"),
    }


def test_body_stops_above_the_footer(polytechnique):
    footer = next(m for m in polytechnique.layout.margins(2) if m.kind is MarginKind.FOOTER)
    assert polytechnique.layout.body(2).y1 < footer.box.y0


def test_text_span_leaves_line_numbers_out(polytechnique):
    left, right = polytechnique.layout.text_span()
    numbers = [m for m in polytechnique.margins if m.kind is MarginKind.LINE_NUMBER]
    assert left > max(m.box.x1 for m in numbers)
    assert right > 450


def test_blocks_of_a_page(centrale):
    blocks = centrale.blocks(1)
    assert blocks[0].kind is BlockKind.TEXT
    assert blocks[0].text == "Un voyage vers la planète rouge"
    assert blocks[-1].kind is BlockKind.MARGIN
