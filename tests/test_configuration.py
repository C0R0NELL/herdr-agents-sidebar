import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from configuration import Conflict, Presentation, Settings, Store

CONFIG = '''# Keep user comments and commands.
[keys]
prefix = "ctrl+b"
[[keys.command]]
key = "prefix+p"
type = "plugin_action"
command = "ray.plugin-manager.open"
description = "open plugin manager"
[[keys.command]]
key = "prefix+e"
type = "shell"
command = "herdr plugin pane open --plugin ttt.editor --entrypoint editor"
[ui]
agent_panel_sort = "priority" # existing choice
[ui.toast]
delivery = "off"
[ui.sidebar.agents]
row_gap = 1
rows = [
 ["state_icon", "machine", "workspace", "tab"],
 ["agent"],
]
'''


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "config.toml"
        self.config.write_text(CONFIG)
        self.presentation = Presentation(self.config, self.root / "state")

    def tearDown(self):
        self.temp.cleanup()

    def test_apply_and_restore_preserve_original_bytes_and_bindings(self):
        self.presentation.apply(Settings())
        import tomllib
        applied = tomllib.loads(self.config.read_text())
        self.assertEqual(applied["keys"]["prefix"],"ctrl+b")
        self.assertEqual(len(applied["keys"]["command"]),2)
        self.assertEqual(applied["ui"]["agent_panel_sort"],"spaces")
        self.assertEqual(applied["ui"]["sidebar"]["agents"]["row_gap"],0)
        self.presentation.restore()
        self.assertEqual(self.config.read_text(),CONFIG)

    def test_restore_preserves_later_user_edits_and_is_idempotent(self):
        self.presentation.apply(Settings())
        text = self.config.read_text().replace('delivery = "off"','delivery = "terminal"')
        text = text.replace('row_gap = 0','row_gap = 2 # user changed this')
        self.config.write_text(text)
        self.presentation.restore()
        restored = self.config.read_text()
        self.assertIn('row_gap = 2 # user changed this',restored)
        self.assertIn('delivery = "terminal"',restored)
        self.assertIn('agent_panel_sort = "priority" # existing choice',restored)
        self.presentation.restore()
        self.assertEqual(self.config.read_text(),restored)

    def test_custom_layout_is_a_conflict_and_nothing_is_written(self):
        custom = CONFIG.replace('["agent"],','["$foreign"],')
        self.config.write_text(custom)
        with self.assertRaises(Conflict): self.presentation.apply(Settings())
        self.assertEqual(self.config.read_text(),custom)
        self.assertFalse(list((self.root/"state").glob("*.json")))

    def test_explicit_activation_can_replace_and_restore_native_custom_rows(self):
        original = CONFIG.replace('"state_icon", "machine", "workspace", "tab"',
                                  '"state_icon", "workspace", "tab"')
        self.config.write_text(original)
        with self.assertRaises(Conflict):
            self.presentation.apply(Settings())
        self.presentation.apply(Settings(), replace_native_layout=True)
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), original)
        foreign = original.replace('["agent"],', '["$foreign"],')
        self.config.write_text(foreign)
        with self.assertRaises(Conflict):
            self.presentation.apply(Settings(), replace_native_layout=True)
        self.assertEqual(self.config.read_text(), foreign)

    def test_failed_config_validation_does_not_publish(self):
        def reject(_): raise ValueError("invalid config")
        with self.assertRaisesRegex(ValueError,"invalid config"):
            self.presentation.apply(Settings(),validate=reject)
        self.assertEqual(self.config.read_text(),CONFIG)

    def test_user_changes_to_owned_fields_prevent_reapplication(self):
        self.presentation.apply(Settings())
        changed = self.config.read_text().replace('row_gap = 0','row_gap = 2')
        self.config.write_text(changed)
        with self.assertRaises(Conflict): self.presentation.apply(Settings(machine_color="#123456"))
        self.assertEqual(self.config.read_text(),changed)

    def test_empty_and_dotted_configurations_round_trip(self):
        for original in ('','ui.agent_panel_sort = "priority"\n',
                         '[ui.toast]\ndelivery = "off"\n',
                         'message = """\n[ui.sidebar.agents]\nrows = []\n"""\n'):
            with self.subTest(original=original):
                self.config.write_text(original)
                self.presentation.apply(Settings())
                self.presentation.restore()
                self.assertEqual(self.config.read_text(),original)

    def test_preferences_are_portable_private_and_survive_source_replacement(self):
        env = {"XDG_CONFIG_HOME":str(self.root/"config"), "XDG_STATE_HOME":str(self.root/"state"),
               "HERDR_PLUGIN_ID":"other.plugin", "HERDR_PLUGIN_CONFIG_DIR":str(self.root/"wrong"),
               "HERDR_PLUGIN_STATE_DIR":str(self.root/"wrong-state")}
        with patch.dict(os.environ,env,clear=True): store = Store()
        preferences = Settings(machine_color="#abc",project_color="#123456",agent_color="#ffffff",show_separator=False)
        store.save(preferences)
        self.assertNotIn("wrong",str(store.config))
        self.assertEqual(store.load(),preferences.normalized())
        self.assertEqual(store.preferences.stat().st_mode & 0o777,0o600)
        self.assertTrue(store.preferences.is_relative_to(self.root/"config"))

    def test_invalid_settings_do_not_replace_existing_preferences(self):
        store=Store(self.root/"preferences",self.root/"state")
        store.save(Settings())
        before=store.preferences.read_bytes()
        for change in ({"machine_color":"red"},{"show_separator":"false"}):
            with self.assertRaises(ValueError): store.save(Settings(**change))
            self.assertEqual(store.preferences.read_bytes(),before)

    def test_interrupted_color_update_keeps_the_original_ownership_receipt(self):
        import configuration
        self.presentation.apply(Settings())
        write = configuration.atomic_write
        def interrupt(path, text, **kwargs):
            if path == self.config:
                raise OSError("simulated interruption before config replacement")
            return write(path, text, **kwargs)
        with patch("configuration.atomic_write", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.presentation.apply(Settings(machine_color="#123456"))
        self.presentation.apply(Settings(machine_color="#abcdef"))
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), CONFIG)

    def test_edit_during_validation_is_not_overwritten(self):
        changed = CONFIG.replace('delivery = "off"', 'delivery = "terminal"')
        def concurrent_edit(_):
            self.config.write_text(changed)
        with self.assertRaises(Conflict):
            self.presentation.apply(Settings(), validate=concurrent_edit)
        self.assertEqual(self.config.read_text(), changed)
        self.assertFalse(self.presentation.receipt.exists())


if __name__ == "__main__": unittest.main()
