"""Durable preferences and reversible ownership of Herdr presentation fields."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
import tomllib
import uuid

from layout import DEFAULT_PRIORITY_LINES, GROUPED_VIEWS, MODES, SIDEBAR_FIELDS, TOKENS

PLUGIN_ID = "c0r0nell.agents-sidebar"
SOURCE = "plugin:" + PLUGIN_ID
DEFAULT_ROWS = [["state_icon", "machine", "workspace", "tab"], ["agent"]]
FIELDS = ("ui.sidebar.agents.row_gap", "ui.sidebar.agents.rows")
# Colors offered in Settings; defaults follow the user's selected group palette.
DRACULA_COLORS = {
    "Purple": "#bd93f9", "Pink": "#ff79c6", "White": "#f8f8f2",
    "Cyan": "#8be9fd", "Green": "#50fa7b", "Yellow": "#f1fa8c",
    "Red": "#ff5555", "Orange": "#ffb86c",
}
DARK_BLUE = "#6272a4"
DEFAULT_COLORS = (DRACULA_COLORS["Yellow"], "#89b4fa", DRACULA_COLORS["Purple"], DARK_BLUE)
# Factory snapshot approved on 2026-10-11: fixed Grouped tree, no separator;
# Priority shows Project/Machine above native Status/Agent, with Dark blue machines.
FACTORY_PRIORITY_LINES = (("project", "machine"), ("status", "agent"))
LEGACY_VIEWS = ("agent", "agent/project", "agent/project/machine", "agent/project/machine/tab")
PROFILE_FIELDS = {
    "grouped": {"machine_color", "project_color", "agent_color", "tab_color", "view", "show_separator"},
    "priority": {"machine_color", "project_color", "agent_color", "tab_color", "line1", "line2"},
}


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
class ModeSettings:
    machine_color: str = "default"
    project_color: str = "default"
    agent_color: str = "default"
    tab_color: str = "default"
    show_separator: bool = False
    view: str = "agent"
    line1: tuple = DEFAULT_PRIORITY_LINES[0]
    line2: tuple = DEFAULT_PRIORITY_LINES[1]

    def normalized(self):
        if type(self.show_separator) is not bool:
            raise ValueError("Show separator must be On or Off")
        if self.view not in GROUPED_VIEWS:
            raise ValueError("Choose a supported sidebar View")
        lines = (self.line1, self.line2)
        if any(not isinstance(line, (list, tuple)) for line in lines):
            raise ValueError("Priority lines must be lists of fields")
        names = tuple(name for line in lines for name in line)
        if not names:
            raise ValueError("Choose at least one field for the Priority view")
        if any(not isinstance(name, str) or name not in SIDEBAR_FIELDS for name in names):
            raise ValueError("Choose supported Priority fields")
        if len(set(names)) != len(names):
            raise ValueError("Each field can appear only once in the Priority view")
        return replace(self, machine_color=color(self.machine_color),
                       project_color=color(self.project_color), agent_color=color(self.agent_color),
                       tab_color=color(self.tab_color), line1=tuple(self.line1), line2=tuple(self.line2))


@dataclass(frozen=True)
class Settings:
    # Retain the selected profile when neither mode is enabled.
    mode: str = "grouped"
    enabled: bool = False
    grouped: ModeSettings = field(default_factory=ModeSettings)
    priority: ModeSettings = field(default_factory=lambda: ModeSettings(
        machine_color=DARK_BLUE, line1=FACTORY_PRIORITY_LINES[0], line2=FACTORY_PRIORITY_LINES[1]))

    def profile(self, mode=None):
        mode = self.mode if mode is None else mode
        if mode not in MODES:
            raise ValueError("Mode must be Grouped or Priority")
        return getattr(self, mode)

    def with_profile(self, mode, **changes):
        self.profile(mode)
        if set(changes) - PROFILE_FIELDS[mode]:
            raise ValueError("These settings do not belong to this mode")
        return replace(self, **{mode: replace(self.profile(mode), **changes)})

    def with_active(self, mode):
        if mode is None:
            return replace(self, enabled=False)
        self.profile(mode)  # Validate the target before changing activation.
        return replace(self, mode=mode, enabled=True)

    @property
    def visible_fields(self):
        profile = self.profile()
        if self.mode == "priority":
            return profile.line1 + profile.line2
        return ("machine", "project", "status", "agent") + (("tab",) if profile.view == "agent/tab" else ())

    @property
    def show_separator(self):
        return self.profile().show_separator

    def normalized(self):
        if self.mode not in MODES:
            raise ValueError("Mode must be Grouped or Priority")
        if type(self.enabled) is not bool:
            raise ValueError("Active must be Yes or No")
        if not isinstance(self.grouped, ModeSettings) or not isinstance(self.priority, ModeSettings):
            raise ValueError("Each mode must have its own settings profile")
        return replace(self, grouped=self.grouped.normalized(), priority=self.priority.normalized())

    def rows(self, *, token_names=None):
        if not self.enabled:
            raise ValueError("Both modes are inactive; restore the native sidebar")
        profile = self.profile()
        colors = [fallback if value == "default" else value for value, fallback in
                  zip((profile.machine_color, profile.project_color, profile.agent_color, profile.tab_color), DEFAULT_COLORS)]
        names = dict(zip(TOKENS, TOKENS)) if token_names is None else token_names
        def token(name, index, bold):
            return {"token": "$" + names[name], "fg": colors[index], "bold": bold}
        if self.mode == "priority":
            tokens = {"status": "state_icon", "agent": token("has_agent", 2, False),
                      "tab": {"token": "tab", "fg": colors[3], "bold": False},
                      "machine": token("has_machine", 0, True), "project": token("has_project", 1, True)}
            return [[tokens[name] for name in line] for line in (profile.line1, profile.line2) if line]
        tab = [{"token": "tab", "fg": colors[3], "bold": False}] if profile.view == "agent/tab" else []
        return [[token("has_machine", 0, True)], [token("has_project", 1, True)],
                [token("has_agent_prefix", 2, False), "state_icon", token("has_agent", 2, False)] + tab,
                [token("has_gap", 0, True)]]


def legacy_profile(data, mode):
    """Translate earlier presets without guessing at unknown stored fields."""
    data = dict(data)
    view = data.pop("view", "agent/project/machine" if mode == "grouped" else "agent/project")
    if view not in LEGACY_VIEWS:
        raise Conflict("Unknown legacy View; preferences were preserved")
    if "tab_color" in data or "line1" in data or "line2" in data:
        raise Conflict("Mixed settings formats; preferences were preserved")
    data["tab_color"] = data.get("agent_color", "default") if "tab" in view else "default"
    if "tab" in view and data["tab_color"] == "default":
        data["tab_color"] = DEFAULT_COLORS[2]
    if mode == "grouped":
        return ModeSettings(**data, view="agent/tab" if "tab" in view else "agent")
    if "show_separator" in data and type(data["show_separator"]) is not bool:
        raise ValueError("Show separator must be On or Off")
    data.pop("show_separator", None)  # This field never affected Priority.
    line1 = ("status", "agent") if view == "agent" else ("status",) + tuple(view.split("/")[1:])
    return ModeSettings(**data, line1=line1, line2=() if view == "agent" else ("agent",))


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
def lock(path, timeout=3, *, skip_busy=False):
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
                    if skip_busy:
                        yield False
                        return
                    raise Conflict("Another sidebar operation is running; try again") from None
                time.sleep(.05)
        try:
            yield True
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

    def token_names(self):
        """Keep server-global metadata keys independent for each installation."""
        private_directory(self.state)
        identity = self.state / "instance.json"
        with lock(self.state / "instance.lock"):
            if identity.exists():
                try:
                    data = json.loads(identity.read_text())
                    if (not isinstance(data, dict) or set(data) != {"schema", "id"}
                            or type(data["schema"]) is not int or data["schema"] != 1
                            or not isinstance(data["id"], str)):
                        raise ValueError("Unsupported installation identity")
                    identifier = uuid.UUID(hex=data["id"])
                    if identifier.hex != data["id"]:
                        raise ValueError("Invalid installation identity")
                except (ValueError, TypeError, AttributeError) as error:
                    raise Conflict("Invalid installation identity; existing state was preserved") from error
            else:
                identifier = uuid.uuid4()
                atomic_write(identity, json.dumps({"schema": 1, "id": identifier.hex}))
        compact = base64.urlsafe_b64encode(identifier.bytes).decode().rstrip("=")
        return {name: f"has_{compact}_{suffix}" for name, suffix in zip(TOKENS, ("m", "p", "i", "a", "g"))}

    def load(self):
        if not self.preferences.exists():
            return Settings(enabled=self.legacy_active(default=False))
        data = tomllib.loads(self.preferences.read_text())
        schema = data.pop("schema", None)
        if type(schema) is not int or schema not in (1, 2, 3, 4):
            raise Conflict("Unsupported settings schema; preferences were preserved")
        try:
            if schema < 4:
                if "enabled" in data:
                    raise Conflict("Mixed settings formats; preferences were preserved")
                data["enabled"] = self.legacy_active()
            elif "enabled" not in data:
                raise Conflict("Missing activation preference; preferences were preserved")
            if schema == 1:
                shared = {name: data.pop(name) for name in ("machine_color", "project_color", "agent_color", "show_separator")
                          if name in data}
                grouped = legacy_profile({**shared, "view": data.pop("grouped_view", "agent/project/machine")}, "grouped")
                priority = legacy_profile({**shared, "view": data.pop("priority_view", "agent/project")}, "priority")
            elif schema == 2:
                grouped = legacy_profile(data.pop("grouped", {}), "grouped")
                priority = legacy_profile(data.pop("priority", {}), "priority")
            else:
                profiles = {}
                for mode in MODES:
                    values = data.pop(mode, {})
                    if not isinstance(values, dict) or set(values) - PROFILE_FIELDS[mode]:
                        raise Conflict("Unknown or misplaced profile fields; preferences were preserved")
                    if schema == 4:
                        defaults = asdict(Settings().profile(mode))
                        values = {**{key: defaults[key] for key in PROFILE_FIELDS[mode]}, **values}
                    profiles[mode] = ModeSettings(**values)
                grouped, priority = profiles["grouped"], profiles["priority"]
            return Settings(**data, grouped=grouped, priority=priority).normalized()
        except (TypeError, ValueError) as error:
            raise Conflict("Unknown or malformed settings fields; preferences were preserved") from error

    def legacy_active(self, *, default=True):
        """Read the old pause receipt only until preferences are saved as schema 4."""
        path = self.state / "control.json"
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text())
        except ValueError as error:
            raise Conflict("Unsupported runtime state; existing state was preserved") from error
        if not isinstance(data, dict) or data.get("schema") != 1 or type(data.get("active")) is not bool:
            raise Conflict("Unsupported runtime state; existing state was preserved")
        return data["active"]

    def save(self, settings):
        settings = settings.normalized()
        private_directory(self.config)
        with lock(self.config / "settings.lock"):
            self.load()  # Refuse to replace a newer schema.
            text = "schema = 4\n" + f"mode = {toml(settings.mode)}\nenabled = {toml(settings.enabled)}\n"
            for mode in MODES:
                values = asdict(settings.profile(mode))
                for name in (("line1", "line2") if mode == "grouped" else ("view", "show_separator")):
                    values.pop(name)
                text += f"\n[{mode}]\n" + "".join(f"{k} = {toml(v)}\n" for k, v in values.items())
            atomic_write(self.preferences, text)


def toml(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
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
    def __init__(self, config, state, *, token_names=None):
        self.config = Path(config).resolve()
        self.state = Path(state)
        self.receipt = self.state / "presentation.json"
        self.token_names = token_names

    def _read(self):
        return self.config.read_text() if self.config.exists() else ""

    @staticmethod
    def _restored_text(current, receipt):
        if current == receipt["installed"]:
            return receipt["original"]
        text = current
        for name, field in receipt["fields"].items():
            actual = spans(text)[0].get(tuple(name.split(".")))
            if actual and actual[2] == field["installed"]:
                text = rewrite(text, name, raw=field["original"], remove=field["original"] is None)
        return text

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
            values = (0, settings.rows(token_names=self.token_names))
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
            # Keep legacy ownership records for safe restoration, but stop
            # writing or checking native order. Mode is visual-only.
            fields = dict(receipt["fields"]) if receipt else {}
            for name in FIELDS:
                path = tuple(name.split("."))
                previous = original_spans.get(path)
                fields[name] = {"original": receipt["fields"][name]["original"] if receipt else
                                previous[2] if previous else None,
                                "installed": installed_spans[path][2]}
            journal = {"schema": 1, "config": str(self.config), "phase": "prepared",
                       "original": self._restored_text(original, receipt) if receipt else original,
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

    def restore(self, validate=None, *, native_defaults=False):
        private_directory(self.state)
        with lock(self.state / "presentation.lock"):
            receipt = self._journal()
            current = self._read()
            text = self._restored_text(current, receipt) if receipt else current
            if native_defaults:
                # Explicitly choosing both No means Herdr's built-in layout,
                # rather than a previous native-only customization. Lifecycle
                # cleanup still uses the reversible receipt without this flag.
                agents = tomllib.loads(text).get("ui", {}).get("sidebar", {}).get("agents", {})
                rows = agents.get("rows", DEFAULT_ROWS)
                native_tokens = {"state_icon", "machine", "workspace", "tab", "agent"}
                native_only = isinstance(rows, list) and bool(rows) and all(
                    isinstance(row, list) and bool(row) and all(
                        isinstance(token, str) and token in native_tokens for token in row
                    ) for row in rows
                )
                if agents.get("rows_by_agent") or not native_only:
                    raise Conflict("A custom agent layout exists; native defaults were not applied")
                for name in FIELDS:
                    text = rewrite(text, name, remove=True)
            if text != current:
                self._publish(text, validate, expected=current)
            if receipt:
                self.receipt.unlink()
            return text != current
