import pytest

from enoncepdf.text import readable_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pr´eambule", "Préambule"),
        ("o`u `a", "où à"),
        ("mˆeme", "même"),
        ("ﬂexion eﬀet", "flexion effet"),
        ("na¨ıf", "naïf"),
    ],
)
def test_accents_recomposed_and_ligatures_undone(raw, expected):
    assert readable_text(raw) == expected
