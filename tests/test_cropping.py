import pytest

from enoncepdf import MarginKind, SelectionError


def test_part_without_heading_runs_to_the_next_part(polytechnique):
    crops = polytechnique.crop("Partie Physique", with_heading=False)
    assert [c.page for c in crops] == [1, 2]


def test_without_heading_starts_below_the_heading(polytechnique):
    heading = polytechnique.heading("Partie Physique")
    first = polytechnique.crop("Partie Physique", with_heading=False)[0]
    assert first.kept.y0 > heading.box.y1


def test_with_heading_keeps_the_heading(polytechnique):
    heading = polytechnique.heading("Partie Physique")
    first = polytechnique.crop("Partie Physique")[0]
    assert first.kept.y0 <= heading.box.y0


def test_part_stops_before_the_next_part(polytechnique):
    last = polytechnique.crop("Partie Physique")[-1]
    following = polytechnique.heading("Sciences de l")
    assert last.page < following.page or last.kept.y1 < following.box.y0


def test_no_crop_keeps_a_footer_or_a_line_number(polytechnique):
    crops = polytechnique.crop()
    footers = {m.page: m.box.y0 for m in polytechnique.margins if m.kind is MarginKind.FOOTER}
    numbers = [m for m in polytechnique.margins if m.kind is MarginKind.LINE_NUMBER]
    assert all(c.kept.y1 < footers[c.page] for c in crops)
    assert all(c.kept.x0 > max(m.box.x1 for m in numbers) for c in crops)


def test_ambiguous_number_refused(polytechnique):
    with pytest.raises(SelectionError, match="several headings"):
        polytechnique.crop("2.1")


def test_ambiguity_lifted_by_within(polytechnique):
    assert [c.page for c in polytechnique.crop("2.1", within="Partie Physique")] == [2]


def test_subpart_by_its_number(centrale):
    assert [c.page for c in centrale.crop("I.C", with_heading=False)] == [2]


def test_range_of_questions_stops_before_what_follows(centrale):
    crops = centrale.crop(questions=(1, 3))
    following = centrale.heading("I.B")
    assert [c.page for c in crops] == [1]
    assert crops[0].kept.y1 < following.box.y0


def test_unknown_questions_list_what_was_found(centrale):
    with pytest.raises(SelectionError, match="found: 1, 2, 3"):
        centrale.crop(questions=(40, 41))


def test_unknown_heading_lists_the_headings(centrale):
    with pytest.raises(SelectionError, match="Le voyage entre la Terre"):
        centrale.crop("Partie Chimie")


def test_one_selection_at_a_time(centrale):
    with pytest.raises(ValueError, match="not several"):
        centrale.crop("I", pages=(1, 2))


def test_intro_stops_before_the_first_heading(centrale):
    title = centrale.heading("Un voyage vers la planète rouge")
    first = centrale.heading("I")
    crops = centrale.crop(title, with_heading=False, intro=True)
    assert [c.page for c in crops] == [1]
    assert crops[0].kept.y0 > title.box.y1 and crops[0].kept.y1 < first.box.y0


def test_heading_quoted_in_full_preferred_to_those_containing_it(centrale):
    assert centrale.heading("L’atterrissage").number == "II"


def test_heading_passed_directly(centrale):
    heading = centrale.heading("I.C")
    assert centrale.crop(heading) == centrale.crop("I.C")


def test_crops_of_one_call_share_their_width(polytechnique):
    crops = polytechnique.crop(pages=(1, 3))
    assert len({(c.kept.x0, c.kept.x1) for c in crops}) == 1


def test_blocks_out_of_range_refused(centrale):
    with pytest.raises(SelectionError, match="page 1 has"):
        centrale.crop_blocks(1, 1, 99)
