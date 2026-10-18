import pytest

from enoncepdf.structure import normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Une analogie m´ecanique", "une analogie mecanique"),
        ("Onde de ﬂexion.", "onde de flexion"),
        ("Sciences de l’Ingénieur", "sciences de l'ingenieur"),
    ],
)
def test_normalize_undoes_tex_accents_ligatures_and_apostrophes(raw, expected):
    assert normalize(raw) == expected


def test_title_of_the_subject_at_level_minus_one(polytechnique):
    assert polytechnique.headings[0].level == -1
    assert polytechnique.headings[0].text == "Le piège électrique et ses ondes"


def test_unnumbered_parts_at_level_zero(polytechnique):
    parts = [h.text for h in polytechnique.headings if h.level == 0]
    assert parts == ["Physique", "Sciences de l’Ingénieur"]


def test_levels_from_the_shape_of_the_numbers(centrale):
    levels = {h.label: h.level for h in centrale.headings if h.number}
    assert (levels["I"], levels["I.A –"], levels["II.A.1)"]) == (1, 2, 3)


def test_questions_restart_in_the_second_part(polytechnique):
    assert [q.number for q in polytechnique.questions] == [1, 2, 3, 4, 1, 2, 3]


def test_footnote_at_a_small_size_is_not_a_question(polytechnique):
    assert all(q.page != 4 or q.number == 3 for q in polytechnique.questions)
    assert len([q for q in polytechnique.questions if q.page == 4]) == 1


def test_subquestions_attached_to_their_question(polytechnique):
    assert polytechnique.questions[0].subquestions == ("a -", "b -")


def test_mines_box_questions_found(mines):
    assert [q.number for q in mines.questions] == list(range(1, 13))
    assert mines.questions[0].label.endswith("– 1.")


def test_q_labels(centrale):
    assert [q.label for q in centrale.questions][:2] == ["Q 1.", "Q 2."]
