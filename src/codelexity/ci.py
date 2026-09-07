import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from codelexity.cocomo import estimate
from codelexity.dependency_graph import build_file_graph, render_graph_fragment
from codelexity.multi_lang import analyze_package_multi_lang
from codelexity.report import build_report
from codelexity.scoring import ScoreReport, score_analysis

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDE = ("node_modules", ".venv", "bin", "dist", "build", "coverage")

parser = argparse.ArgumentParser(
    prog="codelexity-ci",
    description="Headless multi-language quality analysis for CI. Exits non-zero when the "
    "overall score is below --min-stars, so it can gate a pull request.",
)
parser.add_argument("path", help="Repository path to analyze.")
parser.add_argument("--component-depth", type=int, default=1, help="Folder-depth for component grouping.")
parser.add_argument("--exclude", nargs="+", default=list(DEFAULT_EXCLUDE), help="Path segments to exclude.")
parser.add_argument("--languages", nargs="+", default=[], help="Restrict to these languages (default: all).")
parser.add_argument(
    "--min-stars",
    type=float,
    default=3.0,
    help="Fail (exit 1) if the overall score is below this many stars (default: 3.0).",
)
parser.add_argument("--report", help="Write the HTML report to this path.")
parser.add_argument("--json", dest="json_path", help="Write a machine-readable JSON summary to this path.")


def _summary(analysis, scores: ScoreReport, cocomo_result: dict) -> dict:
    return {
        "overall_stars": scores.overall_stars,
        "overall_raw": round(scores.overall_raw, 2),
        "metrics": {
            "volume": {"stars": scores.volume_stars, "raw_score": round(scores.volume_raw, 2)},
            **{
                name: {"stars": s.stars, "raw_score": round(s.raw_score, 2), "severity_pct": round(s.severity_pct, 1)}
                for name, s in (
                    ("duplication", scores.duplication),
                    ("unit_size", scores.unit_size),
                    ("unit_complexity", scores.unit_complexity),
                    ("module_coupling", scores.module_coupling),
                    ("component_independence", scores.component_independence),
                )
            },
        },
        "cocomo": cocomo_result,
        "total_loc": analysis.total_loc,
        "files_analyzed": len(analysis.files),
        "units": len(analysis.units),
        "unparsed_files": len(analysis.unparsed_files),
        "unsupported_files": len(analysis.unsupported_files),
        "skipped_large_files": len(analysis.skipped_large_files),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parser.parse_args(argv)
    root = Path(args.path).resolve()

    analysis = analyze_package_multi_lang(
        root,
        component_depth=args.component_depth,
        exclude=tuple(args.exclude),
        languages=tuple(args.languages),
    )
    scores = score_analysis(analysis)
    cocomo_result = estimate(analysis.total_loc / 1000)
    summary = _summary(analysis, scores, cocomo_result)

    print(f"Codelexity overall score: {scores.overall_stars} stars ({scores.overall_raw:.2f}/5.5)")
    for name, m in summary["metrics"].items():
        if "severity_pct" in m:
            print(f"  {name}: {m['stars']} stars ({m['raw_score']:.2f}, {m['severity_pct']:.1f}% severity)")
        else:
            print(f"  {name}: {m['stars']} stars ({m['raw_score']:.2f}, {cocomo_result['kloc']} KLOC)")
    print(f"  COCOMO project type: {cocomo_result['project_type']} (derived from codebase size)")

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("Wrote JSON summary to %s", args.json_path)

    if args.report:
        file_graph = build_file_graph(analysis)
        graph_fragment = render_graph_fragment(file_graph.graph)
        html = build_report(
            analysis,
            scores,
            cocomo_result,
            graph_fragment,
            datetime.now(UTC).isoformat(),
            str(root),
            graph_legend=file_graph.legend,
        )
        Path(args.report).write_text(html, encoding="utf-8")
        logger.info("Wrote HTML report to %s", args.report)

    if scores.overall_stars < args.min_stars:
        print(f"FAIL: overall score {scores.overall_stars} stars is below the required {args.min_stars}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
