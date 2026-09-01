import importlib.machinery
import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

loader = importlib.machinery.SourceFileLoader("observer", str(Path(__file__).parents[1] / "platform-observer.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
observer = importlib.util.module_from_spec(spec)
loader.exec_module(observer)


class ObserverTests(unittest.TestCase):
    def test_managed_products_are_inactive_placeholders(self):
        registry = json.loads((Path(__file__).parents[3] / "config/platform/managed-apps.v1.json").read_text())
        apps = {app["id"]: app for app in registry["apps"]}
        for app_id in ("balne", "pevento", "leso-coffee"):
            app = apps[app_id]
            self.assertFalse(app["enabled"])
            self.assertEqual(app["configuration_status"], "pending_configuration")
            self.assertIsNone(app["public_url"])
            self.assertIsNone(app["release"])
            self.assertIsNone(app["health_check"])
            self.assertEqual(app["log_sources"], [])

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

    def test_pending_app_has_no_runtime_configuration_in_snapshot(self):
        app = observer.app_observation({
            "id": "pevento", "display_name": "Pevento", "enabled": False,
            "configuration_status": "pending_configuration", "public_url": None,
            "release": None, "health_check": None,
        })
        self.assertEqual(app["configuration_status"], "pending_configuration")
        self.assertFalse(app["enabled"])
        self.assertEqual(app["health"], {"status": "not_configured"})
        self.assertIsNone(app["public_url"])
        self.assertIsNone(app["release"])

    def test_atomic_write_produces_parseable_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "observation.json"
            with patch.object(observer.os, "chown") as chown:
                observer.atomic_write(output, {"schema": "test"})
            self.assertEqual(json.loads(output.read_text())["schema"], "test")
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o640)
            self.assertEqual(stat.S_IMODE(output.parent.stat().st_mode), 0o750)
            self.assertEqual(chown.call_args_list[0], call(output.parent, 0, observer.PORTAL_GID))
            self.assertEqual(chown.call_args_list[1].args[1:], (0, observer.PORTAL_GID))


if __name__ == "__main__":
    unittest.main()
