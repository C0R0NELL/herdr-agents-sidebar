#!/usr/bin/env python3
"""Capture factory layouts through the real settings popup in isolated Herdr."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tomllib

from check_herdr import ROOT, popup_open, tokens, wait, worker_stopped
from check_visual import capture_svg, sidebar_lines
from configuration import DARK_BLUE, DEFAULT_COLORS, PLUGIN_ID, Settings, Store
from herdr_harness import HerdrHarness


def capture(output):
    output.mkdir(parents=True, exist_ok=True)
    width = 36
    with HerdrHarness() as h:
        h.connect_remote()
        for machine in ("local", "remote"):
            h.start(machine, width=width, rows="")
            agents = h.populate(machine)
            snapshot = h.api(machine, "session.snapshot")["snapshot"]
            for index, workspace in enumerate(snapshot["workspaces"], 1):
                h.api(machine, "workspace.rename", {"workspace_id": workspace["workspace_id"],
                                                      "label": f"project{index:02}"})
            for index, tab in enumerate(snapshot["tabs"], 1):
                h.api(machine, "tab.rename", {"tab_id": tab["tab_id"], "label": f"tab{index:02}"})
            for index, (pane, _) in enumerate(agents, 1 if machine == "local" else 4):
                h.api(machine, "agent.rename", {"target": pane, "name": f"agent{index:02}"})
                state = "working" if index == 2 else "blocked" if index == 5 else "idle"
                h.api(machine, "pane.report_agent", {"pane_id": pane, "source": "test:fixture",
                                                      "agent": "codex", "state": state, "seq": 1})
        config = h.config_path("local")
        store = Store(h.root / "local/config/herdr/plugins/config" / PLUGIN_ID,
                      h.root / "local/state/herdr/plugins" / PLUGIN_ID)
        h.command("local", "plugin", "link", str(ROOT / "herdr-plugin.toml"), "--enabled")
        version = h.command("local", "--version").stdout.strip()
        terminal = h.terminal()
        try:
            for mode in ("grouped", "priority"):
                h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID,
                                                      "entrypoint": "settings", "focus": True})
                terminal.wait(popup_open)
                if mode == "priority":
                    os.write(terminal.master, b"\x1bOC")
                    terminal.wait(lambda lines: any("View" in line and "[Edit lines]" in line for line in lines))
                os.write(terminal.master, b"\r")
                wait(lambda: store.load() == Settings().with_active(mode))
                wait(lambda: all(t.get("has_agent") for machine in ("local", "remote") for t in tokens(h, machine)))
                os.write(terminal.master, b"\x1b")
                def rendered(lines):
                    rows = [(y, text) for y, text in sidebar_lines(lines, width) if text.strip()]
                    entries = [(y, text) for y, text in rows if "agent0" in text]
                    if popup_open(lines) or len(rows) != 12 or len(entries) != 6:
                        return False
                    if mode == "grouped":
                        return (all(text.index("agent0") == 10 for _, text in entries)
                                and sum("Local" in text for _, text in rows) == 1
                                and sum("machine02" in text for _, text in rows) == 1)
                    # Wait for remote reconciliation and the client redraw too;
                    # the old layout can briefly contain the same six agent names.
                    return all("tab0" not in text and "project" in text
                               and lines[y+1][:width-1].strip() in ("Local", "machine02")
                               for y, text in entries)
                lines = terminal.wait(rendered)
                if mode == "priority":
                    heading = next(y for y, line in enumerate(lines) if line[1:width].strip().startswith("agents"))
                    terminal.click(lines[heading].index("grouped") + 1, heading)
                    lines = terminal.wait(lambda lines: "priority" in lines[heading] and rendered(lines))
                settings = store.load()
                assert tomllib.loads(config.read_text())["ui"]["sidebar"]["agents"]["rows"] == settings.rows(token_names=store.token_names())
                rows = [(y, text) for y, text in sidebar_lines(lines, width) if text.strip()]
                assert len(rows) == 12, rows
                assert not any(text.strip() == "·" for _, text in rows)
                for y, text in rows:
                    if "project" in text:
                        assert terminal.screen.buffer[y][text.index("project")].fg == DEFAULT_COLORS[1][1:]
                    if "agent0" in text:
                        assert terminal.screen.buffer[y][text.index("agent0")].fg == DEFAULT_COLORS[2][1:]
                        if mode == "priority":
                            assert "project" in text and "tab0" not in text
                            assert text.index("project") < text.index("agent0")
                            assert "Local" not in text and "machine02" not in text
                    if mode == "priority" and ("Local" in text or "machine02" in text):
                        machine_name = "Local" if "Local" in text else "machine02"
                        assert terminal.screen.buffer[y][text.index(machine_name)].fg == DARK_BLUE[1:]
                    if mode == "grouped" and ("Local" in text or "machine02" in text):
                        assert terminal.screen.buffer[y][1].fg == DEFAULT_COLORS[0][1:]
                stem = output / f"default-{mode}"
                capture_svg(terminal.screen, rows, stem.with_suffix(".svg"), width,
                            title=f"Agents Sidebar: default {mode.title()} layout, captured in Herdr")
                stem.with_suffix(".json").write_text(json.dumps({
                    "herdr": version, "mode": mode, "native_order": mode, "width": width,
                    "preferences": asdict(settings.profile()),
                    "transport": "local SSH shim, real Herdr servers and bridges",
                    "capture": "factory profile activated through the real Settings popup",
                    "rows": [text.replace("\u2800", " ").rstrip() for _, text in rows],
                }, ensure_ascii=False, indent=2) + "\n")
                print(f"PASS: captured default {mode.title()} layout at {stem.with_suffix('.svg')}", flush=True)
        finally:
            h.command("local", "plugin", "disable", PLUGIN_ID, check=False)
            wait(lambda: worker_stopped(store.state), timeout=25)
            terminal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/evidence")
    capture(parser.parse_args().output_dir)
