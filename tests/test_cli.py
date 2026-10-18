import argparse
import json

import pytest

from enoncepdf.cli import main, parse_range


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("1-10", (1, 10)),
        ("Q1-10", (1, 10)),
        ("Q1-Q10", (1, 10)),
        ("q 3 - 7", (3, 7)),
        ("p9", (9, 9)),
        ("12-4", (4, 12)),
    ],
)
def test_range_read(typed, expected):
    assert parse_range(typed) == expected


@pytest.mark.parametrize("typed", ["", "X3", "1-", "Q1-10-12"])
def test_unreadable_range_refused(typed):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_range(typed)


def test_structure_lists_headings_and_questions(centrale, capsys):
    assert main(["structure", str(centrale.path)]) == 0
    out = capsys.readouterr().out
    assert "I.A –" in out and "Questions: 8" in out


def test_trims_as_json(centrale, capsys):
    assert main(["trims", str(centrale.path), "--questions", "Q1-3", "--json"]) == 0
    [trim] = json.loads(capsys.readouterr().out)
    assert set(trim) == {"page", "L", "B", "R", "U"} and trim["page"] == 1


def test_crop_writes_latex_and_sheet(centrale, capsys, tmp_path):
    sheet = tmp_path / "sheet.png"
    assert main(["crop", str(centrale.path), "--part", "I.C", "--sheet", str(sheet)]) == 0
    assert capsys.readouterr().out.startswith("\\includetoolargegraphics[page=2")
    assert sheet.is_file()


def test_selection_error_exits_with_one(centrale, capsys):
    assert main(["crop", str(centrale.path), "--part", "Chimie"]) == 1
    assert "names no heading" in capsys.readouterr().err


def test_numbering_and_blocks(centrale, capsys):
    assert main(["numbering", str(centrale.path)]) == 0
    assert "Q {1}." in capsys.readouterr().out
    assert main(["blocks", str(centrale.path), "1"]) == 0
    assert "blocks" in capsys.readouterr().out
