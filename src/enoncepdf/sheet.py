"""Contact sheets of thumbnails, to check at a glance.

Looking at twenty pages one by one costs twenty readings; a contact sheet shows at once
what is wrong: an almost empty page, a figure that overflows, a crop that kept a header
or cut a line. Two sheets:

- ``pages``: the whole pages of a document, in a grid;
- ``crops``: each crop rendered as it will be included, framed by a rule, with its page
  — the check of a statement built from crops before even compiling it.
"""

from PIL import Image, ImageDraw

from enoncepdf.document import PdfDocument
from enoncepdf.models import Crop

__all__ = ["ContactSheet"]

_GUTTER = 14  # px between two thumbnails
_CAPTION = 12  # px of height kept for the page number


class ContactSheet:
    """Assembles renderings of pages or crops into one image."""

    def __init__(self, document: PdfDocument) -> None:
        self.document = document

    def pages(self, pages: list[int] | None = None, dpi: int = 40, columns: int = 4) -> Image.Image:
        pages = pages or list(range(1, self.document.page_count + 1))
        thumbnails = [(f"p. {p}", self.document.image(p, dpi)) for p in pages]
        return self._grid(thumbnails, columns)

    def crops(self, crops: list[Crop], dpi: int = 60, columns: int = 2) -> Image.Image:
        thumbnails = [(f"p. {c.page}", self.document.image(c.page, dpi, c.kept)) for c in crops]
        return self._grid(thumbnails, columns)

    @staticmethod
    def _grid(thumbnails: list[tuple[str, Image.Image]], columns: int) -> Image.Image:
        if not thumbnails:
            return Image.new("RGB", (200, 60), "white")
        columns = max(1, min(columns, len(thumbnails)))
        width = max(img.width for _, img in thumbnails)
        rows = [thumbnails[i : i + columns] for i in range(0, len(thumbnails), columns)]
        heights = [max(img.height for _, img in row) for row in rows]
        sheet = Image.new(
            "RGB",
            (columns * (width + _GUTTER) + _GUTTER, sum(h + _GUTTER + _CAPTION for h in heights) + _GUTTER),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        y = _GUTTER
        for row, height in zip(rows, heights, strict=True):
            for k, (caption, img) in enumerate(row):
                x = _GUTTER + k * (width + _GUTTER)
                draw.text((x, y), caption, fill="black")
                sheet.paste(img, (x, y + _CAPTION))
                draw.rectangle(
                    [x - 1, y + _CAPTION - 1, x + img.width, y + _CAPTION + img.height],
                    outline="gray",
                )
            y += height + _GUTTER + _CAPTION
        return sheet
