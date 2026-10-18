def test_sheet_of_pages_in_a_grid(centrale):
    image = centrale.contact_sheet(dpi=20)
    assert image.width > 3 * 595 * 20 / 72 and image.height < 2 * 842 * 20 / 72


def test_sheet_of_crops(centrale):
    crops = centrale.crop(questions=(1, 3))
    image = centrale.contact_sheet(crops)
    assert image.width >= crops[0].kept.width * 60 / 72


def test_empty_sheet(centrale):
    assert centrale.contact_sheet([]).size == (200, 60)
