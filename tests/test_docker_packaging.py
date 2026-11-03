"""Prevent local Python imports from being omitted in the addon image."""

import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "nm_bridge"


class DockerPackagingTests(unittest.TestCase):
    def test_every_transitively_imported_local_module_is_copied_to_image(self):
        """Direct bridge imports alone missed ets_import -> recognition in 5.8.0."""
        local = {path.stem for path in ROOT.glob("*.py")}
        pending = ["bridge"]
        imported = set()
        while pending:
            module = pending.pop()
            if module in imported:
                continue
            imported.add(module)
            tree = ast.parse((ROOT / f"{module}.py").read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    candidate = node.module.split(".", 1)[0]
                    if candidate in local:
                        pending.append(candidate)
                elif isinstance(node, ast.Import):
                    pending.extend(alias.name for alias in node.names if alias.name in local)
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        for module in sorted(imported):
            with self.subTest(module=module):
                self.assertIn(f"COPY {module}.py /app/{module}.py", dockerfile)

    def test_bridge_imports_from_docker_style_flat_module_directory(self):
        """Replicate the /app entry point without launching a server or KNX connection."""
        result = subprocess.run([sys.executable, "-c", "import bridge; import ets_import; import recognition"],
                                cwd=ROOT, capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
