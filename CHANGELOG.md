# Changelog

## 0.1.0 — 2026-08-19

Initial release.

- Halstead metrics, McCabe cyclomatic complexity and the Coleman-Oman maintainability index, per module.
- Package-level maintainability score, weighted by Katz centrality and module size.
- Interactive dependency graph (`--plot`), nodes coloured by maintainability.
- JSON output (`--json`) with per-module detail and aggregate analytics.
- `--include-only` / `--exclude` filtering, and `--absolute` to keep full paths.
