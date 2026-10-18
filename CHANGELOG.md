# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-18

First public release.

### Added

- `Statement`: headings and their levels, questions and sub-questions, margins
  (headers, footers, line numbers, repeated rules), and crops of a part, a range of
  questions, pages or blocks, as `\includetoolargegraphics` lines or trims in cm.
- `NumberingAnalysis` and `pattern`: the numbering profile of a statement or of one
  of its parts.
- `locate`, `match`: questions found at their number in any lines, keeping the
  longest increasing run, part by part.
- `PdfiumDocument`: lines as pdfium breaks them, restricted to an area, with nothing
  held open between calls.
- `CompiledStatement`: the questions of a LaTeX statement compiled from crops, placed
  in its PDF from its source, log and SyncTeX.
- `ContactSheet`: thumbnails of pages and crops.
- The `enoncepdf` command: `structure`, `crop`, `trims`, `blocks`, `sheet`,
  `numbering`.
- Font style read from the font name (TeX names included), the descriptor flags and
  the embedded font program.
- `scripts/survey.py`, to measure a change on a set of real papers.

[0.1.0]: https://github.com/antnardo/enoncepdf/releases/tag/v0.1.0
