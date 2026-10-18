"""Questions found at their number at the start of a line, and the run they make."""

import pytest

from enoncepdf.models import Box, Line
from enoncepdf.questions import comparable_ref, locate, marks, match


def lines(*texts: str, page: int = 1) -> list[Line]:
    return [
        Line(page, Box(50, 20 * rank, 500, 20 * rank + 10), text, 10.0, False, False, False)
        for rank, text in enumerate(texts)
    ]


@pytest.mark.parametrize(
    ("text", "ref"),
    [
        ("12) Calculer la force.", "12"),
        ("12. Calculer la force.", "12"),
        ("12 — Calculer la force.", "12"),
        ("Q12. Que devient la force ?", "12"),
        ("Q 7. Que devient la force ?", "7"),
        ("Question 3 : Que devient la force ?", "3"),
        ("□ – 7. Déterminer la vitesse.", "7"),
        ("I.A.1) Rappeler l'expression", "I.A.1"),
        ("II.3) Établir l'équation", "II.3"),
        ("1.a) Écrire l'équation", "1.a"),
    ],
)
def test_a_question_opens_its_line(text, ref):
    [mark] = marks(lines(text))
    assert (mark.kind, mark.ref) == ("question", ref)


@pytest.mark.parametrize("text", ["2.5 kg de matière", "3 —", "12)", "Il faut 3) au moins", "1.1 Les ondes"])
def test_what_does_not_open_a_question(text):
    assert [m for m in marks(lines(text)) if m.kind == "question"] == []


@pytest.mark.parametrize(
    ("text", "part"),
    [
        ("II. — Corriger la gravitation", "II"),
        ("I. Mouvement sans suspension", "I"),
        ("I.A. — Champ uniforme", "I"),
        ("Partie 2 Électricité", "II"),
        ("Part 3 Optics", "III"),
    ],
)
def test_a_part_heading(text, part):
    [mark] = marks(lines(text))
    assert (mark.kind, mark.ref) == ("part", part)


def test_the_run_leaves_headings_and_quantities_out():
    found = locate(
        lines(
            "1 - Énergie électrostatique",
            "1) En s'appuyant sur le travail des forces",
            "2) Exprimer l'énergie",
            "Q3 désigne la charge de l'électrode",
            "3) Montrer que",
            "2 – Système à trois électrodes",
            "4) En déduire",
        )
    )
    assert [(q.ref, q.label) for q in found] == [("1", "1)"), ("2", "2)"), ("3", "3)"), ("4", "4)")]


def test_numbering_restarts_in_each_part():
    found = locate(
        lines(
            "I. Mouvement sans suspension",
            "1.a) Écrire l'équation",
            "2) On suppose maintenant",
            "II. Suspension sans amortisseur",
            "1. La liaison entre les masses",
            "2.a) Établir l'équation",
            "III. Suspension avec amortisseur",
            "1.a) Écrire l'équation",
        )
    )
    assert [(q.part, q.ref) for q in found] == [
        ("I", "1.a"),
        ("I", "2"),
        ("II", "1"),
        ("II", "2.a"),
        ("III", "1.a"),
    ]


def test_a_number_off_the_running_size_is_not_a_question():
    """« 6 – Corrigé »: the number of an assignment under its title, at 12 pt over a text
    at 10 pt; an index at 7 pt neither."""
    running = "Une ligne du texte courant, assez longue pour mesurer son corps."

    def line(text, size, rank):
        return Line(1, Box(50, 20 * rank, 500, 20 * rank + 10), text, size, False, False, False)

    found = marks(
        [
            line("6 – Corrigé", 12.1, 0),
            *(line(running, 10.0, rank) for rank in range(1, 4)),
            line("0 – un indice mal lu", 7.0, 4),
            line("1) Calculer la vitesse.", 10.0, 5),
        ]
    )
    assert [mark.ref for mark in found] == ["1"]


def test_the_position_is_that_of_the_line():
    [question] = locate(lines("Titre", "12) Calculer", page=3))
    assert (question.page, question.box) == (3, Box(50, 20, 500, 30))


@pytest.mark.parametrize(
    ("raw", "expected"), [("Q12", "12"), ("I.A.1)", "I.A.1"), (" q 3 ", "3"), (None, "")]
)
def test_comparable_ref(raw, expected):
    assert comparable_ref(raw) == expected


class TestMatch:
    located = locate(lines("I.A.1) Rappeler", "I.A.2) On se place", "I.B.1) Déterminer"))

    def test_by_reference(self):
        assert match("I.B.1", self.located).ref == "I.B.1"

    def test_by_the_second_title(self):
        assert match("Q9", self.located, other="I.A.2)").ref == "I.A.2"

    def test_by_number_when_it_is_unique(self):
        assert match("Question 2", self.located).ref == "I.A.2"

    def test_an_ambiguous_number_says_nothing(self):
        assert match("Q1", self.located) is None  # I.A.1 or I.B.1
