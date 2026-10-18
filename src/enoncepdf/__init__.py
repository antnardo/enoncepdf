"""Read exam statements in PDF: find their headings and questions, and crop them.

Entry points: ``Statement`` for a subject to crop, ``CompiledStatement`` for an
assignment compiled from crops, ``locate`` for the questions of any lines. On the
command line: ``enoncepdf --help``.
"""

from enoncepdf.compiled import (
    CompiledStatement,
    Inclusion,
    StatementQuestion,
    SyncTeXBox,
    inclusions,
    synctex_boxes,
)
from enoncepdf.cropping import Cropper, SelectionError
from enoncepdf.document import PdfDocument
from enoncepdf.layout import LayoutAnalysis
from enoncepdf.models import (
    BP_PER_CM,
    Block,
    BlockKind,
    Box,
    Crop,
    Heading,
    Line,
    LocatedQuestion,
    Margin,
    MarginKind,
    Position,
    Question,
)
from enoncepdf.numbering import NumberingAnalysis, NumberingProfile, Restart, pattern
from enoncepdf.questions import Mark, comparable_ref, locate, marks, match, questions
from enoncepdf.reading import PdfiumDocument
from enoncepdf.sheet import ContactSheet
from enoncepdf.statement import Statement
from enoncepdf.structure import StructureAnalysis, normalize
from enoncepdf.text import readable_text

__version__ = "0.1.0"

__all__ = [
    "BP_PER_CM",
    "Block",
    "BlockKind",
    "Box",
    "CompiledStatement",
    "ContactSheet",
    "Crop",
    "Cropper",
    "Heading",
    "Inclusion",
    "LayoutAnalysis",
    "Line",
    "LocatedQuestion",
    "Margin",
    "MarginKind",
    "Mark",
    "NumberingAnalysis",
    "NumberingProfile",
    "PdfDocument",
    "PdfiumDocument",
    "Position",
    "Question",
    "Restart",
    "SelectionError",
    "Statement",
    "StatementQuestion",
    "StructureAnalysis",
    "SyncTeXBox",
    "__version__",
    "comparable_ref",
    "inclusions",
    "locate",
    "marks",
    "match",
    "normalize",
    "pattern",
    "questions",
    "readable_text",
    "synctex_boxes",
]
