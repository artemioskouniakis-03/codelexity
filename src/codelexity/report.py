from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from codelexity.models import AnalysisResult
from codelexity.scoring import ScoreReport
from codelexity.thresholds import volume_label

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def build_report(
    analysis: AnalysisResult,
    scores: ScoreReport,
    cocomo: dict,
    graph_html_path: str,
    generated_at: str,
    repo_path: str,
) -> str:
    """Pure string-in/string-out - no file I/O, no datetime.now() inside. The caller
    writes the returned string to disk."""
    kloc = analysis.total_loc / 1000
    template = _env().get_template("report.html.j2")
    return template.render(
        repo_path=repo_path,
        generated_at=generated_at,
        analysis=analysis,
        scores=scores,
        cocomo=cocomo,
        graph_html_path=graph_html_path,
        kloc=round(kloc, 2),
        volume_label=volume_label(kloc),
        metric_cards=[
            ("Unit Complexity", scores.unit_complexity, "McCabe cyclomatic complexity per function/method"),
            ("Duplication", scores.duplication, "% of code found in duplicated blocks"),
            ("Module Coupling", scores.module_coupling, "Incoming references (fan-in) per file"),
            (
                "Component Independence",
                scores.component_independence,
                "Cross-component coupling (Martin's Instability)",
            ),
            ("Unit Size", scores.unit_size, "Lines of code per function/method"),
        ],
    )
