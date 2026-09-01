import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
