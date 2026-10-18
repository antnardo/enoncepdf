# enoncepdf

[![CI](https://github.com/antnardo/enoncepdf/actions/workflows/ci.yml/badge.svg)](https://github.com/antnardo/enoncepdf/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/enoncepdf.svg)](https://pypi.org/project/enoncepdf/)
[![Python](https://img.shields.io/pypi/pyversions/enoncepdf.svg)](https://pypi.org/project/enoncepdf/)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/antnardo/enoncepdf/blob/main/LICENSE)

Take a part of an exam paper in PDF — « Partie II », « questions 1 to 10 » — and get
what to keep of each page: the **page** and the **trim**, without headers, footers or
line numbers. Find the questions of any PDF, too.

*Énoncé* is French for the statement of an exam problem. The package reads the
conventions of French exam papers — « Partie Physique », « Q 7. », « □ – 12. »,
« I.A.1) » — but works from typography and repetition, on any PDF with text.

## The goal

A teacher builds a new assignment from parts of past papers. For each part, they
need to know which pages it covers and how much to cut from each edge of each page,
so that the slices show the part and nothing else: not the header that repeats the
name of the competition, not the « Page 3/12 » footer, not the line numbers in the
margin, not the end of the previous part nor the start of the next.

Doing it by hand means opening the PDF, measuring, and trying again. enoncepdf does it
from a description as one would say it:

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

Each line is a page and its trim: what to cut from the left, bottom, right and top, in
cm — the order of the `trim` key of graphicx. That is the output of the package; how
you write it is yours to choose (a table, JSON, `\includegraphics` lines, the command
of your own class).

## The means

1. **Read the page.** Every character, with its position, its font and its size, and
   the ink of the page (what the text alone does not show: figures, rules, logos).
   What nobody sees on the page — text clipped away, white on white, outside the page
   — is left out.
2. **Find the margins.** A header or a footer is what repeats at the same place from
   page to page, or what reads « Page 3/12 »; line numbers are small numbers in a
   column beside the text. What lies between them is the **body** of the page.
3. **Find the structure.** Headings are bold, or larger, or « Partie … »; their level
   comes from the shape of their number (`I`, `I.A`, `I.A.1` or `1`, `1.1`, `1.1.1`).
   Questions start with their number at the size of the running text, and follow one
   another.
4. **Crop.** A selection — a part, a range of questions, pages — becomes two positions
   in the flow of the document. On each page in between, the body is kept, then
   tightened on the ink. All the crops of one selection have the same width, so that
   stacked slices keep one scale.

Everything is read through pdfium (`pypdfium2`); the package is MIT-licensed, with no
AGPL dependency.

## Installation

```bash
pip install enoncepdf
```

Python 3.11 or later. Dependencies: pypdfium2, numpy, Pillow; on Python 3.13 and later,
latexdetok, to read LaTeX sources (see [Compiled statements](#compiled-statements)).

## Command line

```bash
enoncepdf structure subject.pdf                      # headings, questions, margins found
enoncepdf crop subject.pdf --part II                 # page and trim of each page of part II
enoncepdf crop subject.pdf --questions Q1-10 --sheet crops.png
```

`crop` takes one selection:

| Option | Extract |
| --- | --- |
| `--part II`, `--part "Partie Physique"` | from the heading to the next one of the same level |
| `--within "Partie Physique"` | look for the part inside another, when a number comes back |
| `--without-heading` | leave the heading line out |
| `--intro` | only the text that opens the part, up to its first heading |
| `--questions 1-10`, `--questions Q1-Q10` | from question 1 to whatever follows question 10 |
| `--pages 3-9` | the body of whole pages |

and prints, by default, one line per page:

```text
page 2   L=1.23cm B=1.72cm R=1.88cm U=26.25cm
page 3   L=1.23cm B=2.36cm R=1.88cm U=1.98cm
page 4   L=1.23cm B=18.52cm R=1.88cm U=2.05cm
```

Each value is what to cut from that edge. On page 2, the kept band runs from 26.25 cm
below the top to 1.72 cm above the bottom: question 1, at the bottom of the page.

The same crops, written otherwise:

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

A template is a Python format string (literal braces doubled), with these fields:

| Field | Value |
| --- | --- |
| `{page}` | the page, from 1 |
| `{left}`, `{bottom}`, `{right}`, `{top}` | the trim of each edge, in cm |
| `{trim}` | the four, as graphicx reads them: `1.23cm 1.72cm 1.88cm 26.25cm` |
| `{width}`, `{height}` | the size of the kept area, in cm |
| `{file}` | `--file`, or the name of the PDF without `.pdf` |

The other commands: `blocks subject.pdf 5` lists the bands of ink of page 5 and crops
some of them (`--from 2 --to 4`), when the structure is not recognised; `sheet` draws
the pages as thumbnails; `numbering` gives the patterns of the numbers (`{R}.{A} -`,
`Q {1}.`) and where questions restart at 1.

## Python

```python
from enoncepdf import SelectionError, Statement

with Statement("subject.pdf") as statement:
    for heading in statement.headings:
        print(heading.level, heading.label, heading.text, heading.page)

    crops = statement.crop(questions=(1, 10))
    for crop in crops:
        print(crop.page, crop.trim_cm)         # (left, bottom, right, top), cm
    print(statement.format(crops))             # \includegraphics lines
    print(statement.format(crops, r"\myinclude[{page}]{{{trim}}}{{{file}}}"))
    statement.contact_sheet(crops).save("crops.png")

    try:
        statement.crop("2.1")                  # a « 2.1 » in each of two parts
    except SelectionError as error:
        print(error)                           # lists both, suggests within=
    statement.crop("2.1", within="Partie Physique")
```

`Statement.crop` takes one selection — a part (`"II"`, `"Partie Physique"`, a piece of
a heading, a `Heading`), `questions=(first, last)` or `pages=(first, last)`, or nothing
for the whole document — with `with_heading`, `intro` and `within`. A selection that
names nothing, or several headings, raises `SelectionError`, whose message lists what
was found. All coordinates are in bp (1/72 in) from the top left of the page, pages
numbered from 1.

The full reference is [docs/DOC.md](docs/DOC.md).

## Finding questions

The questions of a paper are found by `Statement.questions`. For any other PDF — a
model answer, a student's typed work —, `locate` reads them from their numbers alone,
on lines read by `PdfiumDocument`:

```python
from enoncepdf import PdfiumDocument, locate, match

document = PdfiumDocument("answer.pdf")
lines = [line for page in range(1, document.page_count + 1) for line in document.lines(page)]
questions = locate(lines)
for q in questions:
    print(q.part, q.ref, q.label, q.page, q.box)

match("Q12", questions)          # the question « Q12 » names, if any
```

The forms recognised are « 12) », « 12. », « 12 — », « Q12 », « Q 12. »,
« Question 12 : », « □ – 12. », « I.A.1) », « 1.a) ». Section numbers and quantities
(« Q3 désigne la charge… ») are left out: only the longest increasing run of numbers is
kept, part by part.

## Compiled statements

Once the crops are pasted into a new assignment and compiled, where do its questions
fall in its PDF? Neither file says it: the source holds inclusions, not questions, and
a trimmed page keeps in the PDF the text its trim hides. `CompiledStatement` answers it:
it reads the inclusions in the source, the questions in the visible part of each
included page, and places them in the compiled PDF through SyncTeX, problem by problem
(each `\section` opens one). A program that shows the statement beside a student's
answer, or that links a marking scheme to it, needs this.

```python
from enoncepdf import INCLUSION_COMMANDS, CompiledStatement

statement = CompiledStatement("assignment.tex", commands=(*INCLUSION_COMMANDS, "myinclude"))
for found in statement.questions():
    print(found.problem, found.question.ref, found.question.page, round(found.top, 3))
```

It needs the source, the PDF, the SyncTeX file (`-synctex=1`) and the log of the
compilation, and latexdetok (Python 3.13 or later). The inclusions read are
`\includegraphics` and `\includepdf`; name in `commands` any command of your own that
takes graphicx's options (`page`, `trim`, `scale`) and a file.

## Limits

- A scanned PDF without text has no lines: margins, headings and questions are not
  found; crops of pages and blocks still work, on the ink.
- A character whose font has no Unicode mapping (in some math fonts) is not read:
  « erf(χ) » may read « erf( ) ».
- Headings are recognised in French and English papers (« Partie », « Part »); in other
  languages, when they are numbered and bold.
- Pages turned by a `/Rotate` entry are read unturned.
- `Statement` keeps its file open and must not be shared between threads; pdfium is
  not thread-safe either. `PdfiumDocument` opens and closes the file at each call.

## Development

```bash
uv sync --group dev
uv run ruff format src tests examples scripts
uv run ruff check src tests examples scripts
uv run mypy
uv run pytest -q
```

The tests draw their papers with reportlab. `scripts/survey.py` runs the analyses over
a list of real PDFs and compares two versions of the package.

## License

MIT — see [LICENSE](LICENSE).
