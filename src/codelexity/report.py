import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from codelexity.findings import all_findings
from codelexity.models import AnalysisResult
from codelexity.scoring import ScoreReport
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
    graph_html: str,
    generated_at: str,
    repo_path: str,
) -> str:
    """Pure string-in/string-out - no file I/O, no datetime.now() inside. The caller
    writes the returned string to disk. `graph_html` is the full standalone dependency
    graph page (see dependency_graph.render_graph_html) - embedded via an iframe's
    srcdoc rather than referenced by path, so it works both as a downloaded file and
    inline in Streamlit (whose st.components.v1.html has no base URL a relative path
    could resolve against)."""
    kloc = analysis.total_loc / 1000
    volume_star_count, volume_size_label = volume_stars(kloc)
    template = _env().get_template("report.html.j2")
    return template.render(
        repo_path=repo_path,
        generated_at=generated_at,
        analysis=analysis,
        scores=scores,
        cocomo=cocomo,
        graph_html=graph_html,
        kloc=round(kloc, 2),
        volume_stars=volume_star_count,
        volume_label=volume_size_label,
        findings=all_findings(analysis),
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
