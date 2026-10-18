from enoncepdf import Statement


def test_format_one_line_per_crop_on_the_file_stem(centrale):
    crops = centrale.crop(pages=(1, 2))
    lines = centrale.format(crops).splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("\\includegraphics[page=1, trim=") and lines[0].endswith("{centrale}")
    assert centrale.format(crops, "{page}:{file}", "other").splitlines() == ["1:other", "2:other"]


def test_under_a_part_leaves_the_part_heading_out(polytechnique):
    physics = polytechnique.heading("Partie Physique")
    headings, questions = polytechnique.under(physics)
    assert physics not in headings
    assert [h.number for h in headings] == ["1", "2", "2.1", "2.2"]
    assert [q.number for q in questions] == [1, 2, 3, 4]


def test_whole_document_is_one_crop_per_page(centrale):
    assert [c.page for c in centrale.crop()] == [1, 2, 3]


def test_statement_closes_in_a_with_block(centrale):
    with Statement(centrale.path) as statement:
        assert statement.document.page_count == 3
