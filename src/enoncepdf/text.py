"""The text of a PDF as one reads it.

Old TeX fonts extract the accent before its letter (« Pr´eambule », « `a ») and a
ligature as one character (« ﬂexion »): a heading reused in a document — a
``\\section`` — must read « Préambule », « flexion ». This module depends on no PDF
reader, so that both readers (``document`` and ``reading``) give the same text.
"""

import re
import unicodedata

__all__ = ["readable_text"]

# spacing accent → combining accent, placed after the letter it precedes
_ACCENTS = {"´": "́", "`": "̀", "ˆ": "̂", "¨": "̈", "˜": "̃"}
_LONE_ACCENT = re.compile(r"([´`ˆ¨˜])([A-Za-zı])")
_LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})


def readable_text(text: str) -> str:
    """Accents recomposed and ligatures undone: « Pr´eambule » → « Préambule »."""
    recomposed = _LONE_ACCENT.sub(lambda m: m.group(2).replace("ı", "i") + _ACCENTS[m.group(1)], text)
    return unicodedata.normalize("NFC", recomposed.translate(_LIGATURES))
