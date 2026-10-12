import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from configuration import COLOR_FIELDS, Conflict, DARK_BLUE, DEFAULT_ROWS, Presentation, Settings, Store

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
        self.presentation.apply(Settings().with_active("grouped"))
        import tomllib
        applied = tomllib.loads(self.config.read_text())
        self.assertEqual(applied["keys"]["prefix"],"ctrl+b")
        self.assertEqual(len(applied["keys"]["command"]),2)
        self.assertEqual(applied["ui"]["agent_panel_sort"],"priority")
        self.assertEqual(applied["ui"]["sidebar"]["agents"]["row_gap"],0)
        self.presentation.restore()
        self.assertEqual(self.config.read_text(),CONFIG)

    def test_native_defaults_restore_machine_even_without_an_ownership_receipt(self):
        import tomllib
        old = CONFIG.replace('"state_icon", "machine", "workspace", "tab"', '"state_icon", "workspace", "tab"')
        self.config.write_text(old)
        self.assertTrue(self.presentation.restore(native_defaults=True))
        parsed = tomllib.loads(self.config.read_text())
        agents = parsed["ui"]["sidebar"]["agents"]
        self.assertNotIn("rows", agents)
        self.assertNotIn("row_gap", agents)
        self.assertIn("machine", agents.get("rows", DEFAULT_ROWS)[0])
        self.assertEqual(parsed["keys"], tomllib.loads(old)["keys"])
        self.assertEqual(parsed["ui"]["agent_panel_sort"], "priority")
        self.assertFalse(self.presentation.restore(native_defaults=True))

    def test_native_defaults_override_old_native_custom_rows_after_deactivation(self):
        import tomllib
        old = CONFIG.replace('"state_icon", "machine", "workspace", "tab"', '"state_icon", "workspace", "tab"')
        self.config.write_text(old)
        self.presentation.apply(Settings().with_active("grouped"), replace_native_layout=True)
        self.presentation.restore(native_defaults=True)
        parsed = tomllib.loads(self.config.read_text())
        self.assertNotIn("rows", parsed["ui"]["sidebar"]["agents"])
        self.assertNotIn("row_gap", parsed["ui"]["sidebar"]["agents"])
        self.assertFalse(self.presentation.receipt.exists())

    def test_native_defaults_refuse_foreign_layouts_and_preserve_the_receipt(self):
        self.presentation.apply(Settings().with_active("grouped"))
        original = self.config.read_text()
        changed = original.replace('token = "$has_agent"', 'token = "$foreign"')
        self.assertNotEqual(changed, original)
        self.config.write_text(changed)
        with self.assertRaises(Conflict):
            self.presentation.restore(native_defaults=True)
        self.assertEqual(self.config.read_text(), changed)
        self.assertTrue(self.presentation.receipt.exists())

    def test_native_defaults_refuse_unowned_per_agent_overrides(self):
        original = CONFIG + 'rows_by_agent.codex = [["workspace"], ["agent"]]\n'
        self.config.write_text(original)
        with self.assertRaises(Conflict):
            self.presentation.restore(native_defaults=True)
        self.assertEqual(self.config.read_text(), original)

    def test_native_defaults_validation_failure_preserves_config_and_ownership(self):
        self.presentation.apply(Settings().with_active("grouped"))
        original = self.config.read_text()
        def reject(_):
            raise ValueError("invalid config")
        with self.assertRaisesRegex(ValueError, "invalid config"):
            self.presentation.restore(validate=reject, native_defaults=True)
        self.assertEqual(self.config.read_text(), original)
        self.assertTrue(self.presentation.receipt.exists())

    def test_restore_preserves_later_user_edits_and_is_idempotent(self):
        self.presentation.apply(Settings().with_active("grouped"))
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
        with self.assertRaises(Conflict): self.presentation.apply(Settings().with_active("grouped"))
        self.assertEqual(self.config.read_text(),custom)
        self.assertFalse(list((self.root/"state").glob("*.json")))

    def test_explicit_activation_can_replace_and_restore_native_custom_rows(self):
        original = CONFIG.replace('"state_icon", "machine", "workspace", "tab"',
                                  '"state_icon", "workspace", "tab"')
        self.config.write_text(original)
        with self.assertRaises(Conflict):
            self.presentation.apply(Settings().with_active("grouped"))
        self.presentation.apply(Settings().with_active("grouped"), replace_native_layout=True)
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), original)
        foreign = original.replace('["agent"],', '["$foreign"],')
        self.config.write_text(foreign)
        with self.assertRaises(Conflict):
            self.presentation.apply(Settings().with_active("grouped"), replace_native_layout=True)
        self.assertEqual(self.config.read_text(), foreign)

    def test_failed_config_validation_does_not_publish(self):
        def reject(_): raise ValueError("invalid config")
        with self.assertRaisesRegex(ValueError,"invalid config"):
            self.presentation.apply(Settings().with_active("grouped"),validate=reject)
        self.assertEqual(self.config.read_text(),CONFIG)

    def test_user_changes_to_owned_fields_prevent_reapplication(self):
        self.presentation.apply(Settings().with_active("grouped"))
        changed = self.config.read_text().replace('row_gap = 0','row_gap = 2')
        self.config.write_text(changed)
        with self.assertRaises(Conflict): self.presentation.apply(Settings().with_active("grouped").with_profile("grouped", machine_color="#123456"))
        self.assertEqual(self.config.read_text(),changed)

    def test_empty_and_dotted_configurations_round_trip(self):
        for original in ('','ui.agent_panel_sort = "priority"\n',
                         '[ui.toast]\ndelivery = "off"\n',
                         'message = """\n[ui.sidebar.agents]\nrows = []\n"""\n'):
            with self.subTest(original=original):
                self.config.write_text(original)
                self.presentation.apply(Settings().with_active("grouped"))
                self.presentation.restore()
                self.assertEqual(self.config.read_text(),original)

    def test_preferences_are_portable_private_and_survive_source_replacement(self):
        env = {"XDG_CONFIG_HOME":str(self.root/"config"), "XDG_STATE_HOME":str(self.root/"state"),
               "HERDR_PLUGIN_ID":"other.plugin", "HERDR_PLUGIN_CONFIG_DIR":str(self.root/"wrong"),
               "HERDR_PLUGIN_STATE_DIR":str(self.root/"wrong-state")}
        with patch.dict(os.environ,env,clear=True): store = Store()
        preferences = Settings().with_profile("grouped", machine_color="#abc",project_color="#123456",agent_color="#ffffff",show_separator=True)
        store.save(preferences)
        self.assertNotIn("wrong",str(store.config))
        self.assertEqual(store.load(),preferences.normalized())
        self.assertEqual(store.preferences.stat().st_mode & 0o777,0o600)
        self.assertTrue(store.preferences.is_relative_to(self.root/"config"))

    def test_fresh_install_uses_the_factory_snapshot_with_both_modes_inactive(self):
        store = Store(self.root / "preferences", self.root / "state")
        factory = store.load()
        self.assertFalse(factory.enabled)
        self.assertEqual(factory.grouped.view, "agent")
        self.assertFalse(factory.grouped.show_separator)
        self.assertEqual(factory.priority.line1, ("status", "project", "agent"))
        self.assertEqual(factory.priority.line2, ("machine",))
        for mode in ("grouped", "priority"):
            profile = factory.profile(mode)
            for name in (field + "_color" for field in COLOR_FIELDS):
                expected = DARK_BLUE if mode == "priority" and name == "machine_color" else "default"
                self.assertEqual(getattr(profile, name), expected)
        for mode in ("grouped", "priority"):
            self.assertTrue(set(("pane", "status_text", "terminal_title", "terminal_title_stripped")).isdisjoint(
                factory.with_active(mode).visible_fields))
        self.assertFalse(store.preferences.exists(), "Reading defaults must not write user state")

    def test_installations_have_durable_independent_metadata_keys(self):
        first = Store(self.root / "first/config", self.root / "first/state")
        second = Store(self.root / "second/config", self.root / "second/state")
        first_keys, second_keys = first.token_names(), second.token_names()
        self.assertTrue(set(first_keys.values()).isdisjoint(second_keys.values()))
        self.assertEqual(set(first_keys), {"has_machine", "has_project", "has_agent_prefix", "has_agent", "has_gap"})
        import re
        for name in first_keys.values():
            self.assertIsNotNone(re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name))
        # Test key mapping with a fixed view, independently of the factory layout.
        preferences = Settings().with_profile("priority", line1=("project",), line2=("agent",)).with_active("priority")
        first.save(preferences)
        reopened = Store(first.config, first.state)
        self.assertEqual(reopened.token_names(), first_keys)
        self.assertEqual(reopened.load(), preferences)
        self.assertEqual((first.state / "instance.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((first.state.stat().st_mode & 0o777), 0o700)
        self.assertEqual(preferences.rows(token_names=first_keys)[0][0]["token"], "$" + first_keys["has_project"])

    def test_native_details_upgrade_and_round_trip_without_changing_saved_views(self):
        import tomllib
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        original = ('schema = 4\nmode = "priority"\nenabled = true\n'
                    '[grouped]\nview = "agent/tab"\nagent_color = "#abc"\n'
                    '[priority]\nline1 = ["status", "agent"]\nline2 = ["machine"]\n')
        store.preferences.write_text(original)
        previous = store.load()
        self.assertEqual(store.preferences.read_text(), original)
        self.assertEqual(previous.grouped.view, "agent/tab")
        self.assertEqual(previous.priority.line1, ("status", "agent"))
        self.assertEqual(previous.priority.line2, ("machine",))
        self.assertTrue(previous.enabled)
        extras = ("pane", "status_text", "terminal_title", "terminal_title_stripped")
        self.assertTrue(all(name not in previous.visible_fields for name in extras))
        edited = previous.with_profile("priority", line1=("status", "agent", "pane", "status_text"),
                                       line2=("terminal_title", "terminal_title_stripped"), pane_color="#f79")
        edited = edited.with_profile("grouped", line1=("status", "agent", "tab", *extras),
                                    pane_color="#abc")
        store.save(edited)
        saved = store.load()
        self.assertEqual(saved, edited.normalized())
        self.assertEqual(saved.grouped.pane_color, "#aabbcc")
        self.assertEqual(saved.priority.pane_color, "#ff7799")
        self.assertEqual(tomllib.loads(store.preferences.read_text())["schema"], 5)
        for mode in ("grouped", "priority"):
            rows = saved.with_active(mode).rows()
            tokens = {item["token"]: item for row in rows for item in row if isinstance(item, dict)}
            for native in ("pane", "state_text", "terminal_title", "terminal_title_stripped"):
                self.assertIn(native, tokens)
                self.assertEqual(tokens[native]["fg"], ("#aabbcc" if mode == "grouped" else "#ff7799")
                                 if native == "pane" else DARK_BLUE)
            if mode == "grouped":
                self.assertEqual([item if isinstance(item, str) else item["token"] for item in rows[2]][-5:],
                                 ["tab", "pane", "state_text", "terminal_title", "terminal_title_stripped"])

    def test_unknown_or_invalid_installation_identity_is_never_replaced(self):
        store = Store(self.root / "preferences", self.root / "state")
        store.state.mkdir()
        identity = store.state / "instance.json"
        for content in ('{"schema": 2, "id": "future"}', '{"schema": 1, "id": "broken"}', '{broken'):
            with self.subTest(content=content):
                identity.write_text(content)
                with self.assertRaises(Conflict):
                    store.token_names()
                self.assertEqual(identity.read_text(), content)

    def test_invalid_settings_do_not_replace_existing_preferences(self):
        store=Store(self.root/"preferences",self.root/"state")
        store.save(Settings())
        before=store.preferences.read_bytes()
        for mode, changes in (("grouped", {"machine_color": "red"}),
                              ("grouped", {"show_separator": "false"}),
                              ("grouped", {"view": "machine"}),
                              ("grouped", {"line1": ()}),
                              ("grouped", {"line1": ("agent", "machine")}),
                              ("grouped", {"line1": ("pane", "pane")}),
                              ("grouped", {"pane_color": "red"}),
                              ("priority", {"view": "agent/tab"}),
                              ("priority", {"tab_color": "white"}),
                              ("priority", {"line1": (), "line2": ()}),
                              ("priority", {"line1": ("status", "agent"), "line2": ("agent",)}),
                              ("priority", {"line1": ("unknown",)})):
            with self.assertRaises(ValueError): store.save(Settings().with_profile(mode, **changes))
            self.assertEqual(store.preferences.read_bytes(),before)
        with self.assertRaises(ValueError): store.save(Settings(mode="unknown"))
        self.assertEqual(store.preferences.read_bytes(), before)

    def test_both_modes_can_be_inactive_without_losing_either_profile(self):
        store = Store(self.root / "preferences", self.root / "state")
        original = Settings().with_profile("grouped", view="agent/tab", machine_color="#abc")
        original = original.with_profile("priority", line1=("tab",), line2=()).with_active("priority")
        paused = original.with_active(None)
        store.save(paused)
        saved = store.load()
        self.assertFalse(saved.enabled)
        self.assertEqual(saved.mode, "priority", "Remember the last mode while both are inactive")
        for mode in ("grouped", "priority"):
            self.assertEqual(saved.profile(mode), original.normalized().profile(mode))
            resumed = saved.with_active(mode)
            self.assertTrue(resumed.enabled)
            self.assertEqual(resumed.mode, mode)
        with self.assertRaises(ValueError):
            saved.rows()

    def test_legacy_restore_pause_migrates_without_reactivating_the_sidebar(self):
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        store.state.mkdir()
        store.preferences.write_text('schema = 3\nmode = "priority"\n[priority]\ntab_color = "#abc"\n')
        control = store.state / "control.json"
        control.write_text('{"schema": 1, "active": false}')
        original = store.preferences.read_bytes()
        saved = store.load()
        self.assertFalse(saved.enabled)
        self.assertEqual(store.preferences.read_bytes(), original)
        store.save(saved)
        self.assertFalse(store.load().enabled)
        store.save(saved.with_active("grouped"))
        self.assertTrue(store.load().enabled, "Schema 4 is authoritative over the old pause record")
        control.write_text('{"schema": 1, "active": false}')
        self.assertTrue(store.load().enabled)

    def test_invalid_legacy_pause_is_preserved_and_rejected(self):
        store = Store(self.root / "preferences", self.root / "state")
        store.state.mkdir()
        control = store.state / "control.json"
        control.write_text('{"schema": 2, "active": false}')
        with self.assertRaises(Conflict):
            store.save(Settings())
        self.assertFalse(store.preferences.exists())
        self.assertEqual(control.read_text(), '{"schema": 2, "active": false}')

    def test_existing_preferences_default_to_grouped_and_preserve_explicit_choices(self):
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        store.preferences.write_text('schema = 1\nmachine_color = "#123456"\nshow_separator = true\n')
        saved = store.load()
        self.assertEqual(saved.mode, "grouped")
        self.assertEqual(saved.profile("grouped").machine_color, "#123456")
        self.assertTrue(saved.show_separator)
        from dataclasses import replace
        store.save(replace(saved, mode="priority"))
        self.assertEqual(store.load().mode, "priority")
        self.assertTrue(store.load().profile("grouped").show_separator)

    def test_views_preserve_legacy_defaults_and_are_saved_separately_by_mode(self):
        from dataclasses import replace
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        store.preferences.write_text('schema = 1\nmode = "priority"\nagent_color = "#abc"\n')
        legacy = store.load()
        self.assertEqual(legacy.profile("priority").line1, ("status", "project"))
        self.assertEqual(legacy.profile("priority").line2, ("agent",))
        self.assertEqual(legacy.profile("grouped").view, "agent")
        selected = legacy.with_profile("priority", line1=("machine", "project"), line2=("status", "agent", "tab"))
        selected = selected.with_active("grouped").with_profile("grouped", view="agent/tab")
        store.save(selected)
        saved = store.load()
        self.assertEqual(saved.profile("grouped").view, "agent/tab")
        self.assertEqual(saved.profile("grouped").agent_color, "#aabbcc")
        self.assertEqual(saved.profile("priority").line1, ("machine", "project"))
        self.assertEqual(saved.profile("priority").line2, ("status", "agent", "tab"))

    def test_legacy_preferences_become_independent_profiles_without_changing_active_layout(self):
        import tomllib
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        original = ('schema = 1\nmode = "priority"\nmachine_color = "#123456"\n'
                    'project_color = "#abcdef"\nagent_color = "#ff79c6"\nshow_separator = true\n'
                    'grouped_view = "agent/project/machine/tab"\npriority_view = "agent/project"\n')
        store.preferences.write_text(original)
        legacy = store.load()
        original_rows = legacy.rows()
        for mode in ("grouped", "priority"):
            self.assertEqual(legacy.profile(mode).machine_color, "#123456")
            self.assertEqual(legacy.profile(mode).project_color, "#abcdef")
            self.assertEqual(legacy.profile(mode).agent_color, "#ff79c6")
        self.assertTrue(legacy.profile("grouped").show_separator)
        self.assertEqual(store.preferences.read_text(), original, "Reading must not rewrite preferences")
        inactive_edit = legacy.with_profile("grouped", machine_color="#f1fa8c", view="agent")
        self.assertEqual(inactive_edit.mode, "priority")
        self.assertEqual(inactive_edit.rows(), original_rows, "Inactive edits must not change the sidebar")
        store.save(inactive_edit)
        saved = store.load()
        self.assertEqual(saved.profile("grouped").view, "agent")
        self.assertEqual(saved.profile("priority").line1, ("status", "project"))
        self.assertEqual(saved.profile("priority").machine_color, "#123456")
        parsed = tomllib.loads(store.preferences.read_text())
        self.assertEqual(parsed["schema"], 5)
        self.assertEqual(parsed["mode"], "priority")
        self.assertIn("grouped", parsed)
        self.assertIn("priority", parsed)
        for mode in ("grouped", "priority", "grouped"):
            selected = saved.with_active(mode)
            store.save(selected)
            self.assertEqual(store.load().mode, mode)
            self.assertEqual(store.load().profile("grouped"), saved.profile("grouped"))
            self.assertEqual(store.load().profile("priority"), saved.profile("priority"))

    def test_mode_changes_do_not_change_native_order_and_restore_original_config(self):
        for mode in ("grouped", "priority", "grouped"):
            self.presentation.apply(Settings(mode=mode, enabled=True).with_profile("grouped", show_separator=True))
            import tomllib
            parsed = tomllib.loads(self.config.read_text())
            self.assertEqual(parsed["ui"]["agent_panel_sort"], "priority")
            rows = parsed["ui"]["sidebar"]["agents"]["rows"]
            self.assertEqual(len(rows), 2 if mode == "priority" else 4)
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), CONFIG)

    def test_ambiguous_or_newer_profile_files_cannot_be_overwritten(self):
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        for original in ('schema = 6\nmode = "grouped"\n',
                         'schema = 4\nenabled = "false"\n',
                         'schema = 1\nmachine_color = "#abcdef"\n[grouped]\nview = "agent"\n',
                         'schema = 2\nmachine_color = "#abcdef"\n[grouped]\nview = "agent"\n',
                         'schema = 2\n[grouped]\nunknown = true\n',
                         'schema = 3\n[priority]\nview = "agent"\n',
                         'schema = 3\n[grouped]\nline1 = ["agent"]\n'):
            with self.subTest(original=original):
                store.preferences.write_text(original)
                with self.assertRaises(Conflict):
                    store.save(Settings())
                self.assertEqual(store.preferences.read_text(), original)

    def test_mode_views_upgrade_to_fixed_grouped_tree_and_ordered_priority_lines(self):
        import tomllib
        store = Store(self.root / "preferences", self.root / "state")
        store.config.mkdir()
        original = ('schema = 2\nmode = "priority"\n[grouped]\nview = "agent"\n'
                    'machine_color = "#123456"\n[priority]\n'
                    'view = "agent/project/machine/tab"\nagent_color = "#50fa7b"\n')
        store.preferences.write_text(original)
        upgraded = store.load()
        self.assertEqual(upgraded.profile("grouped").view, "agent")
        self.assertEqual(upgraded.profile("priority").line1, ("status", "project", "machine", "tab"))
        self.assertEqual(upgraded.profile("priority").line2, ("agent",))
        self.assertEqual(upgraded.profile("priority").tab_color, "#50fa7b")
        self.assertEqual(store.preferences.read_text(), original)
        edited = upgraded.with_profile("grouped", view="agent/tab", tab_color="#abc")
        edited = edited.with_profile("priority", line1=("machine", "project"), line2=("agent", "tab", "status"))
        store.save(edited)
        parsed = tomllib.loads(store.preferences.read_text())
        self.assertEqual(parsed["schema"], 5)
        self.assertNotIn("view", parsed["priority"])
        self.assertNotIn("view", parsed["grouped"])
        self.assertNotIn("line2", parsed["grouped"])
        self.assertEqual(parsed["grouped"]["line1"], ["status", "agent", "tab"])
        self.assertEqual(parsed["grouped"]["tab_color"], "#aabbcc")
        self.assertEqual(store.load().profile("priority").line2, ("agent", "tab", "status"))
        group_rows = store.load().with_active("grouped").rows()
        self.assertEqual(group_rows[0][0]["token"], "$has_machine")
        self.assertEqual(group_rows[1][0]["token"], "$has_project")
        self.assertEqual(group_rows[2][-1]["token"], "tab")

    def legacy_sort_receipt(self):
        self.presentation.apply(Settings().with_active("grouped"))
        # Recreate a 0.1.0 receipt that owned native order as well as rows.
        original_sort = 'agent_panel_sort = "priority" # existing choice\n'
        installed_sort = 'agent_panel_sort = "spaces"\n'
        self.config.write_text(self.config.read_text().replace(original_sort, installed_sort))
        receipt = json.loads(self.presentation.receipt.read_text())
        receipt["installed"] = self.config.read_text()
        receipt["fields"]["ui.agent_panel_sort"] = {"original": original_sort, "installed": installed_sort}
        self.presentation.receipt.write_text(json.dumps(receipt))

    def test_legacy_sort_ownership_is_preserved_for_cleanup_without_new_sort_writes(self):
        self.legacy_sort_receipt()
        self.presentation.apply(Settings(mode="priority", enabled=True))
        self.assertIn('agent_panel_sort = "spaces"\n', self.config.read_text())
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), CONFIG)

    def test_later_native_sort_edit_is_allowed_after_legacy_upgrade_and_survives_restore(self):
        self.legacy_sort_receipt()
        changed = self.config.read_text().replace('agent_panel_sort = "spaces"',
                                                 'agent_panel_sort = "priority" # later user edit')
        self.config.write_text(changed)
        self.presentation.apply(Settings(mode="priority", enabled=True))
        self.presentation.restore()
        self.assertIn('agent_panel_sort = "priority" # later user edit', self.config.read_text())

    def test_unrelated_user_edit_survives_mode_change_and_disable(self):
        self.presentation.apply(Settings().with_active("grouped"))
        self.config.write_text(self.config.read_text().replace('delivery = "off"', 'delivery = "terminal"'))
        self.presentation.apply(Settings(mode="priority", enabled=True))
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), CONFIG.replace('delivery = "off"', 'delivery = "terminal"'))

    def test_interrupted_color_update_keeps_the_original_ownership_receipt(self):
        import configuration
        self.presentation.apply(Settings().with_active("grouped"))
        write = configuration.atomic_write
        def interrupt(path, text, **kwargs):
            if path == self.config:
                raise OSError("simulated interruption before config replacement")
            return write(path, text, **kwargs)
        with patch("configuration.atomic_write", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.presentation.apply(Settings().with_active("grouped").with_profile("grouped", machine_color="#123456"))
        self.presentation.apply(Settings().with_active("grouped").with_profile("grouped", machine_color="#abcdef"))
        self.presentation.restore()
        self.assertEqual(self.config.read_text(), CONFIG)

    def test_edit_during_validation_is_not_overwritten(self):
        changed = CONFIG.replace('delivery = "off"', 'delivery = "terminal"')
        def concurrent_edit(_):
            self.config.write_text(changed)
        with self.assertRaises(Conflict):
            self.presentation.apply(Settings().with_active("grouped"), validate=concurrent_edit)
        self.assertEqual(self.config.read_text(), changed)
        self.assertFalse(self.presentation.receipt.exists())


if __name__ == "__main__": unittest.main()
