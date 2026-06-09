"""
[AIQ-933] Guard against duplicate method definitions in backend/database.py.

The `employee_tasks` methods were defined TWICE in the Database class (sets at
~L15932 and ~L16215). Python binds the last definition, so the first set was
silent dead code — and an edit to it would be silently ignored. This guard
fails if ANY class in database.py defines the same method name more than once,
so the bug class can't reappear.

Pure AST parse — no DB, no imports of the module (which conftest mocks).
"""
from __future__ import annotations

import ast
import os
import unittest
from collections import Counter

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.py"
)


class NoDuplicateMethodDefsTests(unittest.TestCase):
    def test_no_class_defines_a_method_twice(self) -> None:
        tree = ast.parse(open(_DB_PATH, encoding="utf-8").read())
        offenders = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names = [
                    n.name
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                dups = {k: v for k, v in Counter(names).items() if v > 1}
                if dups:
                    offenders[node.name] = dups
        self.assertEqual(
            offenders,
            {},
            f"Duplicate method definitions found (last-wins silently shadows the first): {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
