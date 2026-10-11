"""Compute owned presentation tokens from ordered native Herdr snapshots.

The caller supplies machine order and native snapshots. Grouped requires spaces
order; Priority attaches context to every agent regardless of client order.
This module never moves
workspaces, renames agents or changes agent authority. It deliberately has no
filesystem, socket or credential access.
"""

from dataclasses import dataclass
import unicodedata

TOKENS = ("has_machine", "has_project", "has_agent_prefix", "has_agent", "has_gap")
HEADERS = ("has_machine", "has_project", "has_gap")
MODES = ("grouped", "priority")
GROUPED_VIEWS = ("agent", "agent/tab")
SIDEBAR_FIELDS = ("status", "agent", "tab", "machine", "project")
DEFAULT_PRIORITY_LINES = (("status", "project"), ("agent",))
BLANK = "\u2800"
MAX_AGENTS = 2048
MAX_MACHINES = 64
BIDI_CONTROLS = frozenset("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


@dataclass(frozen=True)
class AgentKey:
    machine: str
    session: str
    workspace_id: str
    pane_id: str


@dataclass(frozen=True)
class Machine:
    id: str
    session: str
    label: str
    snapshot: dict
    stale: bool = False


@dataclass(frozen=True)
class Patch:
    key: AgentKey
    tokens: dict


def label(value, fallback, limit):
    """Bound API token length; the native renderer handles width and clipping."""
    value = value if isinstance(value, str) else ""
    value = "".join(char for char in value
                    if unicodedata.category(char) not in {"Cc", "Cs"} and char not in BIDI_CONTROLS).strip()
    value = value or fallback
    return value if len(value) <= limit else value[:limit-1] + "…"


def key(machine, item):
    return AgentKey(machine.id, machine.session, item["workspace_id"], item["pane_id"])


def layout(machines, *, gap_between_machines, mode="grouped", fields=None):
    """Return owned desired state, including explicit clears for nonanchors.

Cached machines remain part of grouping, as they do in Herdr's sidebar. The
publisher must not write to a stale connection. A gap policy is explicit because
shared server tokens cannot describe independent per-client machine catalogs.
"""
    if mode not in MODES:
        raise ValueError("Unknown sidebar mode")
    fields = ("status", "project", "agent") if fields is None else fields
    if any(field not in SIDEBAR_FIELDS for field in fields):
        raise ValueError("Unknown sidebar field")
    show_project = mode == "grouped" or "project" in fields
    show_machine = mode == "grouped" or "machine" in fields
    if len(machines) > MAX_MACHINES:
        raise ValueError("Machine limit exceeded; refusing a partial tree")
    result = {}
    previous = None
    for machine in machines:
        workspaces = {item["workspace_id"]: item.get("label") for item in machine.snapshot.get("workspaces", [])}
        panes = {item["pane_id"]: item for item in machine.snapshot.get("panes", [])}
        projects = set()
        first = True
        active_project = None
        for agent in machine.snapshot.get("agents", []):
            identity = key(machine, agent)
            if identity in result:
                raise ValueError("Duplicate native agent identity; refusing an ambiguous tree")
            if len(result) >= MAX_AGENTS:
                raise ValueError("Agent limit exceeded; refusing a partial tree")
            project = agent["workspace_id"]
            if mode == "grouped" and show_project and project in projects and project != active_project:
                raise ValueError("Noncontiguous workspace order; native spaces order is required")
            if mode == "grouped" and show_machine and first and previous is not None and gap_between_machines:
                result[previous]["has_gap"] = "·"
            heading = None
            if show_project and project not in projects:
                heading = label(workspaces.get(project), "Unknown workspace", 76)
                if not first or not show_machine:
                    heading = BLANK * 2 + heading
            pane = panes.get(agent["pane_id"], {})
            name = next((agent.get(field) for field in ("name", "display_agent", "agent", "title")
                         if agent.get(field)), pane.get("label") or agent["pane_id"])
            if mode == "priority":
                # Every entry carries its selected context. The native client may
                # reorder it at any time without displacing shared headings.
                result[identity] = {
                    "has_machine": label(machine.label, "Unknown machine", 80) if show_machine else None,
                    "has_project": label(workspaces.get(project), "Unknown workspace", 76) if show_project else None,
                    "has_agent_prefix": None,
                    "has_agent": label(name, "Unknown agent", 80) if "agent" in fields else None,
                    "has_gap": None,
                }
                continue
            # Native rows start at column 1, then at column 3 after headings.
            # Pad before the native icon to compensate for both row offsets.
            # Herdr adds a dot between this blank token and the native icon.
            has_heading = (first and show_machine) or heading is not None
            padding = 2 if has_heading else 4
            result[identity] = {
                "has_machine": label(machine.label, "Unknown machine", 80) if first and show_machine else None,
                "has_project": heading,
                "has_agent_prefix": BLANK * padding if show_project else None,
                "has_agent": label(name, "Unknown agent", 80),
                "has_gap": None,
            }
            projects.add(project)
            active_project = project
            previous = identity
            first = False
    return result


def patches(machines, desired, *, renew=False):
    """Return global clear-before-set phases to avoid duplicate moving headers.

Reads current snapshot tokens instead of trusting a successful previous write.
Unknown token keys are never touched. Removed agents still in native panes get
their own presentation tokens cleared; already closed panes need no request.
Renewals include live values to refresh their per-token TTL.
"""
    removals, updates = [], []
    for machine in machines:
        if machine.stale:
            continue
        items = {item["pane_id"]: item for item in machine.snapshot.get("panes", [])}
        items.update({item["pane_id"]: item for item in machine.snapshot.get("agents", [])})
        for item in items.values():
            identity = key(machine, item)
            wanted = desired.get(identity, {})
            current = item.get("tokens") or {}
            clear = {name: None for name in TOKENS
                     if current.get(name) is not None and
                     (wanted.get(name) is None or
                      (name in HEADERS and current[name] != wanted.get(name)))}
            update = {name: value for name, value in wanted.items()
                      if value is not None and (renew or current.get(name) != value)}
            if clear:
                removals.append(Patch(identity, clear))
            if update:
                updates.append(Patch(identity, update))
    return removals, updates
