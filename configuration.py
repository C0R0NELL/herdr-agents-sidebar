"""Durable preferences and reversible ownership of three Herdr config fields."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
import tomllib

PLUGIN_ID = "c0r0nell.agents-sidebar"
SOURCE = "plugin:" + PLUGIN_ID
DEFAULT_ROWS = [["state_icon", "machine", "workspace", "tab"], ["agent"]]
FIELDS = ("ui.agent_panel_sort", "ui.sidebar.agents.row_gap", "ui.sidebar.agents.rows")
# Colors offered in Settings; defaults follow the user's selected group palette.
DRACULA_COLORS = {
    "Purple": "#bd93f9", "Pink": "#ff79c6", "White": "#f8f8f2",
    "Cyan": "#8be9fd", "Green": "#50fa7b", "Yellow": "#f1fa8c",
    "Red": "#ff5555", "Orange": "#ffb86c",
}
DEFAULT_COLORS = (DRACULA_COLORS["Yellow"], "#89b4fa", DRACULA_COLORS["Purple"])


class Conflict(RuntimeError):
    """An existing layout or a later user edit must not be overwritten."""


def color(value):
    if value == "default":
        return value
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value):
        raise ValueError("Choose Default or a hexadecimal color (#RGB or #RRGGBB)")
    value = value.lower()
    return "#" + "".join(c * 2 for c in value[1:]) if len(value) == 4 else value


@dataclass(frozen=True)
class Settings:
    machine_color: str = "default"
    project_color: str = "default"
    agent_color: str = "default"
    show_separator: bool = True

    def normalized(self):
        if type(self.show_separator) is not bool:
            raise ValueError("Show separator must be On or Off")
        return Settings(*(color(v) for v in (self.machine_color, self.project_color, self.agent_color)),
                        show_separator=self.show_separator)

    def rows(self):
        colors = [fallback if value == "default" else value for value, fallback in
                  zip((self.machine_color, self.project_color, self.agent_color), DEFAULT_COLORS)]
        def token(name, index, bold):
            return {"token": "$" + name, "fg": colors[index], "bold": bold}
        return [[token("has_machine", 0, True)], [token("has_project", 1, True)],
                [token("has_agent_prefix", 2, False), "state_icon", token("has_agent", 2, False)],
                [token("has_gap", 0, True)]]


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def atomic_write(path, text, *, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".sidebar-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def lock(path, timeout=3):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "a", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Conflict("Another sidebar operation is running; try again") from None
                time.sleep(.05)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class Store:
    def __init__(self, config=None, state=None):
        matching = os.environ.get("HERDR_PLUGIN_ID") == PLUGIN_ID
        config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        self.config = Path(config or (os.environ.get("HERDR_PLUGIN_CONFIG_DIR") if matching else None)
                           or config_root / "herdr/plugins/config" / PLUGIN_ID)
        self.state = Path(state or (os.environ.get("HERDR_PLUGIN_STATE_DIR") if matching else None)
                          or state_root / "herdr/plugins" / PLUGIN_ID)
        if not self.config.is_absolute() or not self.state.is_absolute():
            raise ValueError("Plugin storage paths must be absolute")
        self.preferences = self.config / "settings.toml"

    def load(self):
        if not self.preferences.exists():
            return Settings()
        data = tomllib.loads(self.preferences.read_text())
        if data.pop("schema", None) != 1:
            raise Conflict("Unsupported settings schema; preferences were preserved")
        try:
            return Settings(**data).normalized()
        except TypeError as error:
            raise Conflict("Unknown settings fields; preferences were preserved") from error

    def save(self, settings):
        settings = settings.normalized()
        private_directory(self.config)
        with lock(self.config / "settings.lock"):
            self.load()  # Refuse to replace a newer schema.
            text = "schema = 1\n" + "".join(f"{k} = {toml(v)}\n" for k, v in asdict(settings).items())
            atomic_write(self.preferences, text)


def toml(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(k + " = " + toml(v) for k, v in value.items()) + "}"
    raise TypeError("Unsupported configuration value")


def statements(text):
    """Find complete TOML statements, ignoring fake headers inside strings."""
    start, index, depth, quote = 0, 0, 0, None
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote[0] == '"':
                index += 2
                continue
            if text.startswith(quote, index):
                index += len(quote)
                quote = None
                continue
        elif char == "#":
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        elif char in "\"'":
            quote = char * 3 if text.startswith(char * 3, index) else char
            index += len(quote)
            continue
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "\n" and not quote and depth == 0:
            yield start, index + 1, text[start:index + 1]
            start = index + 1
        index += 1
    if start < len(text):
        yield start, len(text), text[start:]


def leaf_path(mapping, target=None):
    path = []
    while isinstance(mapping, dict) and len(mapping) == 1:
        name, mapping = next(iter(mapping.items()))
        path.append(name)
    if target:
        # Section parser includes the __probe__ leaf.
        path.pop()
    return tuple(path)


def spans(text):
    fields, tables, context = {}, {}, ()
    for start, end, raw in statements(text):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if line.startswith("[["):
                context = ("__array_table__",)
                continue
            context = leaf_path(tomllib.loads(line + "\n__probe__ = 0"), True)
            tables[context] = end
            continue
        # Parse the key using TOML itself, including quoted/dotted keys.
        quote = None
        for index, char in enumerate(raw):
            if quote:
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == "=":
                path = context + leaf_path(tomllib.loads(raw[:index] + "= 0"))
                fields[path] = (start, end, raw, raw[:index].strip())
                break
    return fields, tables


def rewrite(text, path, value=None, *, raw=None, remove=False):
    fields, tables = spans(text)
    path = tuple(path.split("."))
    if path in fields:
        start, end, previous, key = fields[path]
        replacement = "" if remove else raw if raw is not None else f"{key} = {toml(value)}\n"
        return text[:start] + replacement + text[end:]
    if remove:
        return text
    parent = path[:-1]
    replacement = raw if raw is not None else f"{path[-1]} = {toml(value)}\n"
    if parent in tables:
        index = tables[parent]
        return text[:index] + replacement + text[index:]
    prefix = "\n" if text and not text.endswith("\n") else ""
    return text + prefix + "\n[" + ".".join(parent) + "]\n" + replacement


class Presentation:
    def __init__(self, config, state):
        self.config = Path(config).resolve()
        self.state = Path(state)
        self.receipt = self.state / "presentation.json"

    def _read(self):
        return self.config.read_text() if self.config.exists() else ""

    def _journal(self):
        if not self.receipt.exists():
            return None
        receipt = json.loads(self.receipt.read_text())
        if receipt.get("schema") != 1 or receipt.get("config") != str(self.config):
            raise Conflict("Configuration ownership belongs to a different path or schema")
        current = self._read()
        if receipt["phase"] == "prepared":
            if current == receipt.get("before", receipt["original"]):
                previous = receipt.get("previous")
                if previous:
                    atomic_write(self.receipt, json.dumps(previous))
                else:
                    self.receipt.unlink()
                return previous
            if current != receipt["installed"]:
                raise Conflict("Interrupted config change requires review; nothing was overwritten")
        return receipt

    def _publish(self, text, validate, *, expected=None):
        tomllib.loads(text)
        if validate:
            self.config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor, temporary = tempfile.mkstemp(prefix=".sidebar-check-", suffix=".toml", dir=self.config.parent)
            try:
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(text)
                validate(Path(temporary))
            finally:
                os.unlink(temporary)
        if expected is not None and self._read() != expected:
            raise Conflict("Configuration changed during validation; the user's edit was preserved")
        mode = self.config.stat().st_mode & 0o777 if self.config.exists() else 0o600
        atomic_write(self.config, text, mode=mode)

    def apply(self, settings, validate=None, *, replace_native_layout=False):
        settings = settings.normalized()
        private_directory(self.state)
        with lock(self.state / "presentation.lock"):
            receipt = self._journal()
            original = self._read()
            parsed = tomllib.loads(original)
            agents = parsed.get("ui", {}).get("sidebar", {}).get("agents", {})
            original_spans, _ = spans(original)
            if receipt:
                for name in FIELDS:
                    current = original_spans.get(tuple(name.split(".")))
                    if not current or current[2] != receipt["fields"][name]["installed"]:
                        raise Conflict(f"{name} was edited after activation; restore/review before applying")
            else:
                rows = agents.get("rows", DEFAULT_ROWS)
                native_tokens = {"state_icon", "machine", "workspace", "tab", "agent"}
                native_only = isinstance(rows, list) and bool(rows) and all(
                    isinstance(row, list) and bool(row) and all(
                        isinstance(token, str) and token in native_tokens for token in row
                    ) for row in rows
                )
                if agents.get("rows_by_agent") or (rows != DEFAULT_ROWS and not
                                                    (replace_native_layout and native_only)):
                    raise Conflict("A custom agent layout already exists; no configuration was changed")
            text = original
            values = ("spaces", 0, settings.rows())
            for name, value in zip(FIELDS, values):
                text = rewrite(text, name, value)
            try:
                tomllib.loads(text)
            except tomllib.TOMLDecodeError as error:
                raise Conflict("This TOML structure cannot be safely edited; nothing was changed") from error
            if text == original:
                return False
            # Validation happens before either the config or ownership receipt changes.
            if validate:
                descriptor, temporary = tempfile.mkstemp(suffix=".toml")
                try:
                    with os.fdopen(descriptor, "w") as stream:
                        stream.write(text)
                    validate(Path(temporary))
                finally:
                    os.unlink(temporary)
            installed_spans, _ = spans(text)
            if self._read() != original:
                raise Conflict("Configuration changed during validation; the user's edit was preserved")
            fields = {}
            for name in FIELDS:
                path = tuple(name.split("."))
                previous = original_spans.get(path)
                fields[name] = {"original": receipt["fields"][name]["original"] if receipt else
                                previous[2] if previous else None,
                                "installed": installed_spans[path][2]}
            journal = {"schema": 1, "config": str(self.config), "phase": "prepared",
                       "original": receipt["original"] if receipt else original,
                       "before": original, "previous": receipt,
                       "installed": text, "fields": fields}
            atomic_write(self.receipt, json.dumps(journal))
            try:
                self._publish(text, None, expected=original)
            except Conflict:
                if receipt:
                    atomic_write(self.receipt, json.dumps(receipt))
                else:
                    self.receipt.unlink()
                raise
            journal["phase"] = "applied"
            journal.pop("previous")
            journal.pop("before")
            atomic_write(self.receipt, json.dumps(journal))
            return True

    def restore(self, validate=None):
        private_directory(self.state)
        with lock(self.state / "presentation.lock"):
            receipt = self._journal()
            if not receipt:
                return False
            current = self._read()
            if current == receipt["installed"]:
                text = receipt["original"]
            else:
                text = current
                for name, field in receipt["fields"].items():
                    actual = spans(text)[0].get(tuple(name.split(".")))
                    if actual and actual[2] == field["installed"]:
                        text = rewrite(text, name, raw=field["original"], remove=field["original"] is None)
            if text != current:
                self._publish(text, validate, expected=current)
            self.receipt.unlink()
            return text != current
