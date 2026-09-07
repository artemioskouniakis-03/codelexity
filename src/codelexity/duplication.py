import hashlib
from collections import defaultdict
from dataclasses import dataclass

from codelexity.languages.base import LanguageAnalyzer, walk_leaves

DEFAULT_MIN_TOKENS = 50

_IDENTIFIER_TYPES = frozenset({"identifier", "type_identifier", "property_identifier", "shorthand_property_identifier"})
_LITERAL_TYPES = frozenset(
    {
        "string",
        "string_literal",
        "integer",
        "integer_literal",
        "float",
        "float_literal",
        "number",
        "number_literal",
        "true",
        "false",
        "null",
        "none",
        "concatenated_string",
        "character_literal",
    }
)


@dataclass(frozen=True, slots=True)
class Token:
    normalized: str
    line: int  # 1-indexed source line this token starts on


@dataclass(frozen=True, slots=True)
class CloneRegion:
    file_a: str
    lines_a: tuple[int, int]
    file_b: str
    lines_b: tuple[int, int]
    token_length: int


def tokenize(tree, source: bytes, analyzer: LanguageAnalyzer) -> list[Token]:
    tokens = []
    for leaf in walk_leaves(tree.root_node):
        if not leaf.is_named:
            continue
        text_type = leaf.type
        if text_type in _IDENTIFIER_TYPES:
            norm = "ID"
        elif text_type in _LITERAL_TYPES:
            norm = "LIT"
        elif "comment" in text_type:
            continue
        else:
            norm = text_type
        line = source.count(b"\n", 0, leaf.start_byte) + 1
        tokens.append(Token(normalized=norm, line=line))
    return tokens


def _hash_window(tokens: list[Token], start: int, size: int) -> bytes:
    joined = "|".join(t.normalized for t in tokens[start : start + size])
    return hashlib.blake2b(joined.encode("utf-8"), digest_size=8).digest()


def find_duplicate_blocks(
    file_tokens: dict[str, list[Token]],
    min_tokens: int = DEFAULT_MIN_TOKENS,
) -> list[CloneRegion]:
    """Token-shingling clone detection (PMD-CPD/jscpd style): hash a sliding window of
    normalized tokens per file, verify hash-bucket collisions token-for-token, and merge
    overlapping matches between the same file pair into one region."""
    buckets: dict[bytes, list[tuple[str, int]]] = defaultdict(list)
    for file, tokens in file_tokens.items():
        for start in range(0, max(len(tokens) - min_tokens + 1, 0)):
            buckets[_hash_window(tokens, start, min_tokens)].append((file, start))

    raw_matches: list[tuple[str, int, str, int]] = []
    for occurrences in buckets.values():
        if len(occurrences) < 2:
            continue
        for i in range(len(occurrences)):
            for j in range(i + 1, len(occurrences)):
                file_a, start_a = occurrences[i]
                file_b, start_b = occurrences[j]
                if file_a == file_b and start_a == start_b:
                    continue
                window_a = file_tokens[file_a][start_a : start_a + min_tokens]
                window_b = file_tokens[file_b][start_b : start_b + min_tokens]
                if [t.normalized for t in window_a] == [t.normalized for t in window_b]:
                    raw_matches.append((file_a, start_a, file_b, start_b))

    # Grow each match forward token-by-token while both streams keep agreeing, then dedupe
    # matches that are subsumed by a longer, already-grown match starting at/before them.
    grown: list[tuple[str, int, str, int, int]] = []
    for file_a, start_a, file_b, start_b in raw_matches:
        tokens_a, tokens_b = file_tokens[file_a], file_tokens[file_b]
        length = min_tokens
        while (
            start_a + length < len(tokens_a)
            and start_b + length < len(tokens_b)
            and tokens_a[start_a + length].normalized == tokens_b[start_b + length].normalized
        ):
            length += 1
        grown.append((file_a, start_a, file_b, start_b, length))

    grown.sort(key=lambda m: -m[4])
    kept: list[tuple[str, int, str, int, int]] = []
    for match in grown:
        file_a, start_a, file_b, start_b, length = match
        subsumed = any(
            k[0] == file_a
            and k[2] == file_b
            and k[1] <= start_a
            and k[3] <= start_b
            and k[1] + k[4] >= start_a + length
            for k in kept
        )
        if not subsumed:
            kept.append(match)

    regions = []
    for file_a, start_a, file_b, start_b, length in kept:
        tokens_a, tokens_b = file_tokens[file_a], file_tokens[file_b]
        end_line_a = tokens_a[min(start_a + length - 1, len(tokens_a) - 1)].line
        end_line_b = tokens_b[min(start_b + length - 1, len(tokens_b) - 1)].line
        regions.append(
            CloneRegion(
                file_a=file_a,
                lines_a=(tokens_a[start_a].line, end_line_a),
                file_b=file_b,
                lines_b=(tokens_b[start_b].line, end_line_b),
                token_length=length,
            )
        )
    return regions


def duplicate_loc_per_file(regions: list[CloneRegion]) -> dict[str, set[int]]:
    """Line numbers covered by any clone region, per file. Callers should intersect this
    with the file's Volume-countable lines before treating it as a duplication count."""
    covered: dict[str, set[int]] = defaultdict(set)
    for region in regions:
        covered[region.file_a].update(range(region.lines_a[0], region.lines_a[1] + 1))
        covered[region.file_b].update(range(region.lines_b[0], region.lines_b[1] + 1))
    return covered
