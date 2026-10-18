"""The facade: a statement, and what one wants from it.

It is the entry point for callers. It hides the chain document → layout → structure →
crops behind one class, and each analysis runs only once, when first asked for::

    statement = Statement("subject.pdf")
    statement.crop("Partie Physique", with_heading=False)  # a part, without its heading
    statement.crop("2.1", within="Partie Physique")        # a subpart
    statement.crop(questions=(1, 17))                       # a range of questions
    statement.crop(pages=(3, 9))                            # whole pages
    for crop in crops:
        print(crop.page, crop.trim_cm)                      # what to keep: page and trim
    print(statement.format(crops))                          # \\includegraphics lines
"""

from pathlib import Path
from types import TracebackType

from PIL import Image

from enoncepdf.cropping import Cropper
from enoncepdf.document import PdfDocument
from enoncepdf.layout import LayoutAnalysis
from enoncepdf.models import GRAPHICX_TEMPLATE, Block, Crop, Heading, Margin, Question
from enoncepdf.numbering import NumberingAnalysis, NumberingProfile
from enoncepdf.sheet import ContactSheet
from enoncepdf.structure import StructureAnalysis

__all__ = ["Statement"]


class Statement:
    """An exam statement (or a report, a model answer) in PDF.

    ``margin`` is the white space, in bp, left around the ink of each crop. The file
    stays open until ``close()``, or the end of a ``with`` block.
    """

    def __init__(self, path: Path | str, margin: float = 3.0) -> None:
        self.document = PdfDocument(path)
        self.layout = LayoutAnalysis(self.document)
        self.structure = StructureAnalysis(self.layout)
        self.cropper = Cropper(self.layout, self.structure, margin)

    def __enter__(self) -> "Statement":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.document.close()

    @property
    def path(self) -> Path:
        return self.document.path

    @property
    def headings(self) -> list[Heading]:
        return self.structure.headings()

    @property
    def questions(self) -> list[Question]:
        return self.structure.questions()

    @property
    def margins(self) -> list[Margin]:
        return self.layout.margins()

    def blocks(self, page: int, gap: int = 6) -> list[Block]:
        return self.layout.blocks(page, gap)

    def heading(self, selection: str, within: str | Heading | None = None) -> Heading:
        """The heading a number or a piece of text names; raises ``SelectionError``."""
        return self.cropper.find_heading(selection, within)

    def crop(
        self,
        part: str | Heading | None = None,
        *,
        with_heading: bool = True,
        intro: bool = False,
        within: str | Heading | None = None,
        questions: tuple[int, int] | None = None,
        pages: tuple[int, int] | None = None,
    ) -> list[Crop]:
        """The crops of a part, a range of questions, pages — or the whole document.

        One selection at a time. Headers, footers and line numbers are never kept.
        ``intro`` reduces a part to the text that opens it.
        """
        if sum(x is not None for x in (part, questions, pages)) > 1:
            raise ValueError("select a part, questions or pages, not several")
        if part is not None:
            return self.cropper.part(part, with_heading=with_heading, within=within, intro=intro)
        if questions is not None:
            return self.cropper.questions(*questions, within=within)
        if pages is not None:
            return self.cropper.pages(*pages)
        return self.cropper.pages(1, self.document.page_count)

    def crop_blocks(self, page: int, first: int, last: int | None = None, gap: int = 6) -> list[Crop]:
        return self.cropper.blocks(page, first, last, gap)

    def format(self, crops: list[Crop], template: str = GRAPHICX_TEMPLATE, file: str | None = None) -> str:
        """One line per crop, written with ``template`` (see ``Crop.format``); ``{file}``
        is ``file``, or the name of the PDF without its suffix."""
        name = self.path.stem if file is None else file
        return "\n".join(c.format(template, name) for c in crops)

    def under(self, heading: str | Heading | None) -> tuple[list[Heading], list[Question]]:
        """The headings and questions placed under ``heading``, up to the next part — the
        heading itself left out. The whole document if ``heading`` is None."""
        if heading is None:
            return self.headings, self.questions
        start, end = self.cropper.span(heading)

        def inside(page: int, y: float) -> bool:
            return start < (page, y) and (end is None or (page, y) < end)

        return (
            [h for h in self.headings if inside(h.page, h.box.y0)],
            [q for q in self.questions if inside(q.page, q.box.y0)],
        )

    def numbering(self, within: str | Heading | None = None) -> NumberingProfile:
        """The numbering profile of the document, or of the part ``within`` only."""
        return NumberingAnalysis(*self.under(within)).profile()

    def levels(self, within: str | Heading | None = None) -> list[int]:
        """The levels of the numbered headings the profile ranks as parts, subparts…"""
        return NumberingAnalysis(*self.under(within)).levels()

    def contact_sheet(self, crops: list[Crop] | None = None, dpi: int | None = None) -> Image.Image:
        """A contact sheet of the given crops, or of all the pages."""
        sheet = ContactSheet(self.document)
        if crops is not None:
            return sheet.crops(crops, dpi or 60)
        return sheet.pages(dpi=dpi or 40)
