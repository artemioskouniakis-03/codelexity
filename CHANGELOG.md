# Changelog

## 0.2.1 — 2026-08-19

Fixed bug with `utf-8` encoding 

### Fixed
- Fixed the encoding related bug in reading text files


## 0.2.0 — 2026-08-19

Adding a new metric

### Added
- Introduced another important Halstead metric in the report: Comprehension Time (h)
- Updated the assets to reflect the above

### Fixed
- Fixed the non-rendering images in PyPI

## 0.1.0 — 2026-08-19

Initial release.

- Halstead metrics, McCabe cyclomatic complexity and the Coleman-Oman maintainability index, per module.
- Package-level maintainability score, weighted by Katz centrality and module size.
- Interactive dependency graph (`--plot`), nodes coloured by maintainability.
- JSON output (`--json`) with per-module detail and aggregate analytics.
- `--include-only` / `--exclude` filtering, and `--absolute` to keep full paths.

