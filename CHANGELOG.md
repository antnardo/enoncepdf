# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-10-18

The output of a crop is its page and its trim; how they are written is the caller's.

### Changed

- `Crop.format` and `Statement.format` write crops with any `str.format` template
  (fields `{page}`, `{left}`, `{bottom}`, `{right}`, `{top}`, `{trim}`, `{width}`,
  `{height}`, `{file}`); the default, `GRAPHICX_TEMPLATE`, is a plain
  `\includegraphics` line. They replace `Crop.latex` and `Statement.latex`, which wrote
  a fixed command and chose a scale for slices taller than a page.
- `Crop.trim_option` is removed: the `{trim}` field gives the same numbers.
- On the command line, `crop` prints the page and the trim of each crop, in cm, and
  takes `--json`, `--latex` or `--template`, with `--file` for `{file}`; `trims` is
  merged into it. `blocks --from … --to …` takes the same options.
- `CompiledStatement` and `inclusions` read `\includegraphics` and `\includepdf`
  (`INCLUSION_COMMANDS`); other inclusion commands are named with `commands=`.

### Added

- `Crop.width_cm` and `Crop.height_cm`.

## [0.1.0] — 2026-10-18

First public release.

### Added

- `Statement`: headings and their levels, questions and sub-questions, margins
  (headers, footers, line numbers, repeated rules), and crops of a part, a range of
  questions, pages or blocks, with their trims in cm.
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

[0.2.0]: https://github.com/antnardo/enoncepdf/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/antnardo/enoncepdf/releases/tag/v0.1.0
