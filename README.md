# enoncepdf

Read exam statements in PDF the way a teacher reads them: find their **headings** and
their **questions**, and **crop** any part of them — a section, a range of questions,
some pages — into slices that leave out headers, footers and line numbers.

A crop is a **page** and a **trim**: what to cut from each edge, left, bottom, right,
top, in cm — the order of the `trim` key of graphicx. That is all the package outputs;
how it is written is yours to choose: a table, JSON, `\includegraphics` lines, or the
command of your own class.

*Énoncé* is French for the statement of an exam problem. The package was written for
French competitive exams (CPGE *concours*: Polytechnique, Centrale, Mines, CCINP…) and
their reports, and it recognises their conventions — « Partie Physique », « Q 7. »,
« □ – 12. », « I.A.1) » — but nothing in it is tied to one competition: it works from
typography and repetition, and on any PDF with text.

```python
from enoncepdf import Statement

with Statement("subject.pdf") as statement:
    for crop in statement.crop("Partie Physique", with_heading=False):
        print(crop.page, crop.trim_cm)
```

```text
3 (1.41, 2.43, 1.62, 4.97)
4 (1.41, 2.43, 1.62, 2.11)
…
```

## Contents

- [What it does](#what-it-does)
- [Installation](#installation)
- [Command line](#command-line)
- [Python](#python)
- [Finding the questions of any PDF](#finding-the-questions-of-any-pdf)
- [Statements compiled from crops](#statements-compiled-from-crops)
- [How it works](#how-it-works)
- [Limits](#limits)
- [Development](#development)
- [License](#license)

## What it does

- **Margins.** Headers, footers, timestamps, « Page 3/12 », repeated rules and logos,
  and the line numbers some papers print every five lines are found over the whole
  document — a footer is what repeats — and never kept in a crop.
- **Structure.** Headings and their levels (the subject's title, « Partie … », then
  `I`, `I.A`, `I.A.1` or `1`, `1.1`, `1.1.1`), questions and their sub-questions, and
  the **numbering profile** of the statement: the patterns of its numbers
  (`{R}.{A} -`, `Q {1}.`) and where questions restart at 1.
- **Crops.** Name an extract as you read it — a heading number, a piece of a heading,
  a range of questions, pages, blocks — and get one crop per page, tightened on the
  ink, all of the same width so that stacked slices keep one scale.
- **Output.** The page and the trim of each crop, as a table, JSON, or lines written
  with any template (`\includegraphics` by default, your own command otherwise), and
  contact sheets (PNG) to check crops at a glance.
- **Questions anywhere.** `locate` finds the questions of any list of lines — a whole
  page, a crop, a model answer — from their numbers alone, keeping the longest
  increasing run so that section numbers and quantities (« Q3 désigne la charge… »)
  are left out.
- **Compiled statements.** For an assignment compiled from such crops,
  `CompiledStatement` reads the LaTeX source, its log and its SyncTeX, and places each
  question of the included papers in the compiled PDF.

Everything is read through [pdfium](https://pdfium.googlesource.com/pdfium/)
(`pypdfium2`): the package is MIT-licensed from end to end, with no AGPL dependency.

## Installation

```bash
pip install enoncepdf
```

Python 3.11 or later. The dependencies are `pypdfium2`, `numpy` and `Pillow`;
on Python 3.13 and later, `latexdetok` comes along to read the LaTeX source of
compiled statements (without it, `CompiledStatement.questions()` returns nothing).

## Command line

```bash
enoncepdf --help            # or: python -m enoncepdf --help
```

| Command | What it gives |
| --- | --- |
| `structure subject.pdf` | headings with their levels, questions, margins left out |
| `crop subject.pdf …` | the page and the trim of each cropped page, L B R U in cm |
| `blocks subject.pdf 5` | the bands of ink of page 5; `--from 2 --to 5` crops them |
| `sheet subject.pdf` | the pages as thumbnails; `--pages 3-8` for those only |
| `numbering subject.pdf` | the numbering patterns (parts, subparts, questions…) |

`crop` takes one selection at a time:

| Option | Extract |
| --- | --- |
| `--part II`, `--part "Partie Physique"` | from the heading to the next one of the same level |
| `--part 2.1 --within "Partie Physique"` | the same, when a number comes back in two parts |
| `--part NASA --intro` | only the text that opens the part, up to its first heading |
| `--without-heading` | the part without its heading line |
| `--questions 1-10`, `--questions Q1-Q10` | from question 1 to whatever follows question 10 |
| `--pages 3-9` | the body of whole pages |

### Questions 1 to 10

```bash
enoncepdf crop subject.pdf --questions Q1-10
```

```text
page 2   L=1.23cm B=1.72cm R=1.88cm U=26.25cm
page 3   L=1.23cm B=2.36cm R=1.88cm U=1.98cm
page 4   L=1.23cm B=18.52cm R=1.88cm U=2.05cm
```

Each value is the margin **removed** from that edge of the page, in the order of the
`trim` key of graphicx: left, bottom, right, top. On page 2 the kept band runs from
26.25 cm below the top to 1.72 cm above the bottom — question 1, at the bottom of the
page. Headers and footers are always outside the kept area; the last crop stops before
question 11 or the heading that follows question 10.

### Writing the crops

The same numbers, three other ways:

```bash
enoncepdf crop subject.pdf --questions Q1-10 --json
enoncepdf crop subject.pdf --questions Q1-10 --latex
enoncepdf crop subject.pdf --questions Q1-10 --template '\myinclude[{page}]{{{trim}}}{{{file}}}'
```

```text
[{"page": 2, "L": 1.23, "B": 1.72, "R": 1.88, "U": 26.25}, …]
\includegraphics[page=2, trim=1.23cm 1.72cm 1.88cm 26.25cm, clip]{subject}
\myinclude[2]{1.23cm 1.72cm 1.88cm 26.25cm}{subject}
```

`--template` takes a Python format string, so literal braces are doubled. Its fields:

| Field | Value |
| --- | --- |
| `{page}` | the page, from 1 |
| `{left}`, `{bottom}`, `{right}`, `{top}` | the trim of each edge, in cm, rounded to 0.01 |
| `{trim}` | the four of them as graphicx reads them: `1.23cm 1.72cm 1.88cm 26.25cm` |
| `{width}`, `{height}` | the size of the kept area, in cm — to choose a scale, say |
| `{file}` | `--file`, or the name of the PDF without `.pdf` |

Numeric fields take a format spec: `{left:.1f}`. `--latex` is the template
`\includegraphics[page={page}, trim={trim}, clip]{{{file}}}`.

To check before including anything:

```bash
enoncepdf crop subject.pdf --questions Q1-10 --sheet crops.png
```

## Python

```python
from enoncepdf import SelectionError, Statement

with Statement("subject.pdf") as statement:
    for heading in statement.headings:
        print(heading.level, heading.label, heading.text, heading.page)

    crops = statement.crop(questions=(1, 10))
    for crop in crops:
        print(crop.page, crop.trim_cm)        # (left, bottom, right, top) in cm
    print(statement.format(crops))            # \includegraphics lines
    print(statement.format(crops, r"\myinclude[{page}]{{{trim}}}{{{file}}}"))
    statement.contact_sheet(crops).save("crops.png")

    try:
        statement.crop("2.1")                 # two « 2.1 », one in each part
    except SelectionError as error:
        print(error)                          # lists both, and suggests within=
    statement.crop("2.1", within="Partie Physique")
```

`Statement.crop` takes one selection: a part (`"II"`, `"Partie Physique"`, a piece of
a heading, or a `Heading`), `questions=(first, last)` or `pages=(first, last)` — or
nothing, for the whole document — plus `with_heading`, `intro` and `within`. A
selection that names nothing, or several headings, raises `SelectionError`, whose
message lists what was found.

`Statement.numbering()` gives the numbering profile of the whole statement or of one
part:

```python
>>> statement.numbering(within="Partie Physique")
NumberingProfile(part='{1}', subpart='{1}.{1}', subsubpart='', question='{1}.',
                 subquestion='{a} -', restart='none', examples=('1', '2.1', '1.', '2.'))
```

The lower layers are public too — `PdfDocument` (lines and ink masks),
`LayoutAnalysis` (margins, body, blocks), `StructureAnalysis`, `NumberingAnalysis`,
`Cropper`, `ContactSheet` — for a caller that needs one step only. All coordinates
are in bp (1/72 in), from the top left of the visible page, pages numbered from 1.
The full reference is in [docs/DOC.md](docs/DOC.md).

## Finding the questions of any PDF

`locate` works on lines, wherever they come from. `PdfiumDocument` reads them the way
pdfium breaks them, holds nothing open between calls, and can restrict a page to an
area — the visible part of a trimmed page:

```python
from enoncepdf import PdfiumDocument, locate, match

document = PdfiumDocument("model-answer.pdf")
lines = [line for page in range(1, document.page_count + 1) for line in document.lines(page)]
questions = locate(lines)
for q in questions:
    print(q.part, q.ref, q.label, q.page, q.box)

match("Q12", questions)          # by reference, else by number when it is unique
match("I.A.1", questions)
```

The forms recognised are « 12) », « 12. », « 12 — », « Q12 », « Q 12. »,
« Question 12 : », « □ – 12. », « I.A.1) », « II.3) », « 1.a) », with part headings
« II. Title », « I.A. — Title », « Partie 2 », « Part 2 ». When the numbering restarts
in each part, each question carries its part (`q.part == "II"`).

## Statements compiled from crops

The crops above end up in a new assignment: a LaTeX file that includes pages of past
papers, trimmed. Once it is compiled, where are its questions? Its PDF does not say
reliably — a trimmed page keeps the text the trim hides — and its source holds no
question at all, only inclusions. `CompiledStatement` answers it: it reads the source
for the inclusions, finds each included page from the log, reads the questions in the
visible part of that page, and places them in the compiled PDF through SyncTeX,
problem by problem (each `\section` opens a problem). A program that shows the
statement next to students' answers, or that links a marking scheme to the questions,
needs exactly that.

```python
from enoncepdf import CompiledStatement

for found in CompiledStatement("DS2.tex").questions():
    print(found.problem, found.question.ref, found.question.page, round(found.top, 3))
```

It needs the source, the PDF, the SyncTeX file (`-synctex=1`) and the log, all next to
the source unless given. The inclusions read are `\includegraphics` and `\includepdf`;
a class that wraps them in a command of its own names it:
`CompiledStatement("DS2.tex", commands=(*INCLUSION_COMMANDS, "myinclude"))`, the
command taking graphicx's options (`page`, `trim`, `scale`) and the file. Text typed in
the source itself is read from the compiled PDF.

## How it works

- **Reading.** pdfium gives every character with its box, font and size. Characters
  nobody sees are dropped: outside the page, clipped away, white on white, or drawn
  twice for a fake bold. Lines are rebuilt by baseline, and a spacing accent that old
  TeX fonts draw after its letter is put back before it (« Pr´eambule » →
  « Préambule »).
- **Style.** PDF has no bold: a font is bold when it draws thick. The package reads the
  font name, including TeX's (`CMBX10` is bold, `CMTI10` italic), the descriptor flags,
  and the style the embedded font program declares, read by FreeType — the only way to
  know that a Word PDF's « CIDFont+F1 » is Calibri Bold.
- **Margins** are what repeats at the same height across pages, what reads « Page
  3/12 », and small numbers in a column beside the text. The **body** of each page
  lies between them; its width is that of the whole document.
- **Headings** are bold lines (or larger, or « Partie … » in italics); their level
  comes from the *shape* of their number, so that `I/I.A/I.A.1` and `1/1.1/1.1.1` get
  the same levels. **Questions** start with their number at the running size, and
  follow one another.
- **Crops** come from one operation: keep the body between two positions of the flow,
  then tighten it on the ink.

## Limits

- Scanned PDFs without a text layer have no lines: margins, headings and questions are
  then not found (crops of pages and blocks still work, on the ink).
- A character whose font has no Unicode mapping (some math fonts) reads as nothing:
  « erf(χ) » may read « erf( ) ».
- The vocabulary is that of French statements, with « Part » as well; headings in
  other languages are found when they are numbered and bold.
- Rotated pages are read in their unrotated frame.
- `PdfDocument` and `Statement` keep the file open and are not thread-safe; pdfium is
  not either: a threaded caller takes a lock around each call, or uses
  `PdfiumDocument`, which opens and closes the file at each reading.

## Development

```bash
uv sync --group dev
uv run ruff format src tests examples scripts
uv run ruff check src tests examples scripts
uv run mypy
uv run pytest -q
```

The tests draw their statements with reportlab: no real exam paper ships with the
package. `scripts/survey.py` runs the analyses over a list of real PDFs and compares
two versions; it is how a change is measured before release.

## License

MIT — see [LICENSE](LICENSE).
