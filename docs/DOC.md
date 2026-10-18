# enoncepdf — reference

This is the complete reference of enoncepdf 0.1. The [README](../README.md) is the
tour; this document says what every public name does, what it returns and what it
raises, and how the analyses decide.

## Contents

1. [Conventions](#1-conventions)
2. [The modules](#2-the-modules)
3. [Data: `enoncepdf.models`](#3-data-enoncepdfmodels)
4. [Reading a PDF: `PdfDocument`](#4-reading-a-pdf-pdfdocument)
5. [Reading lines anywhere: `PdfiumDocument`](#5-reading-lines-anywhere-pdfiumdocument)
6. [Font style](#6-font-style)
7. [Margins and body: `LayoutAnalysis`](#7-margins-and-body-layoutanalysis)
8. [Headings and questions: `StructureAnalysis`](#8-headings-and-questions-structureanalysis)
9. [Numbering: `NumberingAnalysis`](#9-numbering-numberinganalysis)
10. [Crops: `Cropper`](#10-crops-cropper)
11. [The facade: `Statement`](#11-the-facade-statement)
12. [Contact sheets: `ContactSheet`](#12-contact-sheets-contactsheet)
13. [Questions of any lines: `enoncepdf.questions`](#13-questions-of-any-lines-enoncepdfquestions)
14. [Compiled statements: `enoncepdf.compiled`](#14-compiled-statements-enoncepdfcompiled)
15. [Text: `readable_text`](#15-text-readable_text)
16. [Command line](#16-command-line)
17. [Threads and resources](#17-threads-and-resources)
18. [Measuring a change on real papers](#18-measuring-a-change-on-real-papers)
19. [Troubleshooting](#19-troubleshooting)

## 1. Conventions

- **Units.** Every coordinate and length is in **bp** (big points, 1/72 in), the unit
  of PDF. `BP_PER_CM` (≈ 28.35) converts to centimetres; trims are given in cm.
- **Frame.** The origin is the **top left** of the **visible page** (its CropBox), y
  pointing down. It is the frame of an image rendered at 72 dpi, one pixel per bp: the
  ink masks and the text boxes line up without conversion.
- **Pages** are numbered **from 1**, like the `page=` option of `\includegraphics`.
- **Sizes** are *effective* font sizes in points: the font size times the scale of the
  text matrix (section 4).
- **Immutability.** Everything the analyses return is a frozen dataclass or a list of
  them; nothing is shared mutable state.
- **Laziness.** Each analysis runs once, when first asked, and caches its result; lines
  and ink masks are read page by page on demand.

Every public name is importable from the package root:

```python
from enoncepdf import Statement, PdfiumDocument, locate, CompiledStatement, Crop, ...
```

## 2. The modules

| Module | Holds |
| --- | --- |
| `models` | the data exchanged: `Box`, `Line`, `Margin`, `Block`, `Heading`, `Question`, `LocatedQuestion`, `Crop`, `Position` |
| `text` | `readable_text`: TeX accents recomposed, ligatures undone |
| `document` | `PdfDocument`: lines glued by baseline, ink masks, renderings |
| `reading` | `PdfiumDocument`: lines as pdfium breaks them, nothing held open |
| `layout` | `LayoutAnalysis`: margins, body, text span, blocks |
| `structure` | `StructureAnalysis`: headings and questions from typography; `normalize` |
| `numbering` | `NumberingAnalysis`, `NumberingProfile`, `pattern` |
| `cropping` | `Cropper`: every selection reduced to `between(start, end)`; `SelectionError` |
| `sheet` | `ContactSheet`: thumbnails of pages or crops |
| `statement` | `Statement`: the facade over the chain above |
| `questions` | `marks`, `questions`, `locate`, `match`, `comparable_ref`: questions from text alone |
| `compiled` | `CompiledStatement`: questions of a LaTeX statement built from crops |
| `cli` | the `enoncepdf` command |

Imports go one way: `models` ← readers ← analyses ← `cropping` ← `statement` ← `cli`.

## 3. Data: `enoncepdf.models`

### `Box(x0, y0, x1, y1)`

A rectangle: left, top, right, bottom. Properties `width`, `height`, `center_x`,
`center_y`; `union(other)` returns the smallest box holding both.

### `Line(page, box, text, size, bold, italic, all_bold)`

A visual line of text. `text` is as one reads it (section 15), whitespace collapsed.
`size` is the effective size of its first character, rounded to 0.1 pt. `bold` and
`italic` describe the first character, `all_bold` all of them: a heading « **1** Le
piège » has `bold=True, all_bold=False`.

### `Margin(page, box, kind, text)` and `MarginKind`

Something outside the running text. `kind` is `MarginKind.HEADER` (`"header"`),
`FOOTER` (`"footer"`) or `LINE_NUMBER` (`"line number"`). `text` is empty for a
repeated rule or logo found on the ink alone.

### `Block(page, box, kind, text)` and `BlockKind`

A horizontal band of ink. `kind` is `TEXT`, `FIGURE` (no text inside), `FIGURE_TEXT`
(text covers less than half its height, and it is taller than 25 bp) or `MARGIN`
(every line inside is a margin). `text` is the first line inside, empty for a figure.

### `Position(page, y)`

A point in the flow of the document.

### `Heading(level, number, label, text, page, box)`

| Field | Meaning |
| --- | --- |
| `level` | −1 the title of the subject, 0 « Partie … », then 1, 2, 3 by the shape of the number |
| `number` | the bare number: `"II"`, `"2.1"`, `"I.A"`; empty when unnumbered |
| `label` | the number as printed: `"II."`, `"I.A –"`, `"Partie"` |
| `text` | the heading's text, without the label |

### `Question(number, label, page, box, subquestions=())`

A question found by the structure analysis: `number` is an int, `label` as printed
(« Q 7. »), `subquestions` the labels of its sub-questions (« a - », « b) »).

### `LocatedQuestion(part, ref, label, number, page, box)`

A question found from text alone (section 13). `part` is the Roman numeral of the part
heading before it (`"II"`), None without one; `ref` its reference (`"12"`, `"I.A.1"`,
`"1.a"`), `label` as printed, `number` the last number of the reference.

### `Crop(page, kept, page_width, page_height)`

A slice of a page, described by the box it keeps.

| Member | Value |
| --- | --- |
| `raw_trim_cm` | what to cut from each edge, in cm, unrounded: (left, bottom, right, top) |
| `trim_cm` | the same, rounded to 0.01 cm and never negative — the numbers written everywhere |
| `width_cm`, `height_cm` | the size of the kept box, in cm |
| `format(template=GRAPHICX_TEMPLATE, file="")` | the crop written with a `str.format` template |

**The page and the trim are the output of the package.** Everything else is a way of
writing them, and `format` leaves that to the caller. Its fields:

| Field | Value |
| --- | --- |
| `{page}` | the page, from 1 |
| `{left}`, `{bottom}`, `{right}`, `{top}` | `trim_cm`, as floats |
| `{trim}` | the four as graphicx reads them: `1.23cm 1.72cm 1.88cm 26.25cm` |
| `{width}`, `{height}` | `width_cm`, `height_cm`, rounded to 0.01 |
| `{file}` | `file` |

`GRAPHICX_TEMPLATE` is `\includegraphics[page={page}, trim={trim}, clip]{{{file}}}`:
braces meant literally are doubled. A command of one's own is one template away —
`r"\myinclude[{page}]{{{trim}}}{{{file}}}"` —, and what a template cannot express (a
scale chosen when the slice is taller than the page, say) is a few lines over
`trim_cm` and `height_cm`.

## 4. Reading a PDF: `PdfDocument`

```python
PdfDocument(path)
```

An open PDF, read page by page on demand and cached. Use it as a context manager or
call `close()`.

| Member | Returns |
| --- | --- |
| `path` | the `Path` of the file |
| `page_count` | the number of pages |
| `size(page)` | `(width, height)` of the visible page, bp |
| `lines(page)` | the `Line`s of the page, top to bottom, then left to right |
| `ink(page, white=245)` | a boolean numpy array `[y, x]` at 72 dpi: pixels darker than `white` (0–255) |
| `image(page, dpi=72, area=None)` | an RGB `PIL.Image` of the page, or of `area` (a `Box`) |

### How lines are built

1. pdfium lists every character with its loose box (the font's advance and its ascent
   and descent), its origin, its font, its size and its angle.
2. Characters are cut into **fragments**: runs with one font, one size, one angle and
   one baseline (within 0.5 bp). Rotated text keeps its own fragments, along its
   direction.
3. What nobody sees is dropped:
   - a character whose box centre lies outside the visible page;
   - a character whose centre falls outside the clipping path of its text object (the
     bounding boxes of the path, intersected): the text of a figure included as a form
     XObject keeps its whole page, clipped to the figure, and may lie right over the
     running text;
   - a fragment with no ink under any of its characters' tight boxes (white on white,
     hidden under an image). The test is per fragment:
     some PDFs declare glyph widths that drift from what is drawn, and a lone last
     character can miss its own ink;
   - a character identical to one already read within 1 bp — a fake bold drawn by
     overprinting — unless it repeats the character just before with the very same
     box, which is how pdfium expands an « ﬀ » or « ﬁ » ligature;
   - a fragment made only of combining marks (the arrow over a vector, U+20D7), which
     pdfium sets on its own raised baseline and which would otherwise pass for a
     header.
4. Fragments are grouped into **lines** by baseline, within 1.5 bp, unless their
   sizes differ by a ratio below 0.7: a line number at 6 pt on the baseline of a text
   at 11 pt stays apart, so that it can be recognised as a margin.
5. The **text** of a line is assembled character by character in reading order. A
   spacing accent (acute, grave, circumflex, diaeresis, tilde, cedilla, ring, breve,
   caron, dot) goes just before the letter whose centre is
   nearest — old TeX fonts draw the accent after its letter — and a space goes where
   two characters are more than 1.2 bp apart. pdfium's generated spaces are ignored:
   they land after such an accent and would split the word.
6. The loose box of a horizontal character is bounded to 1.25 sizes above its
   baseline and 0.6 below: some math fonts declare an absurd ascent, and one such
   character would make its line 60 bp tall.

pdfium marks a hyphenation hyphen with the code 0x02; it reads as « - ». UTF-16
surrogate pairs are glued back (mathematical italic letters read as such).

## 5. Reading lines anywhere: `PdfiumDocument`

```python
PdfiumDocument(path)
```

The reader for finding questions in any PDF (section 13). It differs from
`PdfDocument` on purpose:

- lines are those pdfium breaks itself, at its line feeds: to find a number at the
  start of a line, safer than fragments glued by baseline, which a descender or an
  index can shift from one line to the next;
- it holds nothing open: every call opens the file, reads it and closes it, and
  returns values that owe nothing to pdfium;
- it reads the hidden text too, and lets the caller restrict a page to an area.

| Member | Returns |
| --- | --- |
| `path`, `page_count` | as above |
| `size(page)` | `(width, height)` of the visible page (CropBox), bp |
| `media(page)` | the whole page (MediaBox) as a `Box` in the frame of the visible page |
| `lines(page, area=None)` | the `Line`s of the page; with `area`, those most of whose characters fall inside it (1 bp tolerance) |

`media` matters for a trimmed page: a crop made by setting its CropBox keeps the rest
of its original page, hidden but still there, and `media` says where.

Both readers take the visible page from pdfium's bounding box, which inherits the
boxes from the page tree: `pypdfium2`'s `get_cropbox()` does not, and falls back to
US Letter for a page that inherits its MediaBox.

## 6. Font style

PDF has no notion of bold: a font is bold when its program draws thick strokes.
Both readers decide `bold` and `italic` per font, in this order:

1. **The name**, without its subset prefix: « Bold », « Medi », « Bd », « Black »,
   « Heavy », « SemiBold » make it bold, « Ital », « Oblique », « Slant », « Corsiva »
   italic; so do the TeX names that say it without the word — `CMBX`, `CMSSBX`,
   `CMMIB`, `CMBSY`, `SFBX`, `SFSX`, `SFXC`, `SFBI`, `ECBX`, `ECSX` bold; `CMMI`, `CMTI`,
   `CMSL`, `CMBXTI`, `SFTI`, `SFSL`, `SFSI`, `ECTI`, `ECSL` italic.
2. **The descriptor flags**: ForceBold, Italic.
3. **The embedded font program**, read by FreeType through Pillow: its declared style
   (« Bold », « Bold Italic »). This is what tells that a Word PDF's « CIDFont+F1 » is
   Calibri Bold.
4. For an **opaque name** (« F1 », « CIDFont+F3 », a Type 3 « Fe »), a weight from 700
   to 1000: a subset program stripped of its names declares « Regular » whatever it
   draws. Weights outside that range are pdfium's guesses and ignored — it reports 976
   for a Latin Modern Roman regular.

Any one signal is enough. Styles are cached per page: a Word PDF names its fonts
« F1 », « F2 » page by page.

## 7. Margins and body: `LayoutAnalysis`

```python
LayoutAnalysis(document: PdfDocument)
```

| Member | Returns |
| --- | --- |
| `margins(page=None)` | the `Margin`s of one page, or of the whole document |
| `body(page)` | the `Box` between header and footer, across the document's text span |
| `text_span()` | `(left, right)`: the extent of the body's ink over the whole document |
| `body_ink(page, vertical_only=False)` | the ink mask with margins erased and the outside of the body blank; `vertical_only` keeps the full width |
| `blocks(page, gap=6)` | the `Block`s of the page, bands of ink separated by at least `gap` bp of white |

### The rules for margins

Candidates are the lines in the top or bottom **band** of the page, 12 % of its height.

- **Repetition.** A candidate whose *signature* (lower case, every number replaced by
  `#`) comes back within 6 bp of the same height on enough pages: 2 when the document
  has 4 pages or fewer, else 30 % of the pages (at least 2). A bare number (`#`) needs
  3 pages at least: on two pages, a graduation of a figure can mimic it.
- **Page numbers.** A candidate that reads « Page 3/12 », « – 3/12 – » or « Page 3 »
  is a margin even alone.
- **Line numbers.** Small numbers alone (1 to 4 digits), smaller than the running
  text, more than 3 bp left or right of the column of long lines (over 40
  characters); at least three of them.
- **Rules and logos.** On the ink mask with the text erased, a band of ink in the top
  or bottom band at the same height (within 3 bp) on half the pages at least, in a
  document of 3 pages or more.

The **body** of a page runs from 1 bp below its lowest header to 1 bp above its highest
footer. Its width is `text_span()`, the same on every page, so that crops of one
statement share one scale.

## 8. Headings and questions: `StructureAnalysis`

```python
StructureAnalysis(layout: LayoutAnalysis)
```

`headings()` and `questions()` return the `Heading`s and `Question`s of the body lines,
in document order. `normalize(text)` is the comparison key used throughout: lower case,
no accents (TeX's detached ones included), no ligature, single spaces, no final
punctuation, typographic apostrophes made straight.

The **running size** is the median size of the body lines longer than 30 characters.

A line is a **heading** when it is at most 120 characters and:

- it reads « Partie … » or « Part … », with or without a number, in bold, italics or
  larger than the running size — level 0, or the depth of its decimal number
  (« Partie 1.1 » → 1);
- or it is all bold, or bold at least 1 pt above the running size, and starts with a
  number made of Arabic numbers, Roman numerals or single capitals separated by dots
  (« 2.1 », « II.A », « I.A.1) »), then a separator (`.`, `)`, `:`, a dash) and text —
  unless it reads as a question at the running size;
- or it is all bold, unnumbered, centred on the text span (within 20 bp) and narrower
  than 80 % of it: the **title of the subject**, level −1 — unless three such lines
  share a page, which makes it a cover page.

The **level** of a numbered heading comes from the shape of its number: each
component is Arabic (`1`), Roman (`R`) or a letter (`A`); shapes are ranked by depth,
then component by component, Roman before Arabic before letter. Whether a lone « I »,
« V » or « X » is Roman or a letter, the document decides: Roman if a numeral of two
characters or more appears in any shape.

A line is a **question** when it starts with « 7. », « 7) », « Q 7. », « Question 7 : »
or « □ – 7. » (a Dingbats box, which extracts as « o », « ❏ » or « ■ »), followed by
text, at a size no more than 1 pt below the running size, and when its number is 1 or
the previous question's plus one. A line starting with « a - », « b) », « (c) » at the
running size is a **sub-question** of the question before.

## 9. Numbering: `NumberingAnalysis`

```python
NumberingAnalysis(headings, questions)
NumberingAnalysis.from_structure(structure)
```

| Member | Returns |
| --- | --- |
| `levels()` | the levels of the numbered headings, highest first, those below 1 left out when there are others |
| `profile()` | a `NumberingProfile` |

`pattern(label, romans=frozenset())` reduces a label to its pattern: each counter
becomes `{1}` (Arabic), `{R}` / `{r}` (Roman, upper / lower case), `{A}` / `{a}`
(letter); the words « Q », « Question », « Partie », « Part » and other words stay;
dashes become `-`; the Mines box becomes `□`. `romans` lists the ranks of the counters
to read as Roman when they are a single letter.

| Label | Pattern |
| --- | --- |
| `II.A –` | `{R}.{A} -` |
| `Q 7.` | `Q {1}.` |
| `o – 1.` | `□ - {1}.` |
| `Partie 1.1 :` | `Partie {1}.{1} :` |

`NumberingProfile` fields: `part`, `subpart`, `subsubpart` (the dominant pattern of
each of the first three levels, empty when absent), `question`, `subquestion`,
`restart` and `examples` (a few real labels). `restart` is `"subpart"` when questions
start again at 1 after a heading of the second level, `"part"` after one of the first,
`"none"` otherwise.

## 10. Crops: `Cropper`

```python
Cropper(layout, structure, margin=3.0)
```

`margin` is the white space, in bp, kept around the ink — never beyond the positions
asked for, so that it does not take back the descender of a heading left out.

| Method | Crops |
| --- | --- |
| `part(selection, with_heading=True, within=None, intro=False)` | from the heading to the next heading of the same level or higher; `intro`: to the next heading of any level |
| `questions(first, last, within=None)` | from question `first` to whatever follows question `last` (a question or a heading) |
| `pages(first, last=None)` | the body of whole pages |
| `blocks(page, first, last=None, gap=6)` | blocks of one page, numbered from 1 as in `LayoutAnalysis.blocks` |
| `between(start, end)` | the one operation: the flow from a `Position` to another (None: the end) |
| `find_heading(selection, within=None)` | the `Heading` a selection names |
| `span(within)` | the bounds of a part in document order, `((page, y), (page, y) or None)` |

`between` keeps, on each page crossed, the body between the two positions, then
tightens it on the ink; a page whose slice has no ink gives no crop. All crops of one
call share the same left and right edges: the extent of the ink over all the pages
crossed.

The start of a part is the first blank pixel row above its heading (within 8 bp) —
text boxes come from font metrics, and an accent can rise above them; without the
heading, the first blank row below it.

### Selecting a heading

`find_heading` compares with `normalize`, among the headings inside `within` if given:

1. **exact**: the selection is the number, the label or « partie » + the number of a
   numbered heading;
2. otherwise **whole**: the selection is the whole text, or label and text;
3. otherwise **textual**: the selection is contained in the text, or starts label and
   text.

The first non-empty group wins; « Flexion » names « III. Flexion », not « Relation de
dispersion des ondes de flexion ». No match, or several, raises `SelectionError`
(a `ValueError`) whose message lists the headings found, or the candidates and the
advice to use `within=`.

## 11. The facade: `Statement`

```python
Statement(path, margin=3.0)
```

Builds `PdfDocument` → `LayoutAnalysis` → `StructureAnalysis` → `Cropper`, exposed as
`document`, `layout`, `structure`, `cropper`. A context manager; `close()` closes the
file.

| Member | Returns |
| --- | --- |
| `path` | the file |
| `headings`, `questions`, `margins` | as the analyses give them |
| `blocks(page, gap=6)` | `LayoutAnalysis.blocks` |
| `heading(selection, within=None)` | `Cropper.find_heading` |
| `crop(part=None, *, with_heading=True, intro=False, within=None, questions=None, pages=None)` | the crops of one selection, or of the whole document; `ValueError` for several selections |
| `crop_blocks(page, first, last=None, gap=6)` | `Cropper.blocks` |
| `format(crops, template=GRAPHICX_TEMPLATE, file=None)` | one line per crop, `{file}` being `file` or the PDF's stem |
| `under(heading)` | `(headings, questions)` strictly inside a part, the whole document for None |
| `numbering(within=None)` | the `NumberingProfile` of the document or of one part |
| `levels(within=None)` | `NumberingAnalysis.levels` of the document or of one part |
| `contact_sheet(crops=None, dpi=None)` | a sheet of the crops (60 dpi), or of all the pages (40 dpi) |

## 12. Contact sheets: `ContactSheet`

```python
ContactSheet(document: PdfDocument)
```

`pages(pages=None, dpi=40, columns=4)` and `crops(crops, dpi=60, columns=2)` return an
RGB `PIL.Image`: a grid of renderings, each framed in grey and captioned with its page.
An empty list gives a blank 200 × 60 image.

## 13. Questions of any lines: `enoncepdf.questions`

These functions read only the text of `Line`s, not their style: they work on the lines
of either reader, of a whole page or of an area.

| Function | Returns |
| --- | --- |
| `marks(lines)` | the `Mark`s: every line that opens with a question or part number |
| `questions(marks)` | the `LocatedQuestion`s: the longest increasing run, part by part |
| `locate(lines)` | `questions(marks(lines))` |
| `comparable_ref(ref)` | a key to compare references: « Q12 » → « 12 », « I.A.1) » → « I.A.1 » |
| `match(title, located, other=None)` | the question a title names, or None |

### What opens a question

The line starts (after optional spaces, and an optional Mines box and dash) with:

| Form | Reference |
| --- | --- |
| « Q12 », « Q 12. », « Question 12 : » | `12` |
| « I.A.1) », « II.3 », « I.A.1.b » | `I.A.1`, `II.3`, `I.A.1.b` |
| « 1.a) » | `1.a` |
| « 12) », « 12. », « 12 — » | `12` |

and a letter follows within 12 characters (« 12) » alone, « 3 — » alone are not
questions; « 2.5 kg » is not either). When at least three lines are longer than 30
characters, their median size is the running size and a question must lie between
1 pt below and 1.5 pt above it.

### What opens a part

« Partie 2 », « Part III », or a Roman numeral followed by an optional dot and dash and
a capital letter: « II. Suspension », « I.A. — Champ ».

### The run

Questions are ordered by `(part, *their numbers)`; only the longest strictly
increasing run is kept, in document order — section numbers (« 1 - Énergie »),
quantities (« Q3 désigne… ») and captions fall out. At equal length, a question keeps
as neighbour the one written in the same form (« 2) » after « 1) »).

`Mark(kind, ref, label, number, order, form, line)`: `kind` is `"question"` or
`"part"`; `order` the tuple compared; `form` one of `q`, `roman`, `sub`, `num)`,
`num.`, `num-`, `part`.

### Matching a title

`match` compares `comparable_ref` of `title` (and of `other`, a second title to try)
with each question's reference; otherwise it takes the last number of `title` and
returns the question with that number if there is exactly one.

## 14. Compiled statements: `enoncepdf.compiled`

```python
CompiledStatement(tex, pdf=None, synctex=None, log=None, directory=None, commands=INCLUSION_COMMANDS)
```

A LaTeX statement built from pages of papers — what one writes with the crops of
section 10 — whose questions are wanted where they fall in the compiled PDF: to show
the statement beside a student's answer, to link a marking scheme to it. The PDF alone
cannot say (a trimmed page keeps the text its trim hides), nor can the source (it holds
inclusions, not questions).

`commands` are the inclusion commands read, without backslash: `INCLUSION_COMMANDS`,
`("includegraphics", "includepdf")`, by default. A class that wraps them in a command
of its own adds it — `commands=(*INCLUSION_COMMANDS, "myinclude")` —, the command
taking graphicx's optional argument (`page`, `trim`, `scale`) and then the file. `pdf`, `synctex` (`.synctex.gz` or
`.synctex`) and `log` default to the source's name; `directory` is the folder of the
compilation, the source's by default — pass it when the source is a copy, so that
inclusions and the file SyncTeX names are still found.

`questions()` returns `StatementQuestion(problem, question, top)` objects: the rank of
the `\section` (unstarred) the question falls under, the `LocatedQuestion` placed in
the compiled PDF, and the top of its line as a fraction of the page height. It returns
an empty list without source, PDF or SyncTeX, or without latexdetok (Python < 3.13).

`inclusions()` / `inclusions(source, commands=INCLUSION_COMMANDS)` list the included pages:
`Inclusion(problem, line, file, page, trim, end, scale)`, `trim` in bp in the order of
graphicx. Commented-out inclusions are skipped; `\includepdf[pages=…]` gives one
inclusion per page; a `\section` inside `pagecommand` opens the problem of its pages.

`synctex_boxes(path, source)` reads a SyncTeX file into `{source line: [SyncTeXBox]}`,
boxes in TeX points from the top left of the page (`page`, `left`, `top`, `right`,
`bottom`, `width`, `height`).

### How questions are placed

1. Each included file is found from the log (`<./DS2/paper.pdf>`), else in a folder
   named after the statement, else in the folder of the compilation.
2. Its visible part is the page minus the `trim`.
3. Its box in the compiled PDF is the SyncTeX box recorded between the line of the
   inclusion and the end of its paragraph, with the proportions of the visible part
   (within 15 %), no wider than the visible part at the requested scale (5 % slack),
   not tiny, and after the previous inclusion's box.
4. The lines of the visible part are read (`PdfiumDocument.lines(page, area)`) and
   carried into the compiled page.
5. Text typed in the source is read from the compiled PDF, outside the full extent of
   every image — including what its trim hides, since the compiled PDF keeps that text.
6. `locate` runs problem by problem.

## 15. Text: `readable_text`

`readable_text(text)` recomposes a spacing accent placed before its letter
(« Pr´eambule » → « Préambule », « na¨ıf » → « naïf »), expands ligatures
(« ﬂexion » → « flexion ») and returns NFC text. Both readers apply it to every line.

## 16. Command line

`enoncepdf` (or `python -m enoncepdf`) runs one command on one PDF; it exits with 1
and prints the message of a `SelectionError` on stderr.

| Command | Arguments |
| --- | --- |
| `structure PDF` | — |
| `crop PDF [selection] [output] [--sheet PNG]` | the page and trim of each crop; writes a contact sheet |
| `blocks PDF PAGE [--gap BP] [--from N --to M [output]]` | lists the blocks, or crops blocks N to M |
| `sheet PDF [--pages A-B] [-o PNG]` | writes a sheet of pages (to the temp folder by default) and prints its path |
| `numbering PDF [--within PART]` | the profile, one field per line |

A *selection* is one of `--part TEXT` (with `--without-heading`, `--intro`,
`--within TEXT`), `--questions RANGE`, `--pages RANGE`. A range reads « 1-10 »,
« Q1-10 », « Q1-Q10 », « p3 », in either order; `enoncepdf.cli.parse_range` parses it.

The *output* is, by default, one line per crop, `page N L=…cm B=…cm R=…cm U=…cm`; or
`--json`, a list of `{"page", "L", "B", "R", "U"}` in cm; or `--latex`, lines written
with `GRAPHICX_TEMPLATE`; or `--template TEMPLATE`, lines written with a template of
one's own (section 3). `--file NAME` sets `{file}`, the PDF's name without `.pdf` by
default.

## 17. Threads and resources

pdfium is not thread-safe. `PdfDocument` (and so `Statement`) keeps its file open
until `close()`; share neither between threads. `PdfiumDocument` opens and closes the
file at each call and returns plain values: in a threaded server, take one lock around
each of its calls, as around any pdfium call.

Memory: ink masks are kept per page (one byte per bp², about 0.5 MB per A4 page) for
the life of the `PdfDocument`.

## 18. Measuring a change on real papers

Exam papers are under copyright, so the tests draw their own (reportlab). A change to
the reading or the analyses is measured on real ones with `scripts/survey.py`, which
is not shipped in the wheel:

```bash
uv run python scripts/survey.py files.txt before.json    # one PDF path per line
git switch my-change
uv run python scripts/survey.py files.txt after.json
uv run python scripts/survey.py --compare before.json after.json
```

The dump holds, per file, page count, headings, questions, margins, the crops of the
whole document, of each heading of level 1 or less and of questions 1 to 3, the
numbering profile and the blocks of page 1. Version 0.1, reading through pdfium, was
measured this way against an earlier reader built on PyMuPDF, on 185 papers and
reports from 1998 to 2026: the same questions on all but three papers, which gained
some; headings gained on 25 papers and lost on 8 (captions and stray numbers the older
reader took for headings); crops within 1 bp on 144 papers; on the others the margins
differ, and a review by eye found the pdfium reader right more often than not —
chiefly footers the older reader kept and figure text it did not see.

## 19. Troubleshooting

| Symptom | Likely cause and remedy |
| --- | --- |
| No heading found | The PDF has no text layer (a scan): only pages and blocks can be cropped. Or the headings are not bold by any of the signals of section 6: check `document.lines(page)` for `bold`. |
| A heading at the wrong level | Its number has a shape the document uses elsewhere at another depth; check `Heading.number`. |
| `SelectionError: … names several headings` | The number comes back in two parts: add `within=` (or `--within`). |
| `SelectionError: questions … not found` | Numbering restarts in each part: add `within=`, or the questions are not at the running size. |
| A footer kept in a crop | It does not repeat at the same height (± 6 bp) and does not read « Page n/N »; crop pages and adjust, or report the case. |
| `CompiledStatement.questions()` is empty | No SyncTeX file (compile with `-synctex=1`), Python below 3.13 (no latexdetok), or included pages that are images without text. |
| A character missing in a heading | Its font has no Unicode mapping; pdfium cannot read it. |
