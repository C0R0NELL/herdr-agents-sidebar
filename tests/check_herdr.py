#!/usr/bin/env python3
"""Check real plugin activation, settings, cleanup and native renderer in isolation."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import tomllib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import Conflict, PLUGIN_ID, Settings, Store
from runtime import Events, Herdr
from herdr_harness import HerdrHarness
from check_visual import capture_svg, check as visual_check, sidebar_lines
from layout import GROUPED_VIEWS, TOKENS
from sidebar import OPTIONS

ROOT = Path(__file__).resolve().parents[1]


def wait(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError("Isolated integration condition timed out")


def tokens(h, machine, *, origin="local"):
    store = Store(h.root / origin / "config/herdr/plugins/config" / PLUGIN_ID,
                  h.root / origin / "state/herdr/plugins" / PLUGIN_ID)
    names = store.token_names()
    return [{**{name: value for name, value in raw.items() if name not in TOKENS},
             **{name: raw[wire] for name, wire in names.items() if wire in raw}}
            for a in h.api(machine, "session.snapshot")["snapshot"]["agents"]
            for raw in [a.get("tokens") or {}]]


def popup_open(lines):
    return any("Active" in line and ("[Yes]" in line or "[No]" in line) for line in lines)


def activate_by_navigation(h):
    """Emit real native focus changes, never an explicit plugin action."""
    snapshot = h.api("local", "session.snapshot")["snapshot"]
    target = next(workspace for workspace in snapshot["workspaces"] if not workspace["focused"])
    h.api("local", "workspace.focus", {"workspace_id": target["workspace_id"]})


def worker_stopped(state):
    for path in state.glob("local-*.lock"):
        with path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
    return True


def native_defaults(config):
    agents = tomllib.loads(config.read_text()).get("ui", {}).get("sidebar", {}).get("agents", {})
    return "rows" not in agents and "row_gap" not in agents


def check_activation():
    """First use requires Settings; Restore resets and Restart never activates No."""
    with HerdrHarness() as h:
        # Native Herdr supplies Machine labels when multiple endpoints exist.
        # A local-only client omits that context even with its default rows.
        h.connect_remote()
        h.start("local", rows='[ui.sidebar.agents]\nrows = [["state_icon", "workspace", "tab"], ["agent"]]\n')
        h.start("remote", rows="")
        local = h.populate("local")
        for pane, _ in local:
            h.api("local", "pane.report_agent", {"pane_id": pane, "source": "test:fixture",
                                                   "agent": "codex", "state": "working", "seq": 1})
        for tab in h.api("local", "session.snapshot")["snapshot"]["tabs"]:
            h.api("local", "tab.rename", {"tab_id": tab["tab_id"], "label": "tab01"})
        config = h.config_path("local")
        original = config.read_bytes()
        store = Store(h.root / "local/config/herdr/plugins/config" / PLUGIN_ID,
                      h.root / "local/state/herdr/plugins" / PLUGIN_ID)
        h.command("local", "plugin", "link", str(ROOT / "herdr-plugin.toml"), "--enabled")
        assert h.api("local", "plugin.list")["plugins"][0]["enabled"]
        activate_by_navigation(h)
        wait(lambda: any(log.get("event") == "workspace.focused" and log["status"] == "succeeded"
                        for log in h.api("local", "plugin.log.list", {"plugin_id": PLUGIN_ID, "limit": 20})["logs"]))
        assert store.load() == Settings()
        assert worker_stopped(store.state) and config.read_bytes() == original
        assert not (store.state / "presentation.json").exists()
        terminal = h.terminal()
        try:
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: popup_open(lines) and any("Active" in line and "[No]" in line for line in lines))
            os.write(terminal.master, b"\x1bOC")
            lines = terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines)
                                  and any("View" in line and "[Edit lines]" in line for line in lines))
            assert not any("Line 1  [" in line or "Line 2  [" in line for line in lines), "Line settings appeared before opening Edit lines"
            os.write(terminal.master, b"\x1bOB\r")
            lines = terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            assert any("Line 1  [Status | Project | Agent]" in line for line in lines)
            assert any("Line 2  [Machine]" in line for line in lines)
            save_row = next(y for y, line in enumerate(lines) if "Save view" in line)
            hint_row = next(y for y, line in enumerate(lines) if "Enter cycles" in line)
            assert hint_row - save_row >= 3, "Save view is crowded against the instructions"
            os.write(terminal.master, b"\x1b")
            lines = terminal.wait(popup_open)
            assert not any("Line 1  [" in line or "Line 2  [" in line for line in lines)
            assert store.load() == Settings() and config.read_bytes() == original
            # User activates Priority from Settings; verify the captured factory view.
            os.write(terminal.master, b"\x1bOA\r")
            wait(lambda: store.load().enabled and store.load().mode == "priority")
            os.write(terminal.master, b"\x1b")
            def factory_rendered(lines):
                entries = [(y, text) for y, text in sidebar_lines(lines, 36) if "agente" in text]
                return (not popup_open(lines) and len(entries) == 3
                        and all("◐" in text and "projeto" in text and "Local" in lines[y+1][:36]
                                for y, text in entries))
            lines = terminal.wait(factory_rendered)
            entries = [(y, text) for y, text in sidebar_lines(lines, 36) if "agente" in text]
            for y, text in entries:
                assert "projeto" in text and "Local" not in text
                assert "tab01" not in text
                x = text.index("◐")
                assert x < text.index("projeto") < text.index("agente")
                assert terminal.screen.buffer[y][x].fg == "f9e2af"
                assert terminal.screen.buffer[y][text.index("projeto")].fg == "89b4fa"
                assert terminal.screen.buffer[y][text.index("agente")].fg == "bd93f9"
                assert lines[y+1][:35].strip() == "Local"
                assert terminal.screen.buffer[y+1][lines[y+1].index("Local")].fg == "6272a4"
            selected = store.load()
            h.command("local", "plugin", "action", "invoke", "restart", "--plugin", PLUGIN_ID)
            wait(lambda: not worker_stopped(store.state) and all(t.get("has_agent") for t in tokens(h, "local")))
            assert store.load() == selected
            # Restore changes actual customized profiles back to the factory snapshot.
            customized = selected.with_profile("grouped", view="agent/tab", machine_color="#abc", show_separator=True)
            customized = customized.with_profile("priority", line1=("tab",), line2=(), agent_color="#ff79c6")
            store.save(customized)
            h.command("local", "plugin", "action", "invoke", "restore", "--plugin", PLUGIN_ID)
            wait(lambda: store.load() == Settings() and worker_stopped(store.state) and native_defaults(config))
            assert not any(t.get("has_agent") for t in tokens(h, "local"))
            # The old native-only customization omitted Machine. Restore must
            # use Herdr's own defaults, showing machine/project/tab for each agent.
            lines = terminal.wait(lambda lines: not popup_open(lines)
                                  and sum("Local · projeto" in text for _, text in sidebar_lines(lines, 36)) == 3)
            assert sum("agente" in text for _, text in sidebar_lines(lines, 36)) == 3
            h.command("local", "plugin", "action", "invoke", "restart", "--plugin", PLUGIN_ID)
            activate_by_navigation(h)
            wait(lambda: store.load() == Settings() and worker_stopped(store.state) and native_defaults(config))
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: popup_open(lines) and any("Active" in line and "[No]" in line for line in lines)
                          and any("Show separator" in line and "[Off]" in line for line in lines))
            os.write(terminal.master, b"\r")
            wait(lambda: store.load().enabled and store.load().mode == "grouped")
            os.write(terminal.master, b"\x1b")
            terminal.wait(lambda lines: not popup_open(lines) and sum(line[10:16] == "agente" for line in lines) == 3)
            h.command("local", "plugin", "action", "invoke", "restore", "--plugin", PLUGIN_ID)
            wait(lambda: worker_stopped(store.state) and native_defaults(config))
        finally:
            terminal.close()
    print("PASS: installed/enabled with both No, factory Priority rendering, Settings activation, Restart and Restore defaults")


def check_runtime(priority_evidence=None):
    with HerdrHarness() as h:
        h.connect_remote()
        h.start("local", rows='[ui.sidebar.agents]\nrows = [["state_icon", "workspace", "tab"], ["agent"]]\n')
        h.start("remote", rows="")
        local = h.populate("local")
        remote = h.populate("remote")
        config = h.config_path("local")
        original = config.read_text()
        config_root = h.root / "local/config/herdr/plugins/config" / PLUGIN_ID
        state = h.root / "local/state/herdr/plugins" / PLUGIN_ID
        store = Store(config_root, state)
        store.save(Settings().with_profile("priority", line1=("status", "project"), line2=("agent",)).with_active("grouped"))
        h.command("local", "plugin", "link", str(ROOT / "herdr-plugin.toml"), "--enabled")
        # A source-restricted probe must not replace another active projection.
        h.api("local", "agent.view.set", {"source": "test:foreign", "label": "Preserve me"})
        env = h.environment("local")
        env.update(HERDR_ENV="1", HERDR_SESSION="sidebar-proof", HERDR_SOCKET_PATH=str(h.socket_path("local")))
        with patch.dict(os.environ, env):
            # Exercise subscription acceptance and delivery directly: periodic
            # snapshots alone must not mask a rejected event subscription.
            workspace = h.api("local", "session.snapshot")["snapshot"]["workspaces"][0]
            events = Events(Herdr())
            try:
                h.api("local", "workspace.rename", {"workspace_id": workspace["workspace_id"],
                                                     "label": "subscription-proof"})
                wait(events.dirty, timeout=3)
            finally:
                events.close()
                h.api("local", "workspace.rename", {"workspace_id": workspace["workspace_id"],
                                                     "label": workspace["label"]})
            try:
                Herdr().check_projection()
            except Conflict:
                pass
            else:
                raise AssertionError("Foreign projection was not detected")
        assert h.api("local", "agent.view.clear", {"source": "test:unrelated"})["active"]
        assert config.read_text() == original
        h.api("local", "agent.view.clear", {"source": "test:foreign"})
        terminal = h.terminal()
        try:
            terminal.wait(lambda lines: any("agents" in line[:36] for line in lines))
            activate_by_navigation(h)
            wait(lambda: len(tokens(h, "local")) == 3 and all(t.get("has_agent") for t in tokens(h, "local")))
            wait(lambda: len(tokens(h, "remote")) == 3 and all(t.get("has_agent") for t in tokens(h, "remote")))
            lines = terminal.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 6)
            body = sidebar_lines(lines, 36)
            # Verify defaults from the actual plugin, independently of the proof rows.
            for x, label, color in ((1, "Local", "f1fa8c"), (3, "projeto01", "89b4fa"),
                                    (10, "agente01", "bd93f9")):
                y = next(y for y, text in body if text[x:].rstrip() == label)
                assert terminal.screen.buffer[y][x].fg == color
            assert sum(bool(t.get("has_machine")) for t in tokens(h, "local")) == 1
            assert sum(bool(t.get("has_project")) for t in tokens(h, "local")) == 2
            assert store.load().show_separator is False
            assert not any(t.get("has_gap") for t in tokens(h, "local"))

            opened = h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID,
                            "entrypoint": "settings", "focus": True})
            assert opened["type"] == "ok", opened
            terminal.wait(popup_open)
            # Actual keyboard interaction with the plugin's curses popup.
            os.write(terminal.master, b"\x1bOB" * 6 + b"\r")
            wait(lambda: store.load().show_separator is True)
            wait(lambda: tokens(h, "local")[-1].get("has_gap") == "·")
            terminal.wait(lambda lines: any("[On]" in line for line in lines))
            os.write(terminal.master, b"\r")
            wait(lambda: store.load().show_separator is False)
            wait(lambda: not any(t.get("has_gap") for t in tokens(h, "local")))
            terminal.wait(lambda lines: any("[Off]" in line for line in lines))
            os.write(terminal.master, b"\x1bOA" * 4 + b"\r")
            terminal.wait(lambda lines: any("Purple" in line for line in lines))
            os.write(terminal.master, b"\x1bOB" * 7 + b"\r")
            wait(lambda: store.load().profile("grouped").machine_color == "#ff79c6")
            parsed = tomllib.loads(config.read_text())
            assert parsed["ui"]["sidebar"]["agents"]["rows"][0][0]["fg"] == "#ff79c6"
            # Closing the owned popup must not alter native agent identities.
            os.write(terminal.master, b"\x1b")
            terminal.wait(lambda lines: not popup_open(lines))
            lines = terminal.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 6)
            y = next(i for i, line in enumerate(lines) if "○ agente03" in line[:36])
            terminal.click(8, y)
            wait(lambda: h.api("local", "session.snapshot")["snapshot"]["focused_pane_id"] == local[-1][0])

            # Mode changes presentation only; select native order independently.
            original_sort = tomllib.loads(config.read_text())["ui"]["agent_panel_sort"]
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID,
                  "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: any("Active" in line and "[Yes]" in line for line in lines))
            os.write(terminal.master, b"\x1bOC")
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            assert store.load().mode == "grouped", "Browsing a tab activated it"
            os.write(terminal.master, b"\r")
            wait(lambda: store.load().mode == "priority")
            wait(lambda: all(not t.get("has_machine") and t.get("has_project") and not t.get("has_agent_prefix")
                             for machine in ("local", "remote") for t in tokens(h, machine)))
            assert tomllib.loads(config.read_text())["ui"]["agent_panel_sort"] == original_sort
            os.write(terminal.master, b"\x1b")
            lines = terminal.wait(lambda lines: sum("agente" in line[:36] for line in lines) == 6
                                  and not popup_open(lines))
            heading_y = next(i for i, line in enumerate(lines) if line[1:36].strip().startswith("agents"))
            assert "grouped" in lines[heading_y], "Settings unexpectedly changed native sort"
            terminal.click(lines[heading_y].index("grouped") + 1, heading_y)
            terminal.wait(lambda lines: "priority" in lines[heading_y])
            h.api("local", "pane.report_agent", {"pane_id": local[-1][0], "source": "test:fixture",
                                                  "agent": "codex", "state": "working", "seq": 1})
            h.api("remote", "pane.report_agent", {"pane_id": remote[1][0], "source": "test:fixture",
                                                   "agent": "codex", "state": "blocked", "seq": 1})
            def priority_ready(lines):
                visible = [(y, text) for y, text in sidebar_lines(lines, 36) if "agente" in text]
                return (len(visible) == 6 and visible[0][1].startswith("   agente02")
                        and lines[visible[0][0]-1].startswith(" × projeto01")
                        and visible[1][1].startswith("   agente03")
                        and lines[visible[1][0]-1].startswith(" ◐ projeto02"))
            lines = terminal.wait(priority_ready)
            visible = [(y, text) for y, text in sidebar_lines(lines, 36) if "agente" in text]
            assert terminal.screen.buffer[visible[0][0]-1][1].fg == "f38ba8"
            assert terminal.screen.buffer[visible[1][0]-1][1].fg == "f9e2af"
            assert [y for y, _ in visible] == list(range(visible[0][0], visible[0][0]+12, 2))
            assert not any(t.get("has_gap") for machine in ("local", "remote") for t in tokens(h, machine))
            for y, text in visible:
                assert text.index("agente") == 3, text
                assert terminal.screen.buffer[y][3].fg == "bd93f9"
                context = lines[y-1][:35]
                assert context.index("projeto") == 3, context
                assert "Local" not in context and "machine02" not in context
                assert terminal.screen.buffer[y-1][3].fg == "89b4fa"
            if priority_evidence:
                priority_evidence.parent.mkdir(parents=True, exist_ok=True)
                rows = [(row_y, lines[row_y][:35]) for y, _ in visible for row_y in (y-1, y)]
                capture_svg(terminal.screen, rows, priority_evidence.with_suffix(".svg"), 36)
                priority_evidence.write_text(json.dumps({"herdr": "0.9.3", "protocol": 22,
                    "mode": "priority", "width": 36, "native_order": "priority",
                    "rows": [text.rstrip() for _, text in rows],
                    "transport": "local SSH shim, real Herdr servers and bridges"},
                    ensure_ascii=False, indent=2)+"\n")
            # Both context and agent rows focus the same real pane.
            terminal.click(12, visible[0][0]-1)
            wait(lambda: h.api("remote", "session.snapshot")["snapshot"]["focused_pane_id"] == remote[1][0])
            lines = terminal.wait(lambda lines: any("new · machine02" in line[:36] for line in lines))
            local_y = next(i for i, line in enumerate(lines)
                           if "agente03" in line[:36] and lines[i-1].startswith(" ◐ projeto02"))
            terminal.click(8, local_y)
            wait(lambda: h.api("local", "session.snapshot")["snapshot"]["focused_pane_id"] == local[-1][0])
            terminal.wait(lambda lines: any("new · Local" in line[:36] for line in lines))

            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID,
                  "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: any("Active" in line and "[Yes]" in line for line in lines))
            os.write(terminal.master, b"\x1bOD")
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            os.write(terminal.master, b"\r")
            wait(lambda: store.load().mode == "grouped")
            wait(lambda: all(t.get("has_agent_prefix") for machine in ("local", "remote") for t in tokens(h, machine)))
            os.write(terminal.master, b"\x1b")
            lines = terminal.wait(lambda lines: not popup_open(lines))
            heading_y = next(i for i, line in enumerate(lines) if line[1:36].strip().startswith("agents"))
            assert "priority" in lines[heading_y], "Returning to Grouped changed native order"
            terminal.click(lines[heading_y].index("priority") + 1, heading_y)
            terminal.wait(lambda lines: "grouped" in lines[heading_y])
            for machine, pane in (("local", local[-1][0]), ("remote", remote[1][0])):
                h.api(machine, "pane.report_agent", {"pane_id": pane, "source": "test:fixture",
                                                     "agent": "codex", "state": "idle", "seq": 2})
                h.api(machine, "pane.focus", {"pane_id": pane})
            terminal.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 6)

            # Native renames relocate headings without losing or renaming agents.
            h.api("local", "workspace.rename", {"workspace_id": "w1", "label": "renamed-project"})
            wait(lambda: any("renamed-project" in t.get("has_project", "") for t in tokens(h, "local")))
            # Drop an anchor fixture while retaining its real terminal/pane.
            h.api("local", "pane.release_agent", {"pane_id": local[0][0], "source": "test:fixture", "agent": "codex"})
            wait(lambda: len(tokens(h, "local")) == 2 and tokens(h, "local")[0].get("has_machine") == "Local")
            panes = h.api("local", "session.snapshot")["snapshot"]["panes"]
            wait(lambda: not next(p for p in h.api("local", "session.snapshot")["snapshot"]["panes"]
                                 if p["pane_id"] == local[0][0]).get("tokens", {}).get(store.token_names()["has_agent"]))
            h.api("local", "pane.report_agent", {"pane_id": local[0][0], "source": "test:fixture",
                                                  "agent": "codex", "state": "idle"})
            h.api("local", "agent.rename", {"target": local[0][0], "name": "agente01"})
            wait(lambda: len(tokens(h, "local")) == 3 and tokens(h, "local")[0].get("has_machine") == "Local")
            moved = h.api("local", "pane.move", {"pane_id": local[0][0], "destination": {
                "type": "new_tab", "workspace_id": "w2", "label": "moved-fixture"}, "focus": False})
            new_pane = moved["move_result"]["pane"]["pane_id"]
            assert new_pane != local[0][0]
            local[0] = (new_pane, local[0][1])
            wait(lambda: sum(bool(t.get("has_machine")) for t in tokens(h, "local")) == 1
                 and tokens(h, "local")[0].get("has_machine") == "Local"
                 and sum(bool(t.get("has_project")) for t in tokens(h, "local")) == 2)

            # Stop only the remote server created by this harness. Local work
            # must still reconcile while the remote bridge is unavailable.
            remote_server = h.processes[1]
            remote_server.terminate()
            remote_server.wait(timeout=5)
            h.api("local", "workspace.rename", {"workspace_id": "w1", "label": "local-while-offline"})
            wait(lambda: any("local-while-offline" in t.get("has_project", "") for t in tokens(h, "local")), timeout=3)
            h.start("remote", rows="")
            restored = h.api("remote", "session.snapshot")["snapshot"]["panes"]
            for pane, name in zip(restored, ("agente01", "agente02", "agente03")):
                h.api("remote", "pane.report_agent", {"pane_id": pane["pane_id"], "source": "test:fixture",
                                                       "agent": "codex", "state": "idle"})
                h.api("remote", "agent.rename", {"target": pane["pane_id"], "name": name})
            wait(lambda: len(tokens(h, "remote")) == 3 and all(t.get("has_agent") for t in tokens(h, "remote")))
            h.api("local", "pane.report_metadata", {"pane_id": local[0][0], "source": "test:other",
                                                     "tokens": {"foreign": "preserved"}})
            h.command("local", "plugin", "disable", PLUGIN_ID)
            wait(lambda: worker_stopped(state))
            wait(lambda: not any(t.get("has_agent") for t in tokens(h, "local")))
            wait(lambda: not any(t.get("has_agent") for t in tokens(h, "remote")))
            assert not any(t.get("has_agent_prefix") for t in tokens(h, "local"))
            assert not any(t.get("has_agent_prefix") for t in tokens(h, "remote"))
            assert config.read_text() == original, "Disable did not restore original config bytes"
            assert any(t.get("foreign") == "preserved" for t in tokens(h, "local"))
            assert store.load().profile("grouped").machine_color == "#ff79c6", "Disable removed preferences"
        finally:
            h.command("local", "plugin", "disable", PLUGIN_ID, check=False)
            wait(lambda: worker_stopped(state), timeout=25)
            terminal.close()
    print("PASS: real plugin, asynchronous remote publication, settings popup, native mouse and disable cleanup")


# From the original two-line layout, build the user's example entirely in the
# real popup: move Status to line 2 before Agent, add Tab there, and put Machine
# before Project on line 1. Selection ends on Machine (field index 3).
CUSTOM_PRIORITY_KEYS = (b"\r\x1bOD" + b"\x1bOB" * 2 + b"\r\r"
                        + b"\x1bOB\r\x1bOD")
SAVE_FROM_MACHINE = b"\x1bOB" * 2 + b"\r"


def check_views():
    """Exercise the fixed tree and arbitrary native fields through the real UI."""
    with HerdrHarness() as h:
        h.connect_remote()
        h.start("local", rows="")
        h.start("remote", rows="")
        local, remote = h.populate("local"), h.populate("remote")
        for index, (pane, _) in enumerate(remote, 4):
            h.api("remote", "agent.rename", {"target": pane, "name": f"agente0{index}"})
        for machine, tab_name in (("local", "tab01"), ("remote", "tab02")):
            for tab in h.api(machine, "session.snapshot")["snapshot"]["tabs"]:
                h.api(machine, "tab.rename", {"tab_id": tab["tab_id"], "label": tab_name})
        config = h.config_path("local")
        original = config.read_bytes()
        store = Store(h.root / "local/config/herdr/plugins/config" / PLUGIN_ID,
                      h.root / "local/state/herdr/plugins" / PLUGIN_ID)
        store.save(Settings().with_profile("priority", line1=("status", "project"), line2=("agent",)).with_active("grouped"))
        h.command("local", "plugin", "link", str(ROOT / "herdr-plugin.toml"), "--enabled")
        activate_by_navigation(h)
        wait(lambda: all(len(tokens(h, m)) == 3 and all(t.get("has_agent") for t in tokens(h, m))
                         for m in ("local", "remote")))
        terminal = h.terminal()
        try:
            for view in GROUPED_VIEWS:
                current = GROUPED_VIEWS.index(store.load().profile("grouped").view)
                h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
                terminal.wait(popup_open)
                os.write(terminal.master, b"\x1bOB\r")
                lines = terminal.wait(lambda lines: any("    Agent / Tab" in line for line in lines))
                assert not any("Agent / Project" in line for line in lines), "Grouped must offer only two views"
                delta = GROUPED_VIEWS.index(view) - current
                os.write(terminal.master, (b"\x1bOB" if delta >= 0 else b"\x1bOA") * abs(delta) + b"\r")
                terminal.wait(lambda lines: any("Saved" in line for line in lines))
                assert store.load().profile("grouped").view == view
                os.write(terminal.master, b"\x1b")
                def rendered(lines):
                    if popup_open(lines):
                        return False
                    body = [text for _, text in sidebar_lines(lines, 36)]
                    return (sum("agente" in text for text in body) == 6
                            and sum("projeto" in text for text in body) == 4
                            and sum("Local" in text or "machine02" in text for text in body) == 2
                            and sum("tab01" in text or "tab02" in text for text in body) == 6 * (view == "agent/tab"))
                lines = terminal.wait(rendered)
                entries = [(y, text) for y, text in sidebar_lines(lines, 36) if "agente" in text]
                for y, text in entries:
                    assert text.index("agente") == 10, text
                    assert terminal.screen.buffer[y][10].fg == "bd93f9"
                    if view == "agent/tab":
                        tab_x = text.index("tab0")
                        assert terminal.screen.buffer[y][tab_x].fg == "6272a4"
                remote_y = next(y for y, text in entries if "agente05" in text)
                terminal.click(13, remote_y)
                wait(lambda: h.api("remote", "session.snapshot")["snapshot"]["focused_pane_id"] == remote[1][0])
                lines = terminal.wait(lambda lines: rendered(lines) and any("new · machine02" in line[:36] for line in lines))
                local_y = next(y for y, text in sidebar_lines(lines, 36) if "agente02" in text)
                terminal.click(13, local_y)
                wait(lambda: h.api("local", "session.snapshot")["snapshot"]["focused_pane_id"] == local[1][0])
                terminal.wait(lambda lines: any("new · Local" in line[:36] for line in lines))

            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(popup_open)
            os.write(terminal.master, b"\x1bOC\r")
            wait(lambda: store.load().mode == "priority")
            terminal.wait(lambda lines: any("Active" in line and "[Yes]" in line for line in lines))
            os.write(terminal.master, b"\x1bOB\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            before = store.preferences.read_bytes(), config.read_bytes()
            os.write(terminal.master, CUSTOM_PRIORITY_KEYS)
            terminal.wait(lambda lines: any("Line 1  [Machine | Project]" in line for line in lines)
                          and any("Line 2  [Status | Agent | Tab]" in line for line in lines))
            assert (store.preferences.read_bytes(), config.read_bytes()) == before, "Draft changed live settings"
            os.write(terminal.master, b"\x1b")
            terminal.wait(popup_open)
            assert (store.preferences.read_bytes(), config.read_bytes()) == before, "Cancel changed settings"
            os.write(terminal.master, b"\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            os.write(terminal.master, CUSTOM_PRIORITY_KEYS + SAVE_FROM_MACHINE)
            terminal.wait(lambda lines: any("Saved" in line for line in lines))
            assert store.load().profile("priority").line1 == ("machine", "project")
            assert store.load().profile("priority").line2 == ("status", "agent", "tab")
            os.write(terminal.master, b"\x1b")
            def priority_rendered(lines):
                entries = [(y, text) for y, text in sidebar_lines(lines, 36) if "agente" in text]
                return (not popup_open(lines) and len(entries) == 6
                        and all(text[5:11] == "agente" and "tab0" in text
                                and "projeto" in lines[y-1][:35]
                                and ("Local" in lines[y-1][:35] or "machine02" in lines[y-1][:35])
                                for y, text in entries))
            lines = terminal.wait(priority_rendered)
            for y, text in sidebar_lines(lines, 36):
                if "agente" not in text:
                    continue
                assert "tab0" in text, text
                assert "projeto" in lines[y-1][:35]
                assert "Local" in lines[y-1][:35] or "machine02" in lines[y-1][:35]
            # Both rows still focus their original native local/remote pane.
            remote_y = next(y for y, text in sidebar_lines(lines, 36) if "agente05" in text)
            terminal.click(8, remote_y-1)
            wait(lambda: h.api("remote", "session.snapshot")["snapshot"]["focused_pane_id"] == remote[1][0])
            lines = terminal.wait(lambda lines: any("new · machine02" in line[:36] for line in lines))
            local_y = next(y for y, text in sidebar_lines(lines, 36) if "agente02" in text)
            terminal.click(8, local_y)
            wait(lambda: h.api("local", "session.snapshot")["snapshot"]["focused_pane_id"] == local[1][0])
            terminal.wait(lambda lines: any("new · Local" in line[:36] for line in lines))
            h.api("local", "pane.report_agent", {"pane_id": local[-1][0], "source": "test:fixture",
                                                  "agent": "codex", "state": "working", "seq": 1})
            # Move native Status after Agent and Tab; its lifecycle color stays native.
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(popup_open)
            os.write(terminal.master, b"\x1bOB\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            os.write(terminal.master, b"\x1bOC" * 2 + b"\x1bOB" * 5 + b"\r")
            terminal.wait(lambda lines: any("Saved" in line for line in lines))
            assert store.load().profile("priority").line2 == ("agent", "tab", "status")
            os.write(terminal.master, b"\x1b")
            lines = terminal.wait(lambda lines: not popup_open(lines)
                                  and any("agente03 · tab01 · ◐" in line[:36] for line in lines))
            y = next(i for i, line in enumerate(lines) if "agente03 · tab01 · ◐" in line[:36])
            x = lines[y].index("◐")
            assert terminal.screen.buffer[y][x].fg == "f9e2af"
            # Put Status between Machine and Project on line 1, rather than line 2.
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(popup_open)
            os.write(terminal.master, b"\x1bOB\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            os.write(terminal.master, b"\r\r\x1bOD" + b"\x1bOB" * 5 + b"\r")
            terminal.wait(lambda lines: any("Saved" in line for line in lines))
            assert store.load().profile("priority").line1 == ("machine", "status", "project")
            os.write(terminal.master, b"\x1b")
            lines = terminal.wait(lambda lines: not popup_open(lines)
                                  and any("Local · ◐ projeto02" in line[:36] for line in lines))
            y = next(i for i, line in enumerate(lines) if "Local · ◐ projeto02" in line[:36])
            assert terminal.screen.buffer[y][lines[y].index("◐")].fg == "f9e2af"
            # Hide every field except Tab, retaining six native identities and focus.
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(popup_open)
            os.write(terminal.master, b"\x1bOB\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            os.write(terminal.master, b"\r\r\x1bOB\r" + b"\x1bOB" * 2
                     + b"\r\r\x1bOB\r\r\x1bOB\r")
            terminal.wait(lambda lines: any("Saved" in line for line in lines))
            assert store.load().profile("priority").line1 == ()
            assert store.load().profile("priority").line2 == ("tab",)
            os.write(terminal.master, b"\x1b")
            def tab_only(lines):
                if popup_open(lines):
                    return False
                body = [text for _, text in sidebar_lines(lines, 36) if text.strip()]
                return len(body) == 6 and all(text.strip() in ("tab01", "tab02") for text in body)
            lines = terminal.wait(tab_only)
            assert all(len(h.api(m, "session.snapshot")["snapshot"]["agents"]) == 3 for m in ("local", "remote"))
            wait(lambda: all(not t.get("has_agent") and not t.get("has_machine") and not t.get("has_project")
                             for m in ("local", "remote") for t in tokens(h, m)))
            remote_y = [y for y, text in sidebar_lines(lines, 36) if text.strip() == "tab02"][-1]
            terminal.click(3, remote_y)
            wait(lambda: h.api("remote", "session.snapshot")["snapshot"]["focused_pane_id"] == remote[-1][0])
            lines = terminal.wait(lambda lines: tab_only(lines) and any("new · machine02" in line[:36] for line in lines))
            local_y = next(y for y, text in sidebar_lines(lines, 36) if text.strip() == "tab01")
            terminal.click(3, local_y)
            wait(lambda: h.api("local", "session.snapshot")["snapshot"]["focused_pane_id"] == local[0][0])
            terminal.wait(lambda lines: tab_only(lines) and any("new · Local" in line[:36] for line in lines))
            # An empty draft must be rejected without overwriting the valid layout.
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(popup_open)
            os.write(terminal.master, b"\x1bOB\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            before = store.preferences.read_bytes(), config.read_bytes()
            os.write(terminal.master, b"\x1bOB" * 2 + b"\r" + b"\x1bOB" * 3 + b"\r")
            terminal.wait(lambda lines: any("Choose at least one field" in line for line in lines))
            assert (store.preferences.read_bytes(), config.read_bytes()) == before
            os.write(terminal.master, b"\x1b")
            terminal.wait(popup_open)
            os.write(terminal.master, b"\x1b")
            terminal.wait(tab_only)
            assert tomllib.loads(config.read_text())["ui"]["agent_panel_sort"] == "spaces"
            h.command("local", "plugin", "action", "invoke", "restore", "--plugin", PLUGIN_ID)
            wait(lambda: not any(t.get("has_agent") for m in ("local", "remote") for t in tokens(h, m)))
            wait(lambda: config.read_bytes() == original)
            print("PASS: fixed Grouped tree, optional native Tab, Priority draft/cancel/order, movable native Status and remote focus")
        finally:
            terminal.close()


def check_profiles():
    """Editing another tab is independent of activating its live presentation."""
    with HerdrHarness() as h:
        h.start("local", rows="")
        local = h.populate("local")
        for pane, _ in local:
            h.api("local", "pane.report_agent", {"pane_id": pane, "source": "test:fixture",
                                                   "agent": "codex", "state": "working", "seq": 1})
        for tab in h.api("local", "session.snapshot")["snapshot"]["tabs"]:
            h.api("local", "tab.rename", {"tab_id": tab["tab_id"], "label": "tab01"})
        config = h.config_path("local")
        original = config.read_bytes()
        store = Store(h.root / "local/config/herdr/plugins/config" / PLUGIN_ID,
                      h.root / "local/state/herdr/plugins" / PLUGIN_ID)
        store.save(Settings().with_profile("priority", line1=("status", "project"), line2=("agent",)).with_active("grouped"))
        h.command("local", "plugin", "link", str(ROOT / "herdr-plugin.toml"), "--enabled")
        activate_by_navigation(h)
        wait(lambda: len(tokens(h, "local")) == 3 and all(t.get("has_agent") for t in tokens(h, "local")))
        installed = config.read_bytes()
        grouped = store.load().profile("grouped")
        terminal = h.terminal()
        try:
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: any("Grouped | Priority" in line for line in lines)
                          and any("Active" in line and "[Yes]" in line for line in lines))
            os.write(terminal.master, b"\x1bOC")
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            assert store.load().mode == "grouped"
            selected = 0
            for index, name, field, expected in (
                    (2, "Pink", "machine_color", "#ff79c6"),
                    (3, "Orange", "project_color", "#ffb86c"),
                    (4, "Cyan", "agent_color", "#8be9fd"),
                    (5, "Green", "tab_color", "#50fa7b")):
                delta = index - selected
                os.write(terminal.master, (b"\x1bOB" if delta >= 0 else b"\x1bOA") * abs(delta) + b"\r")
                terminal.wait(lambda lines: any("    " + name in line for line in lines))
                # The picker starts at the saved color, including explicit factory colors.
                current = getattr(store.load().profile("priority"), field)
                start = next(i for i, (_, color) in enumerate(OPTIONS) if color == current)
                target = next(i for i, (label, _) in enumerate(OPTIONS) if label == name)
                steps = (target - start) % len(OPTIONS)
                os.write(terminal.master, b"\x1bOB" * steps + b"\r")
                wait(lambda: getattr(store.load().profile("priority"), field) == expected)
                terminal.wait(lambda lines: any("Saved" in line for line in lines))
                selected = index
                assert store.load().mode == "grouped"
                assert store.load().profile("grouped") == grouped
                assert config.read_bytes() == installed, "Editing the inactive tab changed live presentation"
            os.write(terminal.master, b"\x1bOA" * 4 + b"\r")
            terminal.wait(lambda lines: any("Priority view" in line for line in lines))
            os.write(terminal.master, CUSTOM_PRIORITY_KEYS + SAVE_FROM_MACHINE)
            terminal.wait(lambda lines: any("Saved" in line for line in lines))
            priority = store.load().profile("priority")
            assert priority.line1 == ("machine", "project")
            assert priority.line2 == ("status", "agent", "tab")
            assert config.read_bytes() == installed
            os.write(terminal.master, b"\x1bOD")
            terminal.wait(lambda lines: any("Active" in line and "[Yes]" in line for line in lines)
                          and any("Show separator" in line and "[Off]" in line for line in lines))
            # Both No restores native rows, clears tokens, and remembers both profiles.
            os.write(terminal.master, b"\x1bOA\r")
            wait(lambda: not store.load().enabled and worker_stopped(store.state)
                 and config.read_bytes() == original)
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            assert not any(t.get("has_agent") for t in tokens(h, "local"))
            os.write(terminal.master, b"\x1bOC")
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            os.write(terminal.master, b"\r")
            wait(lambda: store.load().enabled and store.load().mode == "priority")
            terminal.wait(lambda lines: any("Active" in line and "[Yes]" in line for line in lines))
            assert not any("Show separator" in line for line in terminal.screen.display)
            os.write(terminal.master, b"\x1b")
            lines = terminal.wait(lambda lines: sum(line[5:11] == "agente" for line in lines) == 3
                                  and not popup_open(lines))
            for y, text in sidebar_lines(lines, 36):
                if "agente" not in text:
                    continue
                assert terminal.screen.buffer[y][5].fg == "8be9fd"
                assert terminal.screen.buffer[y][text.index("tab01")].fg == "50fa7b"
                context = lines[y-1][:35]
                assert terminal.screen.buffer[y-1][context.index("projeto")].fg == "ffb86c"
                assert terminal.screen.buffer[y-1][context.index("Local")].fg == "ff79c6"
                assert lines[y][3] == "◐" and terminal.screen.buffer[y][3].fg == "f9e2af"
            assert store.load().profile("grouped") == grouped
            assert store.load().profile("priority") == priority
            # Reopen and pause Priority too; navigation and editing cannot reactivate it.
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: any("Machine color" in line and "[Pink]" in line for line in lines)
                          and any("Active" in line and "[Yes]" in line for line in lines))
            os.write(terminal.master, b"\r")
            wait(lambda: not store.load().enabled and worker_stopped(store.state)
                 and config.read_bytes() == original)
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            os.write(terminal.master, b"\x1b")
            terminal.wait(lambda lines: not popup_open(lines))
            logs = h.api("local", "plugin.log.list", {"plugin_id": PLUGIN_ID, "limit": 30})["logs"]
            last_event = max(log["started_unix_ms"] for log in logs)
            activate_by_navigation(h)
            wait(lambda: any(log.get("event") == "workspace.focused" and log["status"] == "succeeded"
                            for log in h.api("local", "plugin.log.list", {"plugin_id": PLUGIN_ID, "limit": 30})["logs"]
                            if log["started_unix_ms"] >= last_event))
            assert worker_stopped(store.state) and config.read_bytes() == original
            assert not any(t.get("has_agent") for t in tokens(h, "local"))
            h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines)
                          and any("Machine color" in line and "[Pink]" in line for line in lines))
            os.write(terminal.master, b"\x1bOD")
            terminal.wait(lambda lines: any("Machine color" in line and "[Default]" in line for line in lines)
                          and any("Active" in line and "[No]" in line for line in lines))
            # Edit an inactive profile while both No without publishing rows or tokens.
            os.write(terminal.master, b"\x1bOB" * 6 + b"\r")
            terminal.wait(lambda lines: any("Show separator" in line and "[On]" in line for line in lines))
            assert not store.load().enabled and config.read_bytes() == original
            assert worker_stopped(store.state)
            os.write(terminal.master, b"\r" + b"\x1bOA" * 6 + b"\r")
            wait(lambda: store.load().enabled and store.load().mode == "grouped")
            terminal.wait(lambda lines: any("Active" in line and "[Yes]" in line for line in lines))
            os.write(terminal.master, b"\x1bOC")
            terminal.wait(lambda lines: any("Active" in line and "[No]" in line for line in lines))
            os.write(terminal.master, b"\x1b")
            terminal.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 3
                          and not popup_open(lines))
            assert config.read_bytes() == installed
            assert store.load().profile("priority") == priority
            h.command("local", "plugin", "action", "invoke", "restore", "--plugin", PLUGIN_ID)
            wait(lambda: config.read_bytes() == original and worker_stopped(store.state))
            print("PASS: independent profiles, both No/native cleanup, durable pause, exclusive reactivation and native status")
        finally:
            terminal.close()


def check_independent_installations():
    """A remote installation cannot overwrite the viewing installation's tokens."""
    with HerdrHarness() as h:
        h.connect_remote()
        stores = {}
        for machine in ("local", "remote"):
            h.start(machine, rows="")
            h.populate(machine)
            store = Store(h.root / machine / "config/herdr/plugins/config" / PLUGIN_ID,
                          h.root / machine / "state/herdr/plugins" / PLUGIN_ID)
            mode = "priority" if machine == "local" else "grouped"
            store.save(Settings().with_profile("priority", line1=("project", "machine"),
                                               line2=("status", "agent")).with_active(mode))
            stores[machine] = store
            h.command(machine, "plugin", "link", str(ROOT / "herdr-plugin.toml"), "--enabled")
            snapshot = h.api(machine, "session.snapshot")["snapshot"]
            target = next(w for w in snapshot["workspaces"] if not w["focused"])
            h.api(machine, "workspace.focus", {"workspace_id": target["workspace_id"]})
        local_terminal, remote_terminal = h.terminal(), h.terminal("remote")
        try:
            def independent():
                from_viewer = tokens(h, "remote")
                from_remote = tokens(h, "remote", origin="remote")
                return (all(t.get("has_machine") == "machine02" and t.get("has_agent") for t in from_viewer)
                        and [t.get("has_machine") for t in from_remote] == ["Local", None, None]
                        and all(t.get("has_agent_prefix") for t in from_remote))
            wait(independent)
            lines = local_terminal.wait(lambda lines: sum("machine02" in text for _, text in sidebar_lines(lines, 36)) == 3)
            remote_terminal.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 3)
            # Open remote Settings through the viewer connected to that machine.
            remote_row = next(y for y, text in sidebar_lines(lines, 36) if "machine02" in text)
            local_terminal.click(5, remote_row + 1)
            h.command("remote", "pane", "run", "w1:p1", "printf 'REMOTE_READY\\n'")
            local_terminal.wait(lambda lines: any("REMOTE_READY" in line[36:] for line in lines))
            h.api("remote", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
            local_terminal.wait(popup_open)
            os.write(local_terminal.master, b"\x1bOB" * 4 + b"\r")
            local_terminal.wait(lambda lines: any("Pink" in line for line in lines))
            os.write(local_terminal.master, b"\x1bOB" * 7 + b"\r")
            wait(lambda: stores["remote"].load().grouped.agent_color == "#ff79c6")
            os.write(local_terminal.master, b"\x1b")
            local_terminal.wait(lambda lines: not popup_open(lines))
            remote_terminal.wait(lambda lines: not popup_open(lines))
            # Observe more than two remote reconciliation intervals, including refreshes.
            deadline = time.monotonic() + 11
            while time.monotonic() < deadline:
                assert independent(), "Independent installations replaced each other's presentation"
                local_lines = local_terminal.read(.05)
                remote_lines = remote_terminal.read(.05)
                assert sum("machine02" in text for _, text in sidebar_lines(local_lines, 36)) == 3
                assert sum(line[10:16] == "agente" for line in remote_lines) == 3
            # Cleanup of one installation is restricted to its own metadata namespace.
            h.command("local", "plugin", "disable", PLUGIN_ID)
            wait(lambda: worker_stopped(stores["local"].state))
            assert not any(t.get("has_agent") for t in tokens(h, "remote"))
            assert [t.get("has_machine") for t in tokens(h, "remote", origin="remote")] == ["Local", None, None]
            assert all(t.get("has_agent") for t in tokens(h, "remote", origin="remote"))
        finally:
            for machine in ("local", "remote"):
                h.command(machine, "plugin", "disable", PLUGIN_ID, check=False)
            for store in stores.values():
                wait(lambda: worker_stopped(store.state), timeout=25)
            local_terminal.close()
            remote_terminal.close()
    print("PASS: two active installations, remote Settings, stable native rendering and independent cleanup")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--priority-evidence", type=Path)
    args = parser.parse_args()
    check_activation()
    check_runtime(args.priority_evidence)
    check_views()
    check_profiles()
    check_independent_installations()
    for width in (18, 22, 36):
        visual_check(width, args.evidence)
    visual_check(36, show_separator=True)


if __name__ == "__main__":
    main()
