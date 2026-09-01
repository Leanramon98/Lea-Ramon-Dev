import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

loader = importlib.machinery.SourceFileLoader("observer", str(Path(__file__).parents[1] / "platform-observer.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
observer = importlib.util.module_from_spec(spec)
loader.exec_module(observer)


class ObserverTests(unittest.TestCase):
    def test_redact_removes_common_secret_forms(self):
        result = observer.redact("Authorization: Bearer abc.def password=top-secret AKIAABCDEFGHIJKLMNOP")
        self.assertNotIn("abc.def", result)
        self.assertNotIn("top-secret", result)
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", result)

    def test_collects_only_requested_allowlisted_source_and_bounds_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "syslog"
            log.write_text("\n".join(f"line {number}" for number in range(120)))
            original = observer.LOG_SOURCES
            observer.LOG_SOURCES = {"host-system-log": log}
            try:
                logs = observer.collect_logs([{"enabled": True, "log_sources": ["host-system-log", "not-allowed"]}])
            finally:
                observer.LOG_SOURCES = original
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["source"], "host-system-log")
            self.assertEqual(len(logs[0]["lines"]), observer.MAX_LOG_LINES)

    def test_atomic_write_produces_parseable_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "observation.json"
            observer.atomic_write(output, {"schema": "test"})
            self.assertEqual(json.loads(output.read_text())["schema"], "test")


if __name__ == "__main__":
    unittest.main()
