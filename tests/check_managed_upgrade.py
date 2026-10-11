#!/usr/bin/env python3
"""Exercise the real GitHub installer with an isolated local Git URL rewrite."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import PLUGIN_ID, Settings, Store
from herdr_harness import HerdrHarness
from check_herdr import ROOT, tokens, wait, worker_stopped


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
            h.populate("local")
            original = h.config_path("local").read_text()
            store = Store(h.root / "local/config/herdr/plugins/config" / PLUGIN_ID,
                          h.root / "local/state/herdr/plugins" / PLUGIN_ID)
            preferences = Settings(machine_color="#123456", show_separator=False)
            store.save(preferences)
            h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
            info = next(p for p in h.api("local", "plugin.list")["plugins"] if p["plugin_id"] == PLUGIN_ID)
            checkout = Path(info["plugin_root"])
            assert checkout != source and checkout.is_relative_to(h.root)
            assert not (checkout / "settings.toml").exists()
            assert store.load() == preferences
            h.command("local", "plugin", "action", "invoke", "apply", "--plugin", PLUGIN_ID)
            try:
                wait(lambda: all(t.get("has_agent") for t in tokens(h, "local")))
                # Update the actual upstream commit without using the user's Git.
                path = source / "herdr-plugin.toml"
                path.write_text(path.read_text().replace('version = "0.1.0"', 'version = "0.1.1"'))
                git(source, "add", ".")
                git(source, "commit", "-m", "fix(sidebar): update fixture version")
                git(source, "push", str(remote), "main")
                h.command("local", "plugin", "install", "c0r0nell/herdr-agents-sidebar", "--yes")
                info = next(p for p in h.api("local", "plugin.list")["plugins"] if p["plugin_id"] == PLUGIN_ID)
                assert info["version"] == "0.1.1"
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
                h.command("local", "plugin", "action", "invoke", "apply", "--plugin", PLUGIN_ID)
                wait(lambda: all(t.get("has_agent") for t in tokens(h, "local")))
                assert store.load() == preferences
                h.command("local", "plugin", "unlink", PLUGIN_ID)
                wait(lambda: worker_stopped(store.state))
                assert h.config_path("local").read_text() == original
                assert source.exists(), "Unlink deleted editable source"
            finally:
                h.command("local", "plugin", "disable", PLUGIN_ID, check=False)
                wait(lambda: worker_stopped(store.state), timeout=25)
    print("PASS: real managed install/update/uninstall and local link/unlink preserve external preferences")


if __name__ == "__main__":
    main()
