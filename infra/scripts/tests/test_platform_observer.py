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
    def test_balne_is_an_active_fixed_inventory_entry(self):
        registry = json.loads((Path(__file__).parents[3] / "config/platform/managed-apps.v1.json").read_text())
        apps = {app["id"]: app for app in registry["apps"]}
        balne = apps["balne"]
        self.assertTrue(balne["enabled"])
        self.assertEqual(balne["public_url"], "https://balne.com.ar")
        self.assertNotIn("health_check", balne)
        self.assertEqual(balne["log_sources"], [])

    def test_other_managed_products_remain_inactive_placeholders(self):
        registry = json.loads((Path(__file__).parents[3] / "config/platform/managed-apps.v1.json").read_text())
        apps = {app["id"]: app for app in registry["apps"]}
        for app_id in ("pevento", "leso-coffee"):
            app = apps[app_id]
            self.assertFalse(app["enabled"])
            self.assertEqual(app["configuration_status"], "pending_configuration")
            self.assertIsNone(app["public_url"])
            self.assertIsNone(app["release"])
            self.assertIsNone(app["health_check"])
            self.assertEqual(app["log_sources"], [])

    def test_balne_registry_health_check_override_cannot_redirect_probe(self):
        app = {
            "id": "balne", "display_name": "Balne", "enabled": True,
            "public_url": "https://balne.com.ar", "release": None,
            "health_check": {"url": "http://127.0.0.1:9999/untrusted", "timeout_seconds": 1, "expected_status": 418},
        }
        with patch.object(observer, "health_check", return_value={"status": "healthy"}) as health, \
             patch.object(observer, "systemd_state", return_value="active") as state, \
             patch.object(observer, "repository_revision", return_value="a" * 40) as revision:
            result = observer.app_observation(app)
        self.assertEqual(result["health"], {"status": "healthy"})
        self.assertEqual(result["systemd_state"], "active")
        self.assertEqual(result["release"], {"commit": "a" * 40})
        health.assert_called_once_with(observer.RUNTIME_SOURCES["balne"]["health_check"])
        self.assertEqual(health.call_args.args[0], {"url": "http://127.0.0.1:3000/", "timeout_seconds": 5, "expected_status": 200})
        self.assertNotEqual(health.call_args.args[0], app["health_check"])
        state.assert_called_once_with("balne-landing.service")
        revision.assert_called_once_with(Path("/srv/balne-landing"))

    def test_runtime_probes_use_fixed_argv_and_validate_output(self):
        with patch.object(observer.subprocess, "run") as run:
            run.side_effect = [
                type("Result", (), {"stdout": "active\n"})(),
                type("Result", (), {"stdout": "a" * 40 + "\n"})(),
            ]
            self.assertEqual(observer.systemd_state("balne-landing.service"), "active")
            self.assertEqual(observer.repository_revision(Path("/srv/balne-landing")), "a" * 40)
        self.assertEqual(run.call_args_list[0].args[0], [observer.SYSTEMCTL, "show", "--property=ActiveState", "--value", "balne-landing.service"])
        self.assertEqual(run.call_args_list[1].args[0], [observer.GIT, "-C", "/srv/balne-landing", "rev-parse", "--verify", "HEAD"])
        self.assertTrue(all(call.kwargs["timeout"] == 5 for call in run.call_args_list))

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
