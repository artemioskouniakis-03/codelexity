from dataclasses import dataclass, field
from enum import StrEnum


class Language(StrEnum):
    PYTHON = "python"
    CSHARP = "csharp"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"  # also covers TSX (React) and Angular - both are TypeScript files


@dataclass(frozen=True, slots=True)
class UnitMetric:
    file: str  # posix path, relative to analysis root
    qualified_name: str  # e.g. "OrderService.process_refund"
    kind: str  # "function" | "method" | "arrow" | "constructor" | "local_function"
    language: Language
    start_line: int
    end_line: int
    loc: int  # this unit's own LOC
    complexity: int  # McCabe, excluding nested units' own branches


@dataclass(frozen=True, slots=True)
class FileMetric:
    file: str
    language: Language
    loc: int  # file's total LOC
    incoming_references: int  # fan-in: distinct files/modules importing this one
    duplicate_loc: int  # LOC in this file covered by a detected clone (raw count, not %)
    component: str  # assigned component name at the requested depth


@dataclass(frozen=True, slots=True)
class ComponentMetric:
    name: str  # e.g. "src/orders" for depth=1; "." for the whole-repo component at depth=0
    depth: int
    loc: int
    file_count: int
    efferent: int  # Martin's Ce: cross-component outgoing references
    afferent: int  # Martin's Ca: cross-component incoming references
    independence_score: float  # 1 - Ce/(Ce+Ca); 1.0 when Ce+Ca == 0 (isolated = max independent)
    files: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DuplicateBlock:
    file_a: str
    lines_a: tuple[int, int]
    file_b: str
    lines_b: tuple[int, int]
    token_length: int


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    total_loc: int  # whole-analysis LOC (Volume/KLOC input)
    units: tuple[UnitMetric, ...]
    files: tuple[FileMetric, ...]
    components: tuple[ComponentMetric, ...]
    duplicate_blocks: tuple[DuplicateBlock, ...]
    unparsed_files: tuple[str, ...]  # parsed with tree-sitter errors - results may be incomplete
    unsupported_files: tuple[str, ...]  # no registered analyzer for this extension
