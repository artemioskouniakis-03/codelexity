from pathlib import Path

from codelexity.languages.base import LanguageAnalyzer
from codelexity.languages.csharp_lang import CSharpAnalyzer
from codelexity.languages.java_lang import JavaAnalyzer
from codelexity.languages.javascript_lang import JavaScriptAnalyzer
from codelexity.languages.python_lang import PythonAnalyzer
from codelexity.languages.typescript_lang import TypeScriptAnalyzer

_ANALYZERS: dict[str, LanguageAnalyzer] = {}


def _register(analyzer: LanguageAnalyzer) -> None:
    for ext in analyzer.file_extensions:
        _ANALYZERS[ext] = analyzer


_register(PythonAnalyzer())
_register(JavaScriptAnalyzer())
_register(TypeScriptAnalyzer(dialect="ts"))
_register(TypeScriptAnalyzer(dialect="tsx"))
_register(JavaAnalyzer())
_register(CSharpAnalyzer())


def analyzer_for(path: Path) -> LanguageAnalyzer | None:
    """Returns the registered analyzer for `path`'s extension, or None if the extension
    is unsupported or its grammar package isn't installed (both cases are treated as
    "unsupported" by the caller - see multi_lang.py's unsupported_files handling)."""
    return _ANALYZERS.get(path.suffix.lower())


def supported_extensions() -> frozenset[str]:
    return frozenset(_ANALYZERS)
