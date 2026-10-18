import pytest

from enoncepdf.models import BP_PER_CM, Box, Crop


def test_box_measures_and_union():
    box = Box(10, 20, 30, 60).union(Box(0, 30, 20, 80))
    assert box == Box(0, 20, 30, 80)
    assert (box.width, box.height, box.center_x, box.center_y) == (30, 60, 15, 50)


def test_raw_trim_in_order_left_bottom_right_top():
    crop = Crop(3, Box(BP_PER_CM, 2 * BP_PER_CM, 500, 800), 595.0, 842.0)
    left, bottom, right, top = crop.raw_trim_cm
    assert (round(left, 2), round(top, 2)) == (1.0, 2.0)
    assert round(bottom, 2) == round((842 - 800) / BP_PER_CM, 2)
    assert round(right, 2) == round(95 / BP_PER_CM, 2)


def test_trim_clamped_at_zero_and_rounded():
    # a kept box that overflows the page by a hair gives no negative trim
    crop = Crop(1, Box(-0.3, 10, 595.2, 842.0), 595.0, 842.0)
    assert crop.trim_cm == (0.0, 0.0, 0.0, round(10 / BP_PER_CM, 2))


def test_default_format_is_a_graphicx_line():
    crop = Crop(3, Box(50, 100, 540, 400), 595.0, 842.0)
    expected = " ".join(f"{v:.2f}cm" for v in crop.trim_cm)
    assert crop.format(file="paper") == f"\\includegraphics[page=3, trim={expected}, clip]{{paper}}"


def test_format_fields_for_any_command():
    crop = Crop(2, Box(BP_PER_CM, 2 * BP_PER_CM, 500, 800), 595.0, 842.0)
    line = crop.format("\\mine[{page}]{{{left:.1f} {top:.1f}}}{{{file}}} {width} {height}", "s")
    assert line == f"\\mine[2]{{1.0 2.0}}{{s}} {round(crop.width_cm, 2)} {round(crop.height_cm, 2)}"


def test_size_of_the_kept_box_in_cm():
    crop = Crop(1, Box(0, 0, 2 * BP_PER_CM, 3 * BP_PER_CM), 595.0, 842.0)
    assert (crop.width_cm, crop.height_cm) == pytest.approx((2, 3))
