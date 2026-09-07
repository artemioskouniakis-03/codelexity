import logging
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from codelexity.cocomo import ProjectType, estimate
from codelexity.graph import create_graph, maintainability
from codelexity.models import Language
from codelexity.multi_lang import analyze_package_multi_lang
from codelexity.plot import create_viz
from codelexity.report import build_report
from codelexity.scoring import score_analysis

# Configure logging once so INFO-level progress messages actually reach a handler and show
# up in `docker logs` (or the terminal, running natively). Streamlit reruns this whole
# script on every interaction; basicConfig() is a no-op if the root logger already has a
# handler, so this stays safe across reruns.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

GRAPH_HTML_NAME = "codelexity.html"
REPORT_HTML_NAME = "codelexity_report.html"

# When running via docker-compose, the target folder is bind-mounted read-only to
# /workspace (see docker-compose.yml) and CODELEXITY_DEFAULT_PATH is set to match, so the
# field below defaults to it. Running natively (not in Docker), this env var is unset and
# the field falls back to the current directory, same as before.
DEFAULT_REPO_PATH = os.environ.get("CODELEXITY_DEFAULT_PATH", ".")

st.title("Codelexity")

repo_path = st.text_input("Repository path", value=DEFAULT_REPO_PATH)
depth = st.number_input("Component grouping depth", min_value=0, value=1, step=1)

col1, col2 = st.columns(2)
with col1:
    include_langs = st.multiselect(
        "Include languages (empty = all)", options=[lang.value for lang in Language], default=[]
    )
with col2:
    exclude_paths = st.text_input("Exclude paths (comma-separated)", value="node_modules,.venv,bin,dist,build")

project_type = st.selectbox("COCOMO project type", options=[t.value for t in ProjectType], index=0)


@contextmanager
def timed_step(status, label: str):
    """Logs and displays `label`, then `label - done in Xs` when the block exits -
    the per-step timer the UI and docker logs both show."""
    t0 = time.monotonic()
    status.write(f"{label}...")
    logger.info("%s...", label)
    yield
    elapsed = time.monotonic() - t0
    status.write(f"{label} - done in {elapsed:.2f}s")
    logger.info("%s - done in %.2fs", label, elapsed)


if st.button("Run Analysis", type="primary"):
    status = st.status("Analyzing...", expanded=True)
    try:
        overall_start = time.monotonic()
        root = Path(repo_path).resolve()
        exclude = tuple(p.strip() for p in exclude_paths.split(",") if p.strip())
        logger.info("Starting analysis of %s (exclude=%s, languages=%s)", root, exclude, include_langs or "all")

        parse_label = f"Parsing files under `{root}` (exclude: {', '.join(exclude) or 'none'})"
        with timed_step(status, parse_label):
            progress_bar = st.progress(0.0)
            progress_text = st.empty()

            def on_parse_progress(done: int, total: int) -> None:
                progress_bar.progress(done / total if total else 1.0)
                progress_text.write(f"{done}/{total} files parsed")

            analysis = analyze_package_multi_lang(
                root,
                component_depth=int(depth),
                exclude=exclude,
                languages=tuple(include_langs),
                on_parse_progress=on_parse_progress,
            )
            logger.info(
                "Parsed %d files (%d units, %d LOC); %d unsupported, %d with parse errors",
                len(analysis.files),
                len(analysis.units),
                analysis.total_loc,
                len(analysis.unsupported_files),
                len(analysis.unparsed_files),
            )
            status.write(
                f"{len(analysis.files)} files, {len(analysis.units)} units, {analysis.total_loc} LOC "
                f"({len(analysis.unsupported_files)} unsupported, {len(analysis.unparsed_files)} parse errors)."
            )

        with timed_step(status, "Scoring metrics"):
            scores = score_analysis(analysis)
            logger.info("Overall score: %.2f (%d stars)", scores.overall_raw, scores.overall_stars)

        with timed_step(status, "Estimating COCOMO effort"):
            kloc = analysis.total_loc / 1000
            cocomo_result = estimate(kloc, ProjectType(project_type))
            logger.info("COCOMO estimate: %s", cocomo_result)

        with timed_step(status, "Rendering dependency graph"):
            # Existing dependency graph, unchanged - reused by reference from the report.
            legacy_data = {
                "analytics": {"total_lines": analysis.total_loc},
                "modules": {
                    f.file: {
                        "imports": [],
                        "total_lines": f.loc,
                        "maintainability_index": 100.0,
                    }
                    for f in analysis.files
                },
            }
            graph = create_graph(legacy_data)
            legacy_data["analytics"]["maintainability_index"] = maintainability(graph)
            create_viz(legacy_data, graph, GRAPH_HTML_NAME)

        with timed_step(status, "Building HTML report"):
            generated_at = datetime.now(UTC).isoformat()
            html = build_report(analysis, scores, cocomo_result, GRAPH_HTML_NAME, generated_at, str(root))
            Path(REPORT_HTML_NAME).write_text(html, encoding="utf-8")

        elapsed = time.monotonic() - overall_start
        logger.info("Analysis complete in %.2fs", elapsed)
        status.update(label=f"Analysis complete in {elapsed:.2f}s", state="complete", expanded=False)

        st.success("Analysis complete.")
        st.components.v1.html(html, height=900, scrolling=True)
        st.download_button("Download report", data=html, file_name=REPORT_HTML_NAME, mime="text/html")
    except Exception as exc:  # noqa: BLE001 - UI boundary: last line before a raw Streamlit traceback
        logger.exception("Analysis failed")
        status.update(label="Analysis failed", state="error")
        st.error(str(exc))
