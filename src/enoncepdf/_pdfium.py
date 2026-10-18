"""What both readers ask pdfium about a character: its effective size, its font, its style.

The **effective size** is the font size times the scale of the text matrix: a crop may
write all its text at size 1 enlarged by the matrix, and its sizes would not compare
with those of another PDF.

The **style** is the hard part. PDF has no notion of bold: a font is bold when its
program draws thick strokes. PyMuPDF asks FreeType, which reads the style the font
program declares; pdfium does not expose it. Its font weight is no substitute — the
descriptor's ``FontWeight`` is often missing, and pdfium then estimates it, 976 for a
Latin Modern Roman regular. Measured on 439 fonts of 185 real exam statements, the
signals that hold are, in order:

- the font name: « Bold », « Medi », « Bd », « Black », and the TeX names that say it
  without the word — ``CMBX10``, ``SFBX1200`` (cm-super), ``CMTI10``, ``CMMI12``;
- the descriptor flags, ForceBold and Italic, when the producer sets them;
- the font program itself, read by FreeType through Pillow — the only way to learn
  that a Word PDF's « CIDFont+F1 » is Calibri Bold;
- for such an opaque name, a weight from 700 to 1000: a subset program stripped of
  its names declares « Regular » whatever it draws.

This reads TeX fonts better than PyMuPDF did, which missed the bold of ``CMBX10`` in
some files: on those 185 statements, 31 gain headings and none loses a question.
"""

import ctypes
import io
import math
import re

import pypdfium2.raw as pdfium_c
from PIL import ImageFont

__all__ = ["CharReader"]

_BOLD = re.compile(
    r"Bold|Medi|Bd|Black|Heavy|Semi[Bb]old"
    r"|^(CMBX|CMSSBX|CMMIB|CMBSY|SFBX|SFSX|SFXC|SFBI|SFSO|ECBX|ECSX)"
)
_ITALIC = re.compile(r"Ital|Oblique|Slant|Corsiva|TI$|^(CMMI|CMTI|CMSL|CMBXTI|SFTI|SFSL|SFBI|SFSI|ECTI|ECSL)")
_STYLE_BOLD = re.compile(r"Bold|Black|Heavy", re.IGNORECASE)
_STYLE_ITALIC = re.compile(r"Italic|Oblique", re.IGNORECASE)
_OPAQUE = re.compile(r"(CIDFont\+)?F[0-9a-z]+")  # « F1 », « CIDFont+F3 », Type 3 « Fe »
_FLAG_ITALIC = 1 << 6
_FLAG_FORCE_BOLD = 1 << 18


class CharReader:
    """Reads the size, font and style of the characters of one text page.

    Font names are those of the page's resources: a Word PDF names its fonts « F1 »,
    « F2 » page by page, so the style cache lives no longer than the page.
    """

    def __init__(self, textpage: ctypes.c_void_p) -> None:
        self.raw = textpage
        self._flags = ctypes.c_int()
        self._buffer = ctypes.create_string_buffer(256)
        self._matrix = pdfium_c.FS_MATRIX()
        self._styles: dict[str, tuple[bool, bool]] = {}

    def size(self, index: int) -> float:
        """The effective size of the character, in points."""
        size = float(pdfium_c.FPDFText_GetFontSize(self.raw, index))
        if pdfium_c.FPDFText_GetMatrix(self.raw, index, ctypes.byref(self._matrix)):
            size *= math.hypot(self._matrix.c, self._matrix.d)
        return size

    def font(self, index: int) -> str:
        """The name of the character's font, subset prefix included (« ABCDEF+CMBX10 »)."""
        length = pdfium_c.FPDFText_GetFontInfo(
            self.raw, index, self._buffer, len(self._buffer), ctypes.byref(self._flags)
        )
        return self._buffer.value.decode("latin-1") if 0 < length <= len(self._buffer) else ""

    def style(self, index: int, font: str) -> tuple[bool, bool]:
        """Bold and italic, for the font ``font`` that the character ``index`` uses."""
        if font not in self._styles:
            self._styles[font] = self._read_style(index, font)
        return self._styles[font]

    def _read_style(self, index: int, font: str) -> tuple[bool, bool]:
        self.font(index)  # sets the descriptor flags of this character's font
        flags = self._flags.value
        name = font if font.startswith("CIDFont") else font.split("+", 1)[-1]
        bold = bool(_BOLD.search(name)) or bool(flags & _FLAG_FORCE_BOLD)
        italic = bool(_ITALIC.search(name)) or bool(flags & _FLAG_ITALIC)
        declared = _program_style(self.raw, index)
        if declared:
            bold = bold or bool(_STYLE_BOLD.search(declared))
            italic = italic or bool(_STYLE_ITALIC.search(declared))
        if _OPAQUE.fullmatch(name):
            # a subset program stripped of its names says « Regular » whatever it draws
            bold = bold or 700 <= pdfium_c.FPDFText_GetFontWeight(self.raw, index) <= 1000
        return bold, italic


def _program_style(textpage: ctypes.c_void_p, index: int) -> str | None:
    """The style the embedded font program declares (« Bold », « Regular »), read by
    FreeType; None for a font that is not embedded or that FreeType cannot read."""
    font = pdfium_c.FPDFTextObj_GetFont(pdfium_c.FPDFText_GetTextObject(textpage, index))
    size = ctypes.c_size_t()
    if not font or not pdfium_c.FPDFFont_GetFontData(font, None, 0, ctypes.byref(size)) or not size.value:
        return None
    data = (ctypes.c_uint8 * size.value)()
    pdfium_c.FPDFFont_GetFontData(font, data, size.value, ctypes.byref(size))
    try:
        _, style = ImageFont.truetype(io.BytesIO(bytes(data)), 10).getname()
    except (OSError, ValueError):
        return None
    return style
