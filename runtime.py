"""Public Herdr transports and bounded reconciliation for the native sidebar."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

from configuration import Conflict, PLUGIN_ID, SOURCE, Presentation, Settings, Store, atomic_write, lock
from layout import MAX_MACHINES, Machine, layout, patches

TTL_MS = 60000
RENEW_SECONDS = 20
REMOTE_SECONDS = 5
LIMIT_BYTES = 2**20
EVENTS = ("workspace.created", "workspace.updated", "workspace.renamed", "workspace.moved",
          "workspace.reordered", "workspace.closed", "tab.created", "tab.closed", "tab.moved",
          "pane.created", "pane.closed", "pane.moved", "pane.exited", "pane.updated",
          "pane.agent_detected")
# Status indicators belong to Herdr and need no metadata rewrite. Its
# pane.agent_status_changed subscription requires a specific pane_id.


class Herdr:
    def __init__(self):
        if os.environ.get("HERDR_ENV") != "1":
            raise RuntimeError("Run this plugin inside Herdr")
        matching = os.environ.get("HERDR_PLUGIN_ID") == PLUGIN_ID
        self.binary = (os.environ.get("HERDR_BIN_PATH") if matching else None) or shutil.which("herdr")
        if not self.binary:
            raise RuntimeError("Herdr is not available in PATH")
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "herdr"
        self.config = Path(os.environ.get("HERDR_CONFIG_PATH", root / "config.toml"))
        self.session = os.environ.get("HERDR_SESSION", "default")
        session_root = root if self.session == "default" else root / "sessions" / self.session
        self.socket = Path(os.environ.get("HERDR_SOCKET_PATH", session_root / "herdr.sock"))
        self.local_id = "local:" + hashlib.sha256(str(self.socket.resolve()).encode()).hexdigest()[:16]

    def api(self, method, params=None):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(3)
            connection.connect(str(self.socket))
            request = {"id": "agents-sidebar", "method": method, "params": params or {}}
            connection.sendall((json.dumps(request) + "\n").encode())
            with connection.makefile("rb") as stream:
                raw = stream.readline(LIMIT_BYTES + 1)
        if len(raw) > LIMIT_BYTES:
            raise RuntimeError("Herdr response exceeded the bounded snapshot limit")
        response = json.loads(raw)
        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"{method}: {error.get('code', 'request failed')}")
        return response["result"]

    def command(self, *args, env=None):
        # A process group bounds bridge descendants too. Temporary streams bound
        # memory usage; reject oversized output before decoding it.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([self.binary, *args], env=env or os.environ,
                                       stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                       start_new_session=True)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise RuntimeError("Herdr command timed out; state will be reread before retrying") from None
            size = output.tell()
            if size > LIMIT_BYTES:
                raise RuntimeError("Herdr command response exceeded the snapshot limit")
            if process.returncode:
                # Do not persist SSH targets, environment or snapshots in errors.
                raise RuntimeError("Herdr command failed; inspect Herdr's own diagnostics")
            output.seek(0)
            return output.read().decode("utf-8")

    def validate(self, path):
        env = dict(os.environ, HERDR_CONFIG_PATH=str(path))
        self.command("config", "check", env=env)

    def reload(self):
        report = self.api("server.reload_config")
        if report.get("status") not in {"applied", "ok"}:
            raise RuntimeError("Herdr could not fully reload the configuration")

    def enabled(self):
        plugins = self.api("plugin.list")["plugins"]
        return any(p["plugin_id"] == PLUGIN_ID and p["enabled"] for p in plugins)

    def check_projection(self):
        # Source-restricted clear is a public, non-destructive probe for a foreign
        # active projection. This plugin never sets or replaces a projection.
        result = self.api("agent.view.clear", {"source": SOURCE})
        view = result.get("view", result)
        if view.get("active") and view.get("source") != SOURCE:
            raise Conflict("Another agent projection is active; no layout was replaced")

    def machine_profiles(self):
        profiles = json.loads(self.command("machine", "list", "--json"))
        if len(profiles) >= MAX_MACHINES:
            raise Conflict("Machine limit exceeded; refusing a partial tree")
        return [p for p in profiles if p["enabled"]]

    def snapshot(self, profile=None):
        if profile is None:
            data = self.api("session.snapshot")["snapshot"]
            return Machine(self.local_id, self.session, "Local", data)
        response = json.loads(self.command("--machine", profile["id"], "api", "snapshot"))
        return Machine(profile["id"], profile["session"], profile["label"], response["result"]["snapshot"])

    def publish(self, patch):
        if patch.key.machine == self.local_id:
            return self.api("pane.report_metadata", {"pane_id": patch.key.pane_id, "source": SOURCE,
                                                     "tokens": patch.tokens, "ttl_ms": TTL_MS})
        args = ["--machine", patch.key.machine, "pane", "report-metadata", patch.key.pane_id,
                "--source", SOURCE, "--ttl-ms", str(TTL_MS)]
        for name, value in patch.tokens.items():
            args += ["--clear-token", name] if value is None else ["--token", name + "=" + value]
        return self.command(*args)


class Events:
    """One bounded dirty flag rather than an unbounded queue of pane events."""
    def __init__(self, herdr):
        self.connection = socket.socket(socket.AF_UNIX)
        self.connection.settimeout(3)
        self.buffer = b""
        try:
            self.connection.connect(str(herdr.socket))
            request = {"id": "sidebar-events", "method": "events.subscribe",
                       "params": {"subscriptions": [{"type": name} for name in EVENTS]}}
            self.connection.sendall((json.dumps(request) + "\n").encode())
            # Confirm acceptance before allowing polling to appear successful.
            # Keep any following event bytes received with the acknowledgement.
            while b"\n" not in self.buffer:
                raw = self.connection.recv(65536)
                if not raw:
                    raise ConnectionError("Herdr event stream disconnected before subscription")
                self.buffer += raw
                if len(self.buffer) > LIMIT_BYTES:
                    raise RuntimeError("Herdr event exceeded the buffer limit")
            line, self.buffer = self.buffer.split(b"\n", 1)
            response = json.loads(line)
            if "error" in response:
                raise RuntimeError("events.subscribe: " + response["error"].get("code", "request failed"))
            if response.get("result", {}).get("type") != "subscription_started":
                raise RuntimeError("Herdr did not confirm the event subscription")
            self.connection.setblocking(False)
        except BaseException:
            self.connection.close()
            raise

    def dirty(self):
        changed = False
        while b"\n" in self.buffer or select.select([self.connection], [], [], 0)[0]:
            if b"\n" not in self.buffer:
                raw = self.connection.recv(65536)
                if not raw:
                    raise ConnectionError("Herdr event stream disconnected")
                self.buffer += raw
                if len(self.buffer) > LIMIT_BYTES:
                    raise RuntimeError("Herdr event exceeded the buffer limit")
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                event = json.loads(line)
                if "error" in event:
                    raise RuntimeError("Herdr event stream reported an error")
                changed = changed or "event" in event or "type" in event
        return changed

    def close(self):
        self.connection.close()


class Reconciler:
    """Keep native snapshots in memory and isolate slow remote endpoints."""
    def __init__(self, herdr):
        self.herdr = herdr
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.profiles = []
        self.cache = {}
        self.pending = {}
        self.next_remote = 0
        self.next_profiles = 0
        self.next_renew = 0
        self.remote_renew = {}

    def tick(self, settings, *, clear=False):
        now = time.monotonic()
        if now >= self.next_profiles:
            self.profiles = self.herdr.machine_profiles()
            self.next_profiles = now + 10
        for profile in self.profiles:
            identity = profile["id"]
            future = self.pending.get(identity)
            if future and future.done():
                try:
                    self.cache[identity] = future.result()
                except (OSError, RuntimeError, ValueError):
                    if identity in self.cache:
                        self.cache[identity] = replace(self.cache[identity], stale=True)
                del self.pending[identity]
        known = {p["id"] for p in self.profiles}
        self.cache = {key: value for key, value in self.cache.items() if key in known}
        local = self.herdr.snapshot()
        machines = [local] + [self.cache[p["id"]] for p in self.profiles if p["id"] in self.cache]
        desired = {} if clear else layout(machines, gap_between_machines=settings.show_separator,
                                         mode=settings.mode, fields=settings.visible_fields)
        renew = now >= self.next_renew
        removals, updates = patches(machines, desired, renew=renew)
        # Each endpoint clears old anchors before setting new ones. Remote work
        # runs separately: a stalled SSH bridge cannot delay local reconciliation.
        for phase in (removals, updates):
            for patch in phase:
                if patch.key.machine == local.id:
                    self.herdr.publish(patch)
        if now >= self.next_remote:
            for profile in self.profiles:
                if profile["id"] not in self.pending:
                    self.pending[profile["id"]] = self.pool.submit(self._remote, profile, machines, settings, clear)
            self.next_remote = now + REMOTE_SECONDS
        if renew:
            self.next_renew = now + RENEW_SECONDS

    def _remote(self, profile, machines, settings, clear):
        current = self.herdr.snapshot(profile)
        combined = [current if m.id == current.id else m for m in machines]
        if not any(m.id == current.id for m in combined):
            combined.append(current)
        desired = {} if clear else layout(combined, gap_between_machines=settings.show_separator,
                                         mode=settings.mode, fields=settings.visible_fields)
        # Fresh state before every attempt, including after ambiguous timeouts.
        now = time.monotonic()
        renew = not clear and now >= self.remote_renew.get(current.id, 0)
        phases = patches([current], desired, renew=renew)
        for phase in phases:
            for change in phase:
                self.herdr.publish(change)
        if renew:
            self.remote_renew[current.id] = now + RENEW_SECONDS
        return self.herdr.snapshot(profile) if any(phases) else current

    def clear(self, settings):
        # Finish already-running owned writes before clearing. Queued tasks are
        # cancelled and all reachable endpoints are reread for source-only cleanup.
        self.pool.shutdown(wait=True, cancel_futures=True)
        local = self.herdr.snapshot()
        for phase in patches([local], {}):
            for change in phase:
                self.herdr.publish(change)
        profiles = self.herdr.machine_profiles()
        with ThreadPoolExecutor(max_workers=4) as cleanup:
            futures = [cleanup.submit(self._remote, p, [], settings, True) for p in profiles]
            for future in futures:
                try:
                    future.result()
                except (OSError, RuntimeError, ValueError):
                    pass  # Unreachable endpoints lose these tokens at TTL expiry.

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)


def presentation(herdr, store):
    return Presentation(herdr.config, store.state)


def active(store):
    return store.load().enabled


def set_active(store, value):
    settings = store.load()
    store.save(settings.with_active(settings.mode if value else None))


def ensure(herdr, store):
    if not herdr.enabled() or not active(store):
        return
    path = store.state / (herdr.local_id.replace(":", "-") + ".lock")
    try:
        with lock(path, timeout=0):
            # Only one worker holds this lock. Concurrent launches are harmless:
            # each worker locks before it reads or changes the presentation.
            subprocess.Popen([sys.executable, "-B", str(Path(__file__).with_name("sidebar.py")), "worker"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except Conflict:
        return


def apply(herdr, store):
    with lock(store.state / "operation.lock"):
        if not herdr.enabled():
            raise Conflict("Enable the plugin before applying its sidebar")
        herdr.check_projection()
        settings = store.load()
        settings = settings.with_active(settings.mode)
        if presentation(herdr, store).apply(settings, validate=herdr.validate, replace_native_layout=True):
            herdr.reload()
        set_active(store, True)
        ensure(herdr, store)


def save_settings(herdr, store, settings):
    with lock(store.state / "operation.lock"):
        _save_settings(herdr, store, settings)


def _save_settings(herdr, store, settings):
    """Caller holds the operation lock, including when restarting a worker."""
    settings = settings.normalized()
    previous = store.load()
    if not herdr.enabled():
        store.save(settings)
        return
    if not settings.enabled:
        store.save(settings)  # Stop workers before clearing their tokens and rows.
        stop_and_restore(herdr, store, native_defaults=True)
        return
    herdr.check_projection()
    managed = presentation(herdr, store)
    changed = managed.apply(settings, validate=herdr.validate, replace_native_layout=not previous.enabled)
    try:
        store.save(settings)
    except (OSError, ValueError, Conflict):
        if changed:
            if previous.enabled:
                managed.apply(previous, validate=herdr.validate)
            else:
                managed.restore(validate=herdr.validate)
        raise
    if changed:
        herdr.reload()
    ensure(herdr, store)


def worker(herdr, store):
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    path = store.state / (herdr.local_id.replace(":", "-") + ".lock")
    try:
        with lock(path, timeout=0):
            engine, events = Reconciler(herdr), None
            status = store.state / (herdr.local_id.replace(":", "-") + ".json")
            restore = False
            failed = False
            try:
                if not herdr.enabled() or not active(store):
                    return
                herdr.check_projection()
                settings = store.load()
                if presentation(herdr, store).apply(settings, validate=herdr.validate, replace_native_layout=True):
                    herdr.reload()
                config_stamp = herdr.config.stat().st_mtime_ns
                next_tick, failures = 0, 0
                while not stopped:
                    try:
                        if not herdr.enabled() or not active(store):
                            restore = True
                            break
                        if events is None:
                            events = Events(herdr)  # Subscribe before the initial snapshot.
                        dirty = events.dirty()
                        current = store.load()
                        now = time.monotonic()
                        if dirty or current != settings or now >= next_tick:
                            herdr.check_projection()
                            stamp = herdr.config.stat().st_mtime_ns
                            if stamp != config_stamp:
                                if presentation(herdr, store).apply(current, validate=herdr.validate):
                                    herdr.reload()
                                config_stamp = herdr.config.stat().st_mtime_ns
                            settings = current
                            engine.tick(settings)
                            next_tick = now + 1
                        failures = 0
                        if status.exists():
                            status.unlink()
                    except Conflict as error:
                        restore, failed = True, True
                        atomic_write(status, json.dumps({"schema": 1, "error": str(error)[:200]}))
                        break
                    except (OSError, RuntimeError, ValueError) as error:
                        failures += 1
                        atomic_write(status, json.dumps({"schema": 1, "error": str(error)[:200]}))
                        if events:
                            events.close()
                            events = None
                        if failures >= 5:
                            restore, failed = True, True
                            break
                    time.sleep(.25 if failures == 0 else 1)
            except (OSError, RuntimeError, ValueError) as error:
                restore, failed = True, True
                atomic_write(status, json.dumps({"schema": 1, "error": str(error)[:200]}))
            finally:
                if events:
                    events.close()
                try:
                    engine.clear(store.load())
                except (OSError, RuntimeError, ValueError):
                    pass  # TTL bounds unreachable endpoints independently of config cleanup.
                if restore:
                    try:
                        others = False
                        if failed:
                            for candidate in store.state.glob("local-*.lock"):
                                if candidate == path:
                                    continue
                                try:
                                    with lock(candidate, timeout=0):
                                        pass
                                except Conflict:
                                    others = True
                        if not others and presentation(herdr, store).restore(validate=herdr.validate):
                            herdr.reload()
                    except (OSError, RuntimeError, ValueError):
                        pass  # Preserve the ownership receipt if restoration cannot be validated.
                engine.close()
                if not failed and status.exists():
                    status.unlink()
    except Conflict:
        return


def restore(herdr, store):
    """Restore factory preferences and native presentation; both modes stay No."""
    with lock(store.state / "operation.lock"):
        store.save(Settings())
        stop_and_restore(herdr, store, native_defaults=True)


def stop_and_restore(herdr, store, *, native_defaults=False):
    # Wait for the current worker's own cleanup, without killing any process.
    path = store.state / (herdr.local_id.replace(":", "-") + ".lock")
    with lock(path, timeout=15):
        engine = Reconciler(herdr)
        try:
            engine.clear(store.load())
        finally:
            engine.close()
        if presentation(herdr, store).restore(validate=herdr.validate, native_defaults=native_defaults):
            herdr.reload()


def restart(herdr, store):
    """Reload this worker while preserving preferences and the activation choice."""
    with lock(store.state / "operation.lock"):
        previous = store.load()
        set_active(store, False)
        # An active restart needs its original ownership baseline intact.
        stop_and_restore(herdr, store, native_defaults=not previous.enabled)
        if previous.enabled:
            _save_settings(herdr, store, previous)
