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
from configuration import Conflict, PLUGIN_ID, Store
from runtime import Events, Herdr
from herdr_harness import HerdrHarness
from check_visual import check as visual_check, sidebar_lines

ROOT = Path(__file__).resolve().parents[1]


def wait(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError("Isolated integration condition timed out")


def tokens(h, machine):
    return [a.get("tokens", {}) for a in h.api(machine, "session.snapshot")["snapshot"]["agents"]]


def worker_stopped(state):
    for path in state.glob("local-*.lock"):
        with path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
    return True


def check_runtime():
    with HerdrHarness() as h:
        h.connect_remote()
        h.start("local", rows='[ui.sidebar.agents]\nrows = [["state_icon", "workspace", "tab"], ["agent"]]\n')
        h.start("remote", rows="")
        local = h.populate("local")
        h.populate("remote")
        config = h.config_path("local")
        original = config.read_text()
        config_root = h.root / "local/config/herdr/plugins/config" / PLUGIN_ID
        state = h.root / "local/state/herdr/plugins" / PLUGIN_ID
        store = Store(config_root, state)
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
            h.command("local", "plugin", "action", "invoke", "apply", "--plugin", PLUGIN_ID)
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
            wait(lambda: tokens(h, "local")[-1].get("has_gap") == "·")

            opened = h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID,
                            "entrypoint": "settings", "focus": True})
            assert opened["type"] == "ok", opened
            terminal.wait(lambda lines: any("Show separator" in line for line in lines))
            # Actual keyboard interaction with the plugin's curses popup.
            os.write(terminal.master, b"\x1bOB\x1bOB\x1bOB\r")
            wait(lambda: store.load().show_separator is False)
            wait(lambda: not any(t.get("has_gap") for t in tokens(h, "local")))
            terminal.wait(lambda lines: any("[Off]" in line for line in lines))
            os.write(terminal.master, b"\x1bOA\x1bOA\x1bOA\r")
            terminal.wait(lambda lines: any("Purple" in line for line in lines))
            os.write(terminal.master, b"\x1bOB" * 7 + b"\r")
            wait(lambda: store.load().machine_color == "#ff79c6")
            parsed = tomllib.loads(config.read_text())
            assert parsed["ui"]["sidebar"]["agents"]["rows"][0][0]["fg"] == "#ff79c6"
            # Closing the owned popup must not alter native agent identities.
            os.write(terminal.master, b"\x1b")
            terminal.wait(lambda lines: not any("Show separator" in line for line in lines))
            lines = terminal.wait(lambda lines: sum(line[10:16] == "agente" for line in lines) == 6)
            y = next(i for i, line in enumerate(lines) if "○ agente03" in line[:36])
            terminal.click(8, y)
            wait(lambda: h.api("local", "session.snapshot")["snapshot"]["focused_pane_id"] == local[-1][0])

            # Native renames relocate headings without losing or renaming agents.
            h.api("local", "workspace.rename", {"workspace_id": "w1", "label": "renamed-project"})
            wait(lambda: any("renamed-project" in t.get("has_project", "") for t in tokens(h, "local")))
            # Drop an anchor fixture while retaining its real terminal/pane.
            h.api("local", "pane.release_agent", {"pane_id": local[0][0], "source": "test:fixture", "agent": "codex"})
            wait(lambda: len(tokens(h, "local")) == 2 and tokens(h, "local")[0].get("has_machine") == "Local")
            panes = h.api("local", "session.snapshot")["snapshot"]["panes"]
            wait(lambda: not next(p for p in h.api("local", "session.snapshot")["snapshot"]["panes"]
                                 if p["pane_id"] == local[0][0]).get("tokens", {}).get("has_agent"))
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
            assert store.load().machine_color == "#ff79c6", "Disable removed preferences"
        finally:
            h.command("local", "plugin", "disable", PLUGIN_ID, check=False)
            wait(lambda: worker_stopped(state), timeout=25)
            terminal.close()
    print("PASS: real plugin, asynchronous remote publication, settings popup, native mouse and disable cleanup")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    check_runtime()
    for width in (18, 22, 36):
        visual_check(width, args.evidence)


if __name__ == "__main__":
    main()
