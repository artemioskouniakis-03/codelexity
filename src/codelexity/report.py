import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from codelexity.findings import all_findings
from codelexity.models import AnalysisResult
from codelexity.scoring import ScoreReport, score_by_language
from codelexity.thresholds import volume_stars

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _to_json_script(value) -> Markup:
    """JSON for embedding inside a <script> block. `</` is escaped so a value containing
    it (unlikely here - file paths - but not guaranteed) can never prematurely close the
    surrounding script tag."""
    return Markup(json.dumps(value).replace("</", "<\\/"))


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tojson_script"] = _to_json_script
    return env


def build_report(
    analysis: AnalysisResult,
    scores: ScoreReport,
    cocomo: dict,
    graph_fragment,
    generated_at: str,
    repo_path: str,
    graph_legend: tuple[tuple[str, str], ...] = (),
    exclude_tests: bool = True,
) -> str:
    """Pure string-in/string-out - no file I/O, no datetime.now() inside. The caller
    writes the returned string to disk. `graph_fragment` is a
    dependency_graph.GraphFragment (head extras + body content) embedded directly into
    this page's own document, rather than through a nested iframe - see
    dependency_graph.render_graph_fragment's docstring for why a nested iframe rendered
    blank. `graph_legend` is dependency_graph.FileGraph.legend (component name, hex
    color) pairs - only meaningful for the file-level view; pass () for the
    component-level view, where each node's own label already names it."""
    kloc = analysis.total_loc / 1000
    _, volume_size_label = volume_stars(kloc)
    template = _env().get_template("report.html.j2")
    return template.render(
        repo_path=repo_path,
        generated_at=generated_at,
        analysis=analysis,
        scores=scores,
        cocomo=cocomo,
        graph_head=graph_fragment.head,
        graph_body=graph_fragment.body,
        graph_legend=graph_legend,
        kloc=round(kloc, 2),
        volume_label=volume_size_label,
        exclude_tests=exclude_tests,
        findings=all_findings(analysis),
        language_scores=score_by_language(analysis),
        # System / Unit / Architecture Level grouping, in that order - confirmed by the
        # user. Volume has no MetricScore (it's a single repo-wide KLOC value, not
        # aggregated over units/files/components like the others) so it's listed with
        # score=None; the template renders it with scores.volume_raw/volume_stars instead.
        metric_levels=[
            (
                "System Level Metrics",
                [
                    ("Volume", None, "Codebase size (KLOC) - COCOMO-informed, larger codebases score lower"),
                    ("Duplication", scores.duplication, "% of code found in duplicated blocks"),
                ],
            ),
            (
                "Unit Level Metrics",
                [
                    ("Unit Size", scores.unit_size, "Lines of code per function/method"),
                    ("Unit Complexity", scores.unit_complexity, "McCabe cyclomatic complexity per function/method"),
                ],
            ),
            (
                "Architecture Level Metrics",
                [
                    ("Module Coupling", scores.module_coupling, "Incoming references (fan-in) per file"),
                    (
                        "Component Independence",
                        scores.component_independence,
                        "Cross-component coupling (Martin's Instability)",
                    ),
                ],
            ),
        ],
    )
