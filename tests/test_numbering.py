import pytest

from enoncepdf.numbering import pattern


@pytest.mark.parametrize(
    ("label", "romans", "expected"),
    [
        ("II.A –", frozenset(), "{R}.{A} -"),
        ("Q 7.", frozenset(), "Q {1}."),
        ("2.1", frozenset(), "{1}.{1}"),
        ("I", frozenset({0}), "{R}"),
        ("I", frozenset(), "{A}"),
        ("o – 1.", frozenset(), "□ - {1}."),
        ("b -", frozenset(), "{a} -"),
        ("Partie 1.1 :", frozenset(), "Partie {1}.{1} :"),
    ],
)
def test_pattern(label, romans, expected):
    assert pattern(label, romans) == expected


def test_profile_of_a_whole_statement(centrale):
    profile = centrale.numbering()
    assert (profile.part, profile.subpart, profile.subsubpart, profile.question) == (
        "{R}",
        "{R}.{A} -",
        "{R}.{A}.{1})",
        "Q {1}.",
    )
    assert profile.restart == "none"


def test_restart_after_each_part(polytechnique):
    assert polytechnique.numbering().restart == "part"


def test_profile_of_one_part(polytechnique):
    profile = polytechnique.numbering(within="Partie Physique")
    assert (profile.part, profile.subpart, profile.question, profile.subquestion) == (
        "{1}",
        "{1}.{1}",
        "{1}.",
        "{a} -",
    )


def test_levels_of_one_part(polytechnique):
    assert polytechnique.levels("Partie Physique") == [1, 2]
