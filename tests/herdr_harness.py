"""Real Herdr servers and terminal capture confined to a temporary directory.

The SSH shim carries the real Herdr bridges between two real servers on this
host. It replaces authentication/transport only; snapshots, rendering and input
routing still run through the installed Herdr binary. No network port is opened.
"""

from __future__ import annotations

import codecs
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import termios
import time

SESSION = "sidebar-proof"
PROFILE_ID = "0123456789abcdef0123456789abcdef"

BASE_CONFIG = '''onboarding = false
[terminal]
default_shell = "/bin/sh"
shell_mode = "non_login"
[update]
version_check = false
manifest_check = false
[session]
resume_agents_on_restore = false
[remote]
manage_ssh_config = false
[experimental]
allow_nested = true
[ui]
sidebar_width = WIDTH
sidebar_min_width = WIDTH
sidebar_max_width = WIDTH
agent_panel_sort = "spaces"
status_indicators = "symbols"
'''

PROOF_ROWS = '''[ui.sidebar.agents]
row_gap = 0
rows = [
  [{token = "$has_machine", fg = "#f1fa8c", bold = true}],
  [{token = "$has_project", fg = "#89b4fa", bold = true}],
  [{token = "$has_agent_prefix", fg = "#bd93f9", bold = false}, "state_icon",
   {token = "$has_agent", fg = "#bd93f9", bold = false}],
  [{token = "$has_gap", fg = "#f1fa8c", bold = true}],
]
'''


class HerdrHarness:
    def __init__(self):
        self.binary = shutil.which("herdr")
        if not self.binary:
            raise RuntimeError("Install Herdr before running integration checks")
        self.temp = tempfile.TemporaryDirectory(prefix="has-test-")
        self.root = Path(self.temp.name)
        self.processes = []
        self.logs = []

    def environment(self, machine):
        base = self.root / machine
        env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
        env.update(
            XDG_CONFIG_HOME=str(base / "config"),
            XDG_STATE_HOME=str(base / "state"),
            XDG_RUNTIME_DIR=str(base / "runtime"),
            HERDR_CONFIG_PATH=str(base / "config/herdr/config.toml"),
            TERM="xterm-256color",
        )
        if (self.root / "bin/ssh").exists():
            env["PATH"] = str(self.root / "bin") + os.pathsep + env["PATH"]
        # The non-login /bin/sh panes must not load the user's startup files.
        env.pop("ENV", None)
        env.pop("BASH_ENV", None)
        for path in (base / "config/herdr", base / "state", base / "runtime"):
            path.mkdir(parents=True, exist_ok=True)
        return env

    def config_path(self, machine):
        return self.root / machine / "config/herdr/config.toml"

    def socket_path(self, machine):
        return self.root / machine / "config/herdr/sessions" / SESSION / "herdr.sock"

    def api(self, machine, method, params=None):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(5)
            connection.connect(str(self.socket_path(machine)))
            request = {"id": "test", "method": method, "params": params or {}}
            connection.sendall((json.dumps(request) + "\n").encode())
            with connection.makefile("rb") as reader:
                response = json.loads(reader.readline(2**20))
        if "error" in response:
            raise RuntimeError(f"{method}: {response['error']}")
        return response["result"]

    def command(self, machine, *args, check=True):
        env = self.environment(machine)
        if (self.root / "bin/ssh").exists():
            env["PATH"] = str(self.root / "bin") + os.pathsep + env["PATH"]
        return subprocess.run(
            [self.binary, "--session", SESSION, *args], env=env, cwd=self.root,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=20, check=check,
        )

    def start(self, machine, width=36, rows=PROOF_ROWS):
        env = self.environment(machine)
        self.config_path(machine).write_text(BASE_CONFIG.replace("WIDTH", str(width)) + rows)
        self.command(machine, "config", "check")
        log = open(self.root / machine / "server.log", "wb")
        self.logs.append(log)
        process = subprocess.Popen(
            [self.binary, "--session", SESSION, "server"], env=env, cwd=self.root,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        )
        self.processes.append(process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError((self.root / machine / "server.log").read_text())
            try:
                self.api(machine, "ping")
                return
            except (OSError, ValueError):
                time.sleep(.05)
        raise RuntimeError("Isolated server did not become ready")

    def populate(self, machine):
        agents = []
        for project, names in (("projeto01", ("agente01", "agente02")),
                               ("projeto02", ("agente03",))):
            created = self.api(machine, "workspace.create", {"label": project, "cwd": str(self.root)})
            pane = created["root_pane"]["pane_id"]
            for index, name in enumerate(names):
                if index:
                    pane = self.api(machine, "pane.split", {
                        "pane_id": pane, "direction": "right", "cwd": str(self.root), "focus": False,
                    })["pane"]["pane_id"]
                # Controlled lifecycle fixtures, never a real coding-agent process.
                self.api(machine, "pane.report_agent", {
                    "pane_id": pane, "source": "test:fixture", "agent": "codex", "state": "idle",
                })
                self.api(machine, "agent.rename", {"target": pane, "name": name})
                agents.append((pane, name))
        return agents

    def publish(self, machine, agents):
        for pane, tokens in agents:
            self.api(machine, "pane.report_metadata", {
                "pane_id": pane, "source": "plugin:c0r0nell.agents-sidebar",
                "tokens": tokens, "ttl_ms": 60000,
            })

    def connect_remote(self):
        bindir = self.root / "bin"
        bindir.mkdir(exist_ok=True)
        remote_env = self.environment("remote")
        overrides = {k: remote_env[k] for k in (
            "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "HERDR_CONFIG_PATH",
        )}
        ssh = bindir / "ssh"
        ssh.write_text(
            "#!/usr/bin/python3\nimport os, sys\n"
            "if 'sidebar-test-remote' not in sys.argv: raise SystemExit('only test remote allowed')\n"
            "env = {k:v for k,v in os.environ.items() if not k.startswith('HERDR_')}\n"
            f"env.update({overrides!r})\n"
            "os.execve('/bin/sh', ['sh', '-c', sys.argv[-1]], env)\n"
        )
        ssh.chmod(0o700)
        catalog = self.root / "local/state/herdr/client/endpoints.json"
        catalog.parent.mkdir(parents=True, exist_ok=True)
        catalog.write_text(json.dumps({"version": 1, "ssh": [{
            "id": PROFILE_ID, "label": "machine02", "target": "sidebar-test-remote",
            "session": SESSION, "enabled": True,
        }]}))

    def terminal(self, machine="local", width=120, height=60, attach=None):
        return TerminalCapture(self, machine, width, height, attach)

    def close(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for log in self.logs:
            log.close()
        self.temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TerminalCapture:
    def __init__(self, harness, machine, width, height, attach=None):
        try:
            import pyte
        except ImportError as error:
            raise RuntimeError("Install test dependencies: pip install -r tests/requirements.txt") from error

        class Screen(pyte.Screen):
            # pyte 0.8.2 does not accept private DSR queries (CSI ? ... n).
            def report_device_status(self, mode, **kwargs):
                if not kwargs:
                    super().report_device_status(mode)

        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
        self.screen = Screen(width, height)
        self.stream = pyte.Stream(self.screen)
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        env = harness.environment(machine)
        env["PATH"] = str(harness.root / "bin") + os.pathsep + env["PATH"]
        args = [harness.binary, "--session", SESSION]
        if attach:
            # A second client with its own catalog/config, sharing this test server.
            env["HERDR_SOCKET_PATH"] = str(harness.socket_path(attach))
            env["HERDR_CLIENT_SOCKET_PATH"] = str(harness.socket_path(attach).with_name("herdr-client.sock"))
            env["HERDR_SESSION"] = SESSION
            args = [harness.binary]
        self.process = subprocess.Popen(
            args, env=env, cwd=harness.root,
            stdin=slave, stdout=slave, stderr=slave, start_new_session=True,
        )
        harness.processes.append(self.process)
        os.close(slave)

    def read(self, seconds=.15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], max(0, deadline-time.monotonic()))[0]:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.stream.feed(self.decoder.decode(chunk))
        return self.screen.display

    def wait(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            lines = self.read()
            if predicate(lines):
                return lines
            if self.process.poll() is not None:
                raise RuntimeError("Herdr TUI exited during capture")
        raise AssertionError("Terminal condition timed out\n" + "\n".join(self.screen.display))

    def click(self, x, y):
        # SGR mouse coordinates are one based; all targets belong to test panes.
        os.write(self.master, f"\x1b[<0;{x+1};{y+1}M\x1b[<0;{x+1};{y+1}m".encode())

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # A restarted bridge can delay native TUI shutdown. This group
                # was created by this capture; it contains no user's process.
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        os.close(self.master)
