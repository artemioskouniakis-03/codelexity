import unittest

from codelexity.dependency_graph import (
    build_component_graph,
    build_file_graph,
    render_graph_fragment,
    render_graph_html,
)
from codelexity.models import AnalysisResult, ComponentMetric, FileMetric, Language


def _analysis() -> AnalysisResult:
    files = (
        FileMetric(
            file="a.py", language=Language.PYTHON, loc=10, incoming_references=1, duplicate_loc=0, component="x"
        ),
        FileMetric(
            file="b.py", language=Language.PYTHON, loc=10, incoming_references=1, duplicate_loc=0, component="y"
        ),
    )
    components = (
        ComponentMetric(
            name="x", depth=1, loc=10, file_count=1, efferent=1, afferent=0, independence_score=0.0, files=("a.py",)
        ),
        ComponentMetric(
            name="y", depth=1, loc=10, file_count=1, efferent=0, afferent=1, independence_score=1.0, files=("b.py",)
        ),
    )
    return AnalysisResult(
        total_loc=20,
        units=(),
        files=files,
        components=components,
        duplicate_blocks=(),
        edges=(("a.py", "b.py"), ("b.py", "a.py")),  # mutual dependency - both directions
        unparsed_files=(),
        unsupported_files=(),
    )


class TestDependencyGraph(unittest.TestCase):
    def test_file_graph_has_both_directed_edges(self):
        file_graph = build_file_graph(_analysis())
        graph = file_graph.graph
        self.assertEqual(set(graph.nodes), {"a.py", "b.py"})
        self.assertTrue(graph.has_edge("a.py", "b.py"))
        self.assertTrue(graph.has_edge("b.py", "a.py"))

    def test_file_graph_legend_covers_every_component_with_distinct_colors(self):
        file_graph = build_file_graph(_analysis())
        self.assertEqual([c for c, _ in file_graph.legend], ["x", "y"])
        colors = [color for _, color in file_graph.legend]
        self.assertEqual(len(colors), len(set(colors)))  # every component gets a distinct color

    def test_file_graph_nodes_are_colored_by_their_component(self):
        file_graph = build_file_graph(_analysis())
        legend = dict(file_graph.legend)
        self.assertEqual(file_graph.graph.nodes["a.py"]["color"], legend["x"])
        self.assertEqual(file_graph.graph.nodes["b.py"]["color"], legend["y"])

    def test_component_graph_aggregates_cross_component_edges(self):
        graph = build_component_graph(_analysis())
        self.assertEqual(set(graph.nodes), {"x", "y"})
        self.assertTrue(graph.has_edge("x", "y"))
        self.assertTrue(graph.has_edge("y", "x"))

    def test_render_graph_html_produces_a_standalone_page(self):
        html = render_graph_html(build_file_graph(_analysis()).graph)
        self.assertIn("<html", html.lower())
        self.assertIn("</html>", html.lower())

    def test_render_graph_fragment_extracts_head_and_body(self):
        fragment = render_graph_fragment(build_file_graph(_analysis()).graph)
        self.assertIn("vis-network", fragment.head)
        self.assertIn("mynetwork", fragment.body)
        # The fragment must not itself contain <html>/<head>/<body> tags - it's meant to
        # be spliced into another page's own document, not stand alone.
        self.assertNotIn("<head>", fragment.head)
        self.assertNotIn("<body>", fragment.body)

    def test_render_graph_fragment_preserves_the_real_script_closing_tag(self):
        fragment = render_graph_fragment(build_file_graph(_analysis()).graph)
        self.assertTrue(fragment.body.rstrip().endswith("</script>") or "</script>" in fragment.body)

    def test_spacious_option_uses_a_longer_spring_length_for_component_graphs(self):
        component_html = render_graph_html(build_component_graph(_analysis()), spacious=True)
        file_html = render_graph_html(build_file_graph(_analysis()).graph, spacious=False)
        self.assertIn("springLength", component_html)
        self.assertNotIn("320", file_html)  # the file-graph preset doesn't use the wide component spacing


if __name__ == "__main__":
    unittest.main()
