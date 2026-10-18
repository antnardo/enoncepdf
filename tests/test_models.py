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


def test_latex_without_scale_when_the_slice_fits():
    crop = Crop(3, Box(50, 100, 540, 400), 595.0, 842.0)
    assert crop.latex("paper").startswith("\\includetoolargegraphics[page=3, trim=")
    assert "scale" not in crop.latex("paper")


@pytest.mark.parametrize(("height", "scale"), [(700.0, "0.92"), (800.0, "0.80")])
def test_latex_sets_the_scale_of_a_slice_too_tall(height, scale):
    crop = Crop(4, Box(40, 40, 550, 40 + height), 595.0, 842.0)
    assert f"scale={scale}" in crop.latex("paper")


def test_latex_writes_the_rounded_trim():
    crop = Crop(2, Box(34.9, 744.1, 541.7, 793.2), 595.0, 842.0)
    expected = " ".join(f"{v:.2f}cm" for v in crop.trim_cm)
    assert f"trim={expected}, clip" in crop.latex("paper")
