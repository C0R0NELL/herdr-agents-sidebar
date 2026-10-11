"""Check event subscription acceptance and framing without a live server."""

import json
from pathlib import Path
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from configuration import DEFAULT_ROWS, Presentation, Settings, Store
from runtime import Events, ensure, restore, restart, save_settings


def frame(value):
    return (json.dumps(value) + "\n").encode()


class EventSubscriptions(unittest.TestCase):
    def test_rejected_subscription_fails_before_periodic_reconciliation(self):
        connection = Mock()
        connection.recv.return_value = frame({"error": {"code": "invalid_request"}})
        with patch("runtime.socket.socket", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "events.subscribe: invalid_request"):
                Events(SimpleNamespace(socket="/unused/socket"))
        connection.close.assert_called_once()

    def test_event_received_with_ack_is_delivered_without_another_read(self):
        connection = Mock()
        connection.recv.return_value = (
            frame({"result": {"type": "subscription_started"}})
            + frame({"event": "workspace.renamed", "data": {"workspace_id": "w1"}})
        )
        with patch("runtime.socket.socket", return_value=connection):
            events = Events(SimpleNamespace(socket="/unused/socket"))
        try:
            with patch("runtime.select.select", return_value=([], [], [])):
                self.assertTrue(events.dirty())
                self.assertFalse(events.dirty())
            connection.recv.assert_called_once()
        finally:
            events.close()


class ActivationLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "preferences", root / "state")
        self.config = root / "config.toml"
        self.original = '[ui]\nagent_panel_sort = "priority"\n[ui.sidebar.agents]\nrows = [["state_icon", "workspace"], ["agent"]]\n'
        self.config.write_text(self.original)
        self.herdr = SimpleNamespace(config=self.config, local_id="local:test", enabled=Mock(return_value=True),
                                     validate=Mock(), reload=Mock(), check_projection=Mock())

    def tearDown(self):
        self.temp.cleanup()

    def assert_native_defaults(self):
        parsed = tomllib.loads(self.config.read_text())
        agents = parsed["ui"]["sidebar"]["agents"]
        self.assertNotIn("rows", agents)
        self.assertNotIn("row_gap", agents)
        self.assertIn("machine", agents.get("rows", DEFAULT_ROWS)[0])
        self.assertEqual(parsed["ui"]["agent_panel_sort"], "priority")

    def test_both_no_clears_owned_tokens_and_restores_builtin_native_rows(self):
        preferences = Settings().with_profile("priority", tab_color="#123456").with_active("priority")
        self.store.save(preferences)
        Presentation(self.config, self.store.state).apply(preferences, replace_native_layout=True)
        with patch("runtime.Reconciler") as reconciler, patch("runtime.subprocess.Popen") as spawn:
            save_settings(self.herdr, self.store, preferences.with_active(None))
        self.assertFalse(self.store.load().enabled)
        self.assertEqual(self.store.load().profile("priority"), preferences.profile("priority"))
        self.assert_native_defaults()
        self.assertFalse((self.store.state / "presentation.json").exists())
        reconciler.return_value.clear.assert_called_once_with(self.store.load())
        self.herdr.reload.assert_called_once()
        spawn.assert_not_called()

    def test_native_activity_cannot_start_a_worker_when_both_modes_are_no(self):
        self.store.save(Settings().with_active(None))
        with patch("runtime.subprocess.Popen") as spawn:
            ensure(self.herdr, self.store)
        spawn.assert_not_called()
        self.assertEqual(self.config.read_text(), self.original)

    def test_failed_reactivation_save_restores_native_and_keeps_both_modes_no(self):
        preferences = Settings().with_active(None)
        self.store.save(preferences)
        with patch.object(self.store, "save", side_effect=OSError("disk full")), patch("runtime.subprocess.Popen") as spawn:
            with self.assertRaisesRegex(OSError, "disk full"):
                save_settings(self.herdr, self.store, preferences.with_active("priority"))
        self.assertEqual(self.store.load(), preferences)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse((self.store.state / "presentation.json").exists())
        self.herdr.reload.assert_not_called()
        spawn.assert_not_called()

    def test_restore_resets_both_profiles_and_leaves_the_plugin_inactive(self):
        custom = Settings().with_profile("grouped", view="agent/tab", machine_color="#abc", show_separator=True)
        custom = custom.with_profile("priority", line1=("tab",), line2=(), tab_color="#123456").with_active("priority")
        self.store.save(custom)
        Presentation(self.config, self.store.state).apply(custom, replace_native_layout=True)
        with patch("runtime.Reconciler"), patch("runtime.subprocess.Popen") as spawn:
            restore(self.herdr, self.store)
        self.assertEqual(self.store.load(), Settings())
        self.assertFalse(self.store.load().enabled)
        self.assert_native_defaults()
        spawn.assert_not_called()

    def test_restart_preserves_inactive_profiles_without_activating_them(self):
        custom = Settings().with_profile("priority", line1=("tab",), line2=(), tab_color="#123456").with_active(None)
        self.store.save(custom)
        with patch("runtime.Reconciler"), patch("runtime.subprocess.Popen") as spawn:
            restart(self.herdr, self.store)
        self.assertEqual(self.store.load(), custom)
        self.assert_native_defaults()
        spawn.assert_not_called()

    def test_restart_reloads_the_active_worker_without_resetting_either_profile(self):
        custom = Settings().with_profile("grouped", view="agent/tab", machine_color="#123456")
        custom = custom.with_profile("priority", line1=("agent",), line2=()).with_active("grouped")
        self.store.save(custom)
        Presentation(self.config, self.store.state).apply(custom, replace_native_layout=True)
        with patch("runtime.Reconciler"), patch("runtime.subprocess.Popen") as spawn:
            restart(self.herdr, self.store)
        self.assertEqual(self.store.load(), custom)
        self.assertTrue(self.store.load().enabled)
        self.assertEqual(tomllib.loads(self.config.read_text())["ui"]["sidebar"]["agents"]["rows"], custom.rows())
        # Registry disable/uninstall must still recover the pre-plugin layout.
        Presentation(self.config, self.store.state).restore()
        self.assertEqual(self.config.read_text(), self.original)
        spawn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
