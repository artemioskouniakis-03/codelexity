import logging
import os
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

if st.button("Run Analysis", type="primary"):
    try:
        with st.spinner("Analyzing..."):
            root = Path(repo_path).resolve()
            exclude = tuple(p.strip() for p in exclude_paths.split(",") if p.strip())

            analysis = analyze_package_multi_lang(
                root,
                component_depth=int(depth),
                exclude=exclude,
                languages=tuple(include_langs),
            )
            scores = score_analysis(analysis)
            kloc = analysis.total_loc / 1000
            cocomo_result = estimate(kloc, ProjectType(project_type))

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

            generated_at = datetime.now(UTC).isoformat()
            html = build_report(analysis, scores, cocomo_result, GRAPH_HTML_NAME, generated_at, str(root))
            Path(REPORT_HTML_NAME).write_text(html, encoding="utf-8")

        st.success("Analysis complete.")
        st.components.v1.html(html, height=900, scrolling=True)
        st.download_button("Download report", data=html, file_name=REPORT_HTML_NAME, mime="text/html")
    except Exception as exc:  # noqa: BLE001 - UI boundary: last line before a raw Streamlit traceback
        logger.exception("Analysis failed")
        st.error(str(exc))
