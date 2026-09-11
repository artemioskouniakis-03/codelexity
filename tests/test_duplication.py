import unittest

from codelexity.duplication import Token, find_duplicate_blocks


def _tokens(pattern: list[str]) -> list[Token]:
    return [Token(normalized=p, line=i + 1) for i, p in enumerate(pattern)]


class TestDuplicateBlocks(unittest.TestCase):
    def test_detects_a_planted_duplicate_across_two_files(self):
        pattern = [str(i) for i in range(60)]  # 60 distinct tokens, well above the default 50-window
        file_tokens = {
            "a.py": _tokens(pattern),
            "b.py": _tokens(["unrelated"] * 5 + pattern),
        }
        blocks = find_duplicate_blocks(file_tokens, min_tokens=50)
        self.assertTrue(any(b.file_a in ("a.py", "b.py") and b.file_b in ("a.py", "b.py") for b in blocks))
        self.assertGreaterEqual(blocks[0].token_length, 50)

    def test_no_false_positive_below_min_tokens(self):
        file_tokens = {
            "a.py": _tokens(["if", "(", "x", ")", "return"]),
            "b.py": _tokens(["if", "(", "y", ")", "return"]),
        }
        blocks = find_duplicate_blocks(file_tokens, min_tokens=50)
        self.assertEqual(blocks, [])

    def test_identical_short_files_below_threshold_are_not_flagged(self):
        file_tokens = {"a.py": _tokens(["ID", "=", "LIT"]), "b.py": _tokens(["ID", "=", "LIT"])}
        blocks = find_duplicate_blocks(file_tokens, min_tokens=10)
        self.assertEqual(blocks, [])


if __name__ == "__main__":
    unittest.main()
