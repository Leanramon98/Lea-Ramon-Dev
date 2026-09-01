import importlib.machinery
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

loader = importlib.machinery.SourceFileLoader("alerts", str(Path(__file__).parents[1] / "platform-alert-dispatcher.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
alerts = importlib.util.module_from_spec(spec)
loader.exec_module(alerts)


class AlertDispatcherTests(unittest.TestCase):
    def test_unconfigured_dispatcher_records_baseline_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observations = root / "observations"
            observations.mkdir()
            (observations / "platform-observation.json").write_text(json.dumps({"apps": [{"id": "portal", "enabled": True, "health": {"status": "healthy"}}]}))
            old_observations, old_state, old_output = alerts.OBSERVATIONS, alerts.STATE, alerts.OUTPUT
            alerts.OBSERVATIONS, alerts.STATE, alerts.OUTPUT = observations, root / "alerts/state.json", observations / "alert-snapshot.json"
            previous = os.environ.pop("ALERT_WEBHOOK_URL", None)
            try:
                with patch.object(alerts.os, "chown"):
                    alerts.main()
            finally:
                if previous is not None: os.environ["ALERT_WEBHOOK_URL"] = previous
                alerts.OBSERVATIONS, alerts.STATE, alerts.OUTPUT = old_observations, old_state, old_output
            snapshot = json.loads((observations / "alert-snapshot.json").read_text())
            self.assertEqual(snapshot["status"], "unconfigured")
            self.assertEqual(len(snapshot["evidence"]), 0)

    def test_transition_requires_a_prior_state(self):
        self.assertEqual(alerts.transitions({}, {"app:portal": "healthy"}, False), [])
        changed = alerts.transitions({"app:portal": "healthy"}, {"app:portal": "unhealthy"}, True)
        self.assertEqual(changed[0]["from"], "healthy")
        self.assertEqual(changed[0]["to"], "unhealthy")

    def test_snapshot_write_sets_portal_group_without_exposing_alert_state(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "observations/alert-snapshot.json"
            state = Path(directory) / "alerts/dispatch-state.json"
            with patch.object(alerts.os, "chown") as chown:
                alerts.write(output, {"status": "healthy"}, alerts.PORTAL_GID)
                alerts.write(state, {"states": {}})
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o640)
            self.assertEqual(stat.S_IMODE(output.parent.stat().st_mode), 0o750)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o640)
            self.assertEqual(chown.call_args_list[0], call(output.parent, 0, alerts.PORTAL_GID))
            self.assertEqual(chown.call_args_list[1].args[1:], (0, alerts.PORTAL_GID))
            self.assertEqual(len(chown.call_args_list), 2)


if __name__ == "__main__":
    unittest.main()
