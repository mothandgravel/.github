"""Protect the dependency direction that keeps the studio replaceable."""

import ast
import unittest
from pathlib import Path


class BoundaryTests(unittest.TestCase):
    def test_views_and_use_cases_do_not_import_pipeline_internals(self):
        package = Path(__file__).resolve().parents[2] / "field_notes_studio"
        files = [
            *package.joinpath("presentation").glob("*.py"),
            *[
                package / name
                for name in (
                    "controller.py",
                    "service.py",
                    "models.py",
                    "repository.py",
                    "processes.py",
                    "preparation_controller.py",
                    "preparation_models.py",
                    "preparation_service.py",
                )
            ],
        ]
        for path in files:
            with self.subTest(file=path.name):
                modules = []
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node, ast.Import):
                        modules.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        modules.append(node.module or "")
                self.assertFalse(any(name.startswith("field_notes_audio") for name in modules))
                if path.parent.name == "presentation":
                    self.assertFalse(
                        any(
                            name in {"sqlite3", "subprocess", "socket", "threading"}
                            or name.startswith("field_notes_studio.pipeline")
                            or name
                            in {
                                "field_notes_studio.preparation",
                                "field_notes_studio.preparation_jobs",
                                "field_notes_studio.preparation_service",
                                "field_notes_studio.preparation_setup",
                            }
                            for name in modules
                        )
                    )
