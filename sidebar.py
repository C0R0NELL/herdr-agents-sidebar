#!/usr/bin/env python3
"""Native sidebar plugin entrypoint and its settings popup."""

import argparse
import curses
from dataclasses import replace
from pathlib import Path
import sys
import tomllib

from configuration import COLOR_FIELDS, Conflict, DARK_BLUE, DRACULA_COLORS, PLUGIN_ID, Settings, Store
from layout import GROUPED_FIELDS, MODES, SIDEBAR_FIELDS, SIDEBAR_LABELS

# Intent: a developer choosing visual groups while staying in Herdr.
# Palette: yellow machines, blue projects, purple names; native status.
# Depth/surfaces: Herdr owns the popup frame; do not add a second decorative box.
# Typography: the user's terminal font, bold title, reversed selected row.
# Spacing: one terminal cell, one blank line below the title and before the footer.
OPTIONS = (("Default", "default"), ("Blue", "#89b4fa")) + tuple(
    (name, DRACULA_COLORS[name])
    for name in ("Yellow", "White", "Green", "Red", "Cyan", "Pink", "Purple", "Orange")) + (("Dark blue", DARK_BLUE),)
MODE_OPTIONS = (("Grouped", "grouped"), ("Priority", "priority"))
FIELDS = (("Active", "active"), ("View", "view")) + tuple(
    (SIDEBAR_LABELS[name] + " color", name + "_color") for name in COLOR_FIELDS)


def display(value):
    if type(value) is bool:
        return "On" if value else "Off"
    return next((name for name, code in MODE_OPTIONS + OPTIONS if code == value), value)


def write(screen, y, x, text, attributes=0):
    height, width = screen.getmaxyx()
    if 0 <= y < height and x < width - 1:
        try:
            screen.addnstr(y, x, text, width-x-1, attributes)
        except curses.error:
            pass


def line_text(line):
    return " | ".join(SIDEBAR_LABELS[name] for name in line) or "(empty)"


def option_rows(screen, entries, selected, *, top=5):
    """Scroll bounded popup lists, retaining a blank row before Save view."""
    height, _ = screen.getmaxyx()
    capacity = max(1, height-top-5)
    position = next(i for i, (index, _) in enumerate(entries) if index == selected)
    offset = max(0, min(position-capacity+1, len(entries)-capacity))
    for row, (index, text) in enumerate(entries[offset:offset+capacity]):
        write(screen, top+row, 2, text, curses.A_REVERSE if index == selected else 0)


def view_ui(screen, profile, mode):
    """Edit a bounded draft; Escape never writes a partial layout."""
    fields = GROUPED_FIELDS if mode == "grouped" else SIDEBAR_FIELDS
    lines = [list(profile.line1)] + ([list(profile.line2)] if mode == "priority" else [])
    selected, message = 0, ""
    while True:
        screen.erase()
        height, _ = screen.getmaxyx()
        write(screen, 1, 2, mode.title() + " view", curses.A_BOLD)
        for index, line in enumerate(lines):
            label = "Agent line" if mode == "grouped" else f"Line {index+1}"
            write(screen, index + 3, 2, f"{label}  [{line_text(line)}]")
        entries = []
        for index, name in enumerate(fields):
            location = next((i for i, line in enumerate(lines) if name in line), None)
            text = "Hidden" if location is None else (
                ("Shown" if mode == "grouped" else f"Line {location+1}") + f" | position {lines[location].index(name)+1}")
            entries.append((index, f"  {SIDEBAR_LABELS[name]:<22} {text}"))
        entries.extend(((None, ""), (len(fields), "  Save view")))
        option_rows(screen, entries, selected)
        write(screen, height-3, 2, message or ("Enter toggles Hidden / Shown" if mode == "grouped" else
                                             "Enter cycles Hidden -> Line 1 -> Line 2 -> Hidden"))
        write(screen, height-2, 2, "left/right reorder | up/down select | esc cancel")
        screen.refresh()
        key = screen.getch()
        if key == 27:
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected = (selected-1) % (len(fields)+1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected+1) % (len(fields)+1)
        elif key in (10, 13, curses.KEY_ENTER):
            if selected == len(fields):
                try:
                    changes = {"line1": tuple(lines[0])}
                    if mode == "priority":
                        changes["line2"] = tuple(lines[1])
                    replace(profile, **changes).normalized()
                    return changes
                except ValueError as error:
                    message = str(error)
                continue
            name = fields[selected]
            location = next((i for i, line in enumerate(lines) if name in line), None)
            if location is not None:
                lines[location].remove(name)
            if mode == "grouped" and location is None:
                lines[0].append(name)
            elif mode == "priority" and location != 1:
                lines[0 if location is None else 1].append(name)
            message = ""
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT) and selected < len(fields):
            name = fields[selected]
            line = next((line for line in lines if name in line), None)
            if line is not None:
                index = line.index(name)
                target = index + (-1 if key == curses.KEY_LEFT else 1)
                if 0 <= target < len(line):
                    line[index], line[target] = line[target], line[index]


def settings_ui(herdr, store):
    """No terminal mouse reporting: Herdr retains sidebar and tab navigation."""
    def run(screen):
        curses.curs_set(0)
        screen.keypad(True)
        curses.set_escdelay(25)
        settings = store.load()
        tab = settings.mode
        selected, choosing, option = 0, False, 0
        message = ""
        while True:
            screen.erase()
            height, _ = screen.getmaxyx()
            fields = FIELDS + (("Show separator", "show_separator"),) if tab == "grouped" else FIELDS
            selected = min(selected, len(fields)-1)
            write(screen, 1, 2, fields[selected][0] if choosing else "Settings", curses.A_BOLD)
            field = fields[selected][1]
            profile = settings.profile(tab)
            choices = OPTIONS
            if choosing:
                option_rows(screen, [(i, "  " + name) for i, (name, _) in enumerate(choices)], option, top=3)
            else:
                tab_x = 2
                for index, (name, mode) in enumerate(MODE_OPTIONS):
                    attributes = curses.A_REVERSE if mode == tab else 0
                    if settings.enabled and mode == settings.mode:
                        attributes |= curses.A_BOLD
                    write(screen, 3, tab_x, name, attributes)
                    tab_x += len(name)
                    if index == 0:
                        write(screen, 3, tab_x, " | ")
                        tab_x += 3
                entries = []
                for index, (name, field) in enumerate(fields):
                    value = ("Yes" if settings.enabled and settings.mode == tab else "No") if field == "active" else (
                        ("Edit line" if tab == "grouped" else "Edit lines") if field == "view" else display(getattr(profile, field)))
                    entries.append((index, f"  {name:<27} [{value}]"))
                option_rows(screen, entries, selected)
            field = fields[selected][1]
            hint = {"active": "Both No restores the native sidebar" if settings.enabled else "Set Active to Yes to use this layout",
                    "view": "Changes belong only to this tab"}.get(field, "") if not choosing else ""
            write(screen, height-3, 2, message or hint)
            write(screen, height-2, 2, "'enter' select | 'esc' back" if choosing else "left/right tabs | 'enter' change | 'esc' close")
            screen.refresh()
            key = screen.getch()
            if key == 27:
                if choosing:
                    choosing = False
                else:
                    return
            elif not choosing and key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("\t"), curses.KEY_BTAB):
                tab = MODES[1 - MODES.index(tab)]
                message = ""
            elif key in (curses.KEY_UP, ord("k")):
                if choosing:
                    option = (option - 1) % len(choices)
                else:
                    selected = (selected - 1) % len(fields)
            elif key in (curses.KEY_DOWN, ord("j")):
                if choosing:
                    option = (option + 1) % len(choices)
                else:
                    selected = (selected + 1) % len(fields)
            elif key in (10, 13, curses.KEY_ENTER):
                field = fields[selected][1]
                if field == "view":
                    changes = view_ui(screen, profile, tab)
                    if changes is None:
                        message = ""
                        continue
                    proposed = settings.with_profile(tab, **changes)
                elif not choosing and field not in ("show_separator", "active"):
                    choosing = True
                    option = next((i for i, (_, code) in enumerate(choices)
                                   if code == getattr(profile, field)), 0)
                    message = ""
                    continue
                elif field == "active":
                    proposed = settings.with_active(None if settings.enabled and settings.mode == tab else tab)
                else:
                    value = choices[option][1] if choosing else not profile.show_separator
                    proposed = settings.with_profile(tab, **{field: value})
                try:
                    from runtime import save_settings
                    save_settings(herdr, store, proposed)
                    settings, choosing, message = proposed, False, "Saved"
                except (OSError, RuntimeError, ValueError) as error:
                    message = str(error)
    curses.wrapper(run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "ensure", "worker", "apply", "restore", "restart", "settings", "settings-open"))
    args = parser.parse_args()
    if args.command == "check":
        # Installation builds validate source without touching a running server.
        manifest = tomllib.loads(Path(__file__).with_name("herdr-plugin.toml").read_text())
        if manifest["id"] != PLUGIN_ID:
            raise ValueError("Manifest identity differs from runtime identity")
        import layout
        import runtime
        Settings().normalized()
        print("Agents Sidebar source check passed (Python 3.11+)")
        return
    from runtime import Herdr, apply, ensure, restore, restart, worker
    store = Store()
    herdr = Herdr(store)
    if args.command == "settings":
        settings_ui(herdr, store)
    elif args.command == "settings-open":
        # Placement comes from the manifest: Herdr 0.9.3's CLI does not accept
        # 'popup' as a --placement value, though its public pane API supports it.
        herdr.command("plugin", "pane", "open", "--plugin", PLUGIN_ID,
                      "--entrypoint", "settings", "--focus")
    else:
        {"ensure": ensure, "worker": worker, "apply": apply, "restore": restore, "restart": restart}[args.command](herdr, store)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Agents Sidebar: {error}", file=sys.stderr)
        raise SystemExit(1)
