#!/usr/bin/env python3
"""Exercise the real GitHub installer with an isolated local Git URL rewrite."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import PLUGIN_ID, Settings, Store
from herdr_harness import HerdrHarness
from check_herdr import ROOT, activate_by_navigation, popup_open, tokens, wait, worker_stopped


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout


def main():
    with HerdrHarness() as h:
        source, remote = h.root / "source", h.root / "remote.git"
        source.mkdir()
        for name in ("sidebar.py", "configuration.py", "runtime.py", "layout.py", "herdr-plugin.toml"):
            shutil.copy2(ROOT / name, source / name)
        git(source, "init", "-b", "main")
        git(source, "config", "user.name", "Plugin integration test")
        git(source, "config", "user.email", "test@example.invalid")
        git(source, "add", ".")
        git(source, "commit", "-m", "feat(sidebar): add isolated fixture")
        subprocess.run(["git", "clone", "--bare", str(source), str(remote)], check=True, capture_output=True)
        global_config = h.root / "gitconfig"
        global_config.write_text(f'[url "{remote.as_uri()}"]\n'
                                 '    insteadOf = https://github.com/c0r0nell/herdr-agents-sidebar.git\n')
        with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_NOSYSTEM": "1",
                                     "GIT_TERMINAL_PROMPT": "0"}):
            h.start("local", rows="")
            local = h.populate("local")
            original = h.config_path("local").read_text()
            store = Store(h.root / "local/config/herdr/plugins/config" / PLUGIN_ID,
                          h.root / "local/state/herdr/plugins" / PLUGIN_ID)
            # Fresh normal install is enabled in Herdr but needs a Settings choice.
            h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
            info = next(p for p in h.api("local", "plugin.list")["plugins"] if p["plugin_id"] == PLUGIN_ID)
            assert info["enabled"] and store.load() == Settings() and not store.load().enabled
            assert h.config_path("local").read_text() == original
            activate_by_navigation(h)
            wait(lambda: any(log.get("event") == "workspace.focused" and log["status"] == "succeeded"
                            for log in h.api("local", "plugin.log.list", {"plugin_id": PLUGIN_ID, "limit": 20})["logs"]))
            assert worker_stopped(store.state) and not (store.state / "presentation.json").exists()
            terminal = h.terminal()
            try:
                h.api("local", "plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "settings", "focus": True})
                terminal.wait(lambda lines: popup_open(lines) and any("Active" in line and "[No]" in line for line in lines))
                os.write(terminal.master, b"\r")
                wait(lambda: store.load().enabled and len(tokens(h, "local")) == 3
                     and all(t.get("has_agent") for t in tokens(h, "local")))
                os.write(terminal.master, b"\x1b")
                terminal.wait(lambda lines: not popup_open(lines))
                h.command("local", "plugin", "action", "invoke", "restore", "--plugin", PLUGIN_ID)
                wait(lambda: store.load() == Settings() and worker_stopped(store.state)
                     and h.config_path("local").read_text() == original)
            finally:
                terminal.close()
            h.command("local", "plugin", "uninstall", PLUGIN_ID)
            preferences = Settings().with_profile("grouped", machine_color="#123456", show_separator=False).with_active("grouped")
            preferences = preferences.with_profile("grouped", view="agent/tab", tab_color="#50fa7b")
            preferences = preferences.with_profile("priority", line1=("machine", "project"),
                                                   line2=("agent", "tab", "status"), tab_color="#ff79c6")
            store.save(preferences)
            h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
            info = next(p for p in h.api("local", "plugin.list")["plugins"] if p["plugin_id"] == PLUGIN_ID)
            checkout = Path(info["plugin_root"])
            assert checkout != source and checkout.is_relative_to(h.root)
            assert not (checkout / "settings.toml").exists()
            assert store.load() == preferences
            assert "apply" not in {action["id"] for action in info["actions"]}
            # Herdr 0.9.3 has no post-install hook. Returning to a native workspace
            # activates the installed plugin without a Plugin Manager action.
            activate_by_navigation(h)
            try:
                wait(lambda: all(t.get("has_agent") for t in tokens(h, "local")))
                # Update the actual upstream commit without using the user's Git.
                path = source / "herdr-plugin.toml"
                manifest = path.read_text()
                version = tomllib.loads(manifest)["version"]
                major, minor, patch_number = map(int, version.split("."))
                updated_version = f"{major}.{minor}.{patch_number + 1}"
                path.write_text(manifest.replace(f'version = "{version}"', f'version = "{updated_version}"'))
                git(source, "add", ".")
                git(source, "commit", "-m", "fix(sidebar): update fixture version")
                git(source, "push", str(remote), "main")
                h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
                info = next(p for p in h.api("local", "plugin.list")["plugins"] if p["plugin_id"] == PLUGIN_ID)
                assert info["version"] == updated_version
                assert store.load() == preferences
                assert (store.state / "presentation.json").exists()
                assert not any((checkout / name).exists() for name in ("settings.toml", "presentation.json"))
                h.command("local", "plugin", "uninstall", PLUGIN_ID)
                wait(lambda: worker_stopped(store.state))
                wait(lambda: not any(t.get("has_agent") for t in tokens(h, "local")))
                assert h.config_path("local").read_text() == original
                assert not checkout.exists(), "Uninstall retained the managed source checkout"
                assert store.load() == preferences, "Uninstall removed durable preferences"
                # The same official identity consumes the same preferences locally.
                h.command("local", "plugin", "link", str(source / "herdr-plugin.toml"), "--enabled")
                activate_by_navigation(h)
                wait(lambda: all(t.get("has_agent") for t in tokens(h, "local")))
                assert store.load() == preferences
                h.command("local", "plugin", "unlink", PLUGIN_ID)
                wait(lambda: worker_stopped(store.state))
                assert h.config_path("local").read_text() == original
                assert source.exists(), "Unlink deleted editable source"
                # Offline installation is supported too: the normal startup
                # hook must apply the sidebar before any new navigation/agents.
                h.processes[0].terminate()
                h.processes[0].wait(timeout=5)
                h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
                assert not (store.state / "presentation.json").exists()
                h.start("local", rows="")
                wait(lambda: (store.state / "presentation.json").exists() and not worker_stopped(store.state))
                assert tomllib.loads(h.config_path("local").read_text())["ui"]["sidebar"]["agents"]["rows"] == preferences.rows()
                assert store.load() == preferences
                logs = h.api("local", "plugin.log.list", {"plugin_id": PLUGIN_ID, "limit": 20})["logs"]
                assert any(log.get("event") == "startup" for log in logs), "Navigation masked a missing startup hook"
                h.command("local", "plugin", "uninstall", PLUGIN_ID)
                wait(lambda: worker_stopped(store.state))
                assert h.config_path("local").read_text() == original
                assert store.load() == preferences
                # Both No remains native across source removal, reinstall and startup.
                paused = preferences.with_active(None)
                store.save(paused)
                h.processes[-1].terminate()
                h.processes[-1].wait(timeout=5)
                h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
                h.start("local", rows="")
                wait(lambda: any(log.get("event") == "startup" and log["status"] == "succeeded"
                                for log in h.api("local", "plugin.log.list", {"plugin_id": PLUGIN_ID, "limit": 20})["logs"]))
                assert store.load() == paused
                assert worker_stopped(store.state) and h.config_path("local").read_text() == original
                assert not (store.state / "presentation.json").exists()
                activate_by_navigation(h)
                assert worker_stopped(store.state) and h.config_path("local").read_text() == original
                h.command("local", "plugin", "uninstall", PLUGIN_ID)
                assert store.load() == paused, "Reinstall/uninstall lost the inactive profiles"
            finally:
                h.command("local", "plugin", "disable", PLUGIN_ID, check=False)
                wait(lambda: worker_stopped(store.state), timeout=25)
    print("PASS: fresh install enabled/both No, Settings activation, factory reset, durable upgrades and offline startup")


if __name__ == "__main__":
    main()
