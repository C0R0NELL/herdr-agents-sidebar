"""Check event subscription acceptance and framing without a live server."""

import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import time
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from configuration import DEFAULT_ROWS, Presentation, Settings, Store
from layout import AgentKey, Patch
from runtime import Events, Herdr, ensure, restore, restart, save_settings, worker


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
        self.assertEqual(tomllib.loads(self.config.read_text())["ui"]["sidebar"]["agents"]["rows"], custom.rows(token_names=self.store.token_names()))
        # Registry disable/uninstall must still recover the pre-plugin layout.
        Presentation(self.config, self.store.state).restore()
        self.assertEqual(self.config.read_text(), self.original)
        spawn.assert_called_once()

    def test_settings_save_cannot_be_reverted_by_a_worker_between_config_and_preferences(self):
        previous = Settings().with_active("grouped")
        proposed = previous.with_active("priority")
        self.store.save(previous)
        names = self.store.token_names()
        Presentation(self.config, self.store.state, token_names=names).apply(previous, replace_native_layout=True)
        ready, saving, progressed, applied = (threading.Event() for _ in range(4))
        sleeps, handlers, errors = [], {}, []
        real_sleep, real_save = time.sleep, self.store.save

        def tick(settings):
            ready.set()
            if settings == proposed:
                applied.set()

        def sleep(_):
            if threading.current_thread().name == "sidebar-test-worker" and saving.is_set():
                sleeps.append(True)
                if len(sleeps) >= 2:
                    progressed.set()
            real_sleep(.01)

        def save(settings):
            # Reproduce the real gap after Herdr config changed but before preferences save.
            saving.set()
            if not progressed.wait(2):
                raise AssertionError("Worker did not progress during the interrupted settings save")
            real_save(settings)

        def run():
            try:
                worker(self.herdr, self.store)
            except BaseException as error:
                errors.append(error)

        with patch("runtime.signal.signal", side_effect=lambda sig, handler: handlers.update({sig: handler})), \
                patch("runtime.Events") as events, patch("runtime.Reconciler") as engine, \
                patch("runtime.time.sleep", side_effect=sleep), patch("runtime.subprocess.Popen"):
            events.return_value.dirty.return_value = True
            engine.return_value.tick.side_effect = tick
            thread = threading.Thread(target=run, name="sidebar-test-worker")
            thread.start()
            try:
                self.assertTrue(ready.wait(2), "Worker never reached the initial live profile")
                with patch.object(self.store, "save", side_effect=save):
                    save_settings(self.herdr, self.store, proposed)
                self.assertTrue(applied.wait(2), "Worker never observed the saved profile")
                self.assertEqual(self.store.load(), proposed)
                rows = tomllib.loads(self.config.read_text())["ui"]["sidebar"]["agents"]["rows"]
                self.assertEqual(rows, proposed.rows(token_names=names))
            finally:
                if signal.SIGTERM in handlers:
                    handlers[signal.SIGTERM]()
                thread.join(3)
                self.assertFalse(thread.is_alive(), "Test worker retained its lock")
            self.assertEqual(errors, [])

    def test_snapshot_and_clear_are_restricted_to_the_installations_wire_keys(self):
        peer = Store(self.store.config.parent / "peer-config", self.store.state.parent / "peer-state")
        own_names, peer_names = self.store.token_names(), peer.token_names()
        raw_tokens = {own_names["has_machine"]: "Local", peer_names["has_machine"]: "peer",
                      "has_machine": "legacy", "foreign": "preserved"}
        native = {"workspace_id": "w1", "pane_id": "w1:p1", "agent": "codex", "state": "working",
                  "tokens": raw_tokens}
        raw = {"panes": [dict(native)], "agents": [dict(native)]}
        original = json.loads(json.dumps(raw))
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_CONFIG_PATH": str(self.config),
                                     "HERDR_SOCKET_PATH": str(self.config.parent / "test.sock")}), \
                patch("runtime.shutil.which", return_value="/unused/herdr"):
            herdr = Herdr(self.store)
        herdr.api = Mock(return_value={"snapshot": raw})
        snapshot = herdr.snapshot()
        agent = snapshot.snapshot["agents"][0]
        self.assertEqual(agent["tokens"], {"has_machine": "Local"})
        self.assertEqual(agent["state"], "working")
        self.assertEqual(agent["pane_id"], "w1:p1")
        self.assertEqual(raw, original, "Decoding mutated an authoritative snapshot")
        herdr.publish(Patch(AgentKey(herdr.local_id, herdr.session, "w1", "w1:p1"), {"has_machine": None}))
        method, params = herdr.api.call_args.args
        self.assertEqual(method, "pane.report_metadata")
        self.assertEqual(params["tokens"], {own_names["has_machine"]: None})


if __name__ == "__main__":
    unittest.main()
