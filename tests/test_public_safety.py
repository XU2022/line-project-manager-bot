from __future__ import annotations

import re
import unittest
from importlib.resources import files
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".md", ".py", ".sql", ".toml", ".json", ".yaml", ".yml",
    ".conf", ".service", ".timer", ".example",
}


class PublicSafetyTest(unittest.TestCase):
    def test_exported_schema_matches_packaged_schema(self) -> None:
        exported = (ROOT / "migrations" / "schema.sql").read_text(encoding="utf-8")
        packaged = files("line_project_manager").joinpath("schema.sql").read_text(
            encoding="utf-8"
        )
        self.assertEqual(exported.rstrip(), packaged.rstrip())

    def test_public_files_contain_no_obvious_runtime_secrets(self) -> None:
        patterns = {
            "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "real-looking LINE id": re.compile(r"\b[UCR][0-9a-fA-F]{32}\b"),
            "macOS home path": re.compile(r"/Users/[^/\s]+/"),
            "Linux home path": re.compile(r"/home/[^/\s]+/"),
        }
        violations: list[str] = []
        for path in ROOT.rglob("*"):
            if path.resolve() == Path(__file__).resolve():
                continue
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix not in TEXT_SUFFIXES and path.name not in {"README.md", ".gitignore"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in patterns.items():
                if pattern.search(content):
                    violations.append(f"{path.relative_to(ROOT)}: {label}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
