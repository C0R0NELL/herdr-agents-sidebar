#!/usr/bin/env python3
"""Run isolated repository checks; never inspect a user's live Herdr state."""
from pathlib import Path
import sys
import unittest


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    if not suite.countTestCases():
        print("No tests discovered; repository validation cannot pass.", file=sys.stderr)
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
