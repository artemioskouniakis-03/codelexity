import unittest

from codelexity.duplication import Token, find_duplicate_blocks


def _tokens(pattern: list[str]) -> list[Token]:
    return [Token(normalized=p, line=i + 1) for i, p in enumerate(pattern)]


class TestDuplicateBlocks(unittest.TestCase):
    def test_detects_a_planted_duplicate_across_two_files(self):
        pattern = [str(i) for i in range(60)]  # 60 distinct lines, well above the default 7-line window
        file_tokens = {
            "a.py": _tokens(pattern),
            "b.py": _tokens(["unrelated"] * 5 + pattern),
        }
        blocks = find_duplicate_blocks(file_tokens, min_lines=7)
        self.assertTrue(any(b.file_a in ("a.py", "b.py") and b.file_b in ("a.py", "b.py") for b in blocks))
        self.assertGreaterEqual(blocks[0].line_length, 7)

    def test_no_false_positive_below_min_lines(self):
        file_tokens = {
            "a.py": _tokens(["if", "(", "x", ")", "return"]),
            "b.py": _tokens(["if", "(", "y", ")", "return"]),
        }
        blocks = find_duplicate_blocks(file_tokens, min_lines=7)
        self.assertEqual(blocks, [])

    def test_identical_short_files_below_threshold_are_not_flagged(self):
        file_tokens = {"a.py": _tokens(["ID", "=", "LIT"]), "b.py": _tokens(["ID", "=", "LIT"])}
        blocks = find_duplicate_blocks(file_tokens, min_lines=10)
        self.assertEqual(blocks, [])

    def test_block_of_exactly_min_lines_is_flagged(self):
        pattern = [str(i) for i in range(7)]  # exactly 7 distinct lines
        file_tokens = {"a.py": _tokens(pattern), "b.py": _tokens(pattern)}
        blocks = find_duplicate_blocks(file_tokens, min_lines=7)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].line_length, 7)

    def test_block_one_line_below_min_lines_is_not_flagged(self):
        pattern = [str(i) for i in range(6)]  # only 6 distinct lines - below the 7-line threshold
        file_tokens = {"a.py": _tokens(pattern), "b.py": _tokens(pattern)}
        blocks = find_duplicate_blocks(file_tokens, min_lines=7)
        self.assertEqual(blocks, [])


if __name__ == "__main__":
    unittest.main()
