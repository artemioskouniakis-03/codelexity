from collections import defaultdict
from dataclasses import dataclass

from codelexity.languages.base import LanguageAnalyzer, walk_leaves

DEFAULT_MIN_TOKENS = 50

# A bucket this large is essentially always boilerplate (license headers, generated
# scaffolding, a common import block) rather than meaningful duplication - verifying it
# pairwise would be O(k^2) token comparisons for no useful signal. Skipped buckets are
# rare in practice; this is a safety cap, not the common case.
MAX_BUCKET_SIZE = 200

_ROLLING_BASE = 1_000_003
_ROLLING_MOD = (1 << 61) - 1  # Mersenne prime - standard modulus for polynomial rolling hashes

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


def _rolling_hashes(ids: list[int], size: int) -> list[int]:
    """Polynomial rolling hash of every `size`-length window over `ids`, computed in
    O(len(ids)) total rather than O(len(ids) * size) - each window updates the previous
    one's hash in O(1) (drop the outgoing token, add the incoming one) instead of
    re-joining and re-hashing `size` tokens from scratch on every single shift, which
    dominated runtime on large files (a 50-token re-hash for every one of tens of
    thousands of positions in a big file adds up fast)."""
    n = len(ids)
    if n < size:
        return []
    high_power = pow(_ROLLING_BASE, size - 1, _ROLLING_MOD)
    windows = [0] * (n - size + 1)
    h = 0
    for i in range(size):
        h = (h * _ROLLING_BASE + ids[i]) % _ROLLING_MOD
    windows[0] = h
    for start in range(1, n - size + 1):
        h = (h - ids[start - 1] * high_power) % _ROLLING_MOD
        h = (h * _ROLLING_BASE + ids[start + size - 1]) % _ROLLING_MOD
        windows[start] = h
    return windows


def find_duplicate_blocks(
    file_tokens: dict[str, list[Token]],
    min_tokens: int = DEFAULT_MIN_TOKENS,
) -> list[CloneRegion]:
    """Token-shingling clone detection (PMD-CPD/jscpd style): hash a sliding window of
    normalized tokens per file, verify hash-bucket collisions token-for-token, and merge
    overlapping matches between the same file pair into one region."""
    token_id: dict[str, int] = {}
    ids_by_file: dict[str, list[int]] = {}
    for file, tokens in file_tokens.items():
        ids = []
        for t in tokens:
            i = token_id.get(t.normalized)
            if i is None:
                i = token_id[t.normalized] = len(token_id)
            ids.append(i)
        ids_by_file[file] = ids

    buckets: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for file, ids in ids_by_file.items():
        for start, h in enumerate(_rolling_hashes(ids, min_tokens)):
            buckets[h].append((file, start))

    raw_matches: list[tuple[str, int, str, int]] = []
    for occurrences in buckets.values():
        if len(occurrences) < 2 or len(occurrences) > MAX_BUCKET_SIZE:
            continue
        for i in range(len(occurrences)):
            for j in range(i + 1, len(occurrences)):
                file_a, start_a = occurrences[i]
                file_b, start_b = occurrences[j]
                if file_a == file_b and start_a == start_b:
                    continue
                ids_a = ids_by_file[file_a][start_a : start_a + min_tokens]
                ids_b = ids_by_file[file_b][start_b : start_b + min_tokens]
                if ids_a == ids_b:  # verifies the hash match - rolling hash collisions are possible
                    raw_matches.append((file_a, start_a, file_b, start_b))

    # Grow each match forward token-by-token while both streams keep agreeing, then dedupe
    # matches that are subsumed by a longer, already-grown match starting at/before them.
    grown: list[tuple[str, int, str, int, int]] = []
    for file_a, start_a, file_b, start_b in raw_matches:
        ids_a, ids_b = ids_by_file[file_a], ids_by_file[file_b]
        length = min_tokens
        while (
            start_a + length < len(ids_a)
            and start_b + length < len(ids_b)
            and ids_a[start_a + length] == ids_b[start_b + length]
        ):
            length += 1
        grown.append((file_a, start_a, file_b, start_b, length))

    # Subsumption only matters within the same (file_a, file_b) pair, so grouping first
    # turns one global O(m^2) check into many much smaller ones - a large repo can have
    # thousands of raw matches spread across hundreds of distinct file pairs.
    by_pair: dict[tuple[str, str], list[tuple[str, int, str, int, int]]] = defaultdict(list)
    for match in grown:
        by_pair[(match[0], match[2])].append(match)

    kept: list[tuple[str, int, str, int, int]] = []
    for pair_matches in by_pair.values():
        pair_matches.sort(key=lambda m: -m[4])
        pair_kept: list[tuple[str, int, str, int, int]] = []
        for match in pair_matches:
            _, start_a, _, start_b, length = match
            subsumed = any(
                k[1] <= start_a and k[3] <= start_b and k[1] + k[4] >= start_a + length for k in pair_kept
            )
            if not subsumed:
                pair_kept.append(match)
        kept.extend(pair_kept)

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
