#!/usr/bin/env python3
"""Native sidebar plugin entrypoint and its settings popup."""

import argparse
import curses
from dataclasses import replace
from pathlib import Path
import sys
import tomllib

from configuration import Conflict, DARK_BLUE, DRACULA_COLORS, PLUGIN_ID, Settings, Store
from layout import GROUPED_VIEWS, MODES, SIDEBAR_FIELDS

# Intent: a developer choosing visual groups while staying in Herdr.
# Palette: yellow machines, blue projects, purple names; native status.
# Depth/surfaces: Herdr owns the popup frame; do not add a second decorative box.
# Typography: the user's terminal font, bold title, reversed selected row.
# Spacing: one terminal cell, one blank line below the title and before the footer.
OPTIONS = (("Default", "default"), ("Blue", "#89b4fa")) + tuple(
    (name, DRACULA_COLORS[name])
    for name in ("Yellow", "White", "Green", "Red", "Cyan", "Pink", "Purple", "Orange")) + (("Dark blue", DARK_BLUE),)
MODE_OPTIONS = (("Grouped", "grouped"), ("Priority", "priority"))
VIEW_OPTIONS = tuple((" / ".join(part.title() for part in view.split("/")), view) for view in GROUPED_VIEWS)
FIELDS = (("Active", "active"), ("View", "view"), ("Machine color", "machine_color"),
          ("Project color", "project_color"), ("Agent color", "agent_color"), ("Tab color", "tab_color"))


def display(value):
    if type(value) is bool:
        return "On" if value else "Off"
    return next((name for name, code in MODE_OPTIONS + VIEW_OPTIONS + OPTIONS if code == value), value)


def write(screen, y, x, text, attributes=0):
    height, width = screen.getmaxyx()
    if 0 <= y < height and x < width - 1:
        try:
            screen.addnstr(y, x, text, width-x-1, attributes)
        except curses.error:
            pass


def line_text(line):
    return " | ".join(name.title() for name in line) or "(empty)"


def priority_view_ui(screen, profile):
    """Edit a bounded draft; Escape never writes a partial layout."""
    lines = [list(profile.line1), list(profile.line2)]
    selected, message = 0, ""
    while True:
        screen.erase()
        height, _ = screen.getmaxyx()
        write(screen, 1, 2, "Priority view", curses.A_BOLD)
        for index, line in enumerate(lines):
            write(screen, index + 3, 2, f"Line {index+1}  [{line_text(line)}]")
        for index, name in enumerate(SIDEBAR_FIELDS):
            location = next((i for i, line in enumerate(lines) if name in line), None)
            text = "Hidden" if location is None else f"Line {location+1} | position {lines[location].index(name)+1}"
            write(screen, index+6, 2, f"  {name.title():<12} {text}", curses.A_REVERSE if selected == index else 0)
        write(screen, 12, 2, "  Save view", curses.A_REVERSE if selected == len(SIDEBAR_FIELDS) else 0)
        write(screen, height-3, 2, message or "Enter cycles Hidden -> Line 1 -> Line 2 -> Hidden")
        write(screen, height-2, 2, "left/right reorder | up/down select | esc cancel")
        screen.refresh()
        key = screen.getch()
        if key == 27:
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected = (selected-1) % (len(SIDEBAR_FIELDS)+1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected+1) % (len(SIDEBAR_FIELDS)+1)
        elif key in (10, 13, curses.KEY_ENTER):
            if selected == len(SIDEBAR_FIELDS):
                try:
                    draft = replace(profile, line1=tuple(lines[0]), line2=tuple(lines[1])).normalized()
                    return draft.line1, draft.line2
                except ValueError as error:
                    message = str(error)
                continue
            name = SIDEBAR_FIELDS[selected]
            location = next((i for i, line in enumerate(lines) if name in line), None)
            if location is not None:
                lines[location].remove(name)
            if location != 1:
                lines[0 if location is None else 1].append(name)
            message = ""
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT) and selected < len(SIDEBAR_FIELDS):
            name = SIDEBAR_FIELDS[selected]
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
            choices = VIEW_OPTIONS if field == "view" else OPTIONS
            if choosing:
                for index, (name, _) in enumerate(choices):
                    write(screen, index + 3, 2, f"  {name}", curses.A_REVERSE if option == index else 0)
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
                for index, (name, field) in enumerate(fields):
                    value = ("Yes" if settings.enabled and settings.mode == tab else "No") if field == "active" else (
                        "Edit lines" if field == "view" and tab == "priority" else display(getattr(profile, field)))
                    text = f"  {name:<19} [{value}]"
                    write(screen, index + 5, 2, text, curses.A_REVERSE if selected == index else 0)
                if tab == "priority":
                    write(screen, 11, 2, "Line 1  [" + line_text(profile.line1) + "]")
                    write(screen, 12, 2, "Line 2  [" + line_text(profile.line2) + "]")
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
                if field == "view" and tab == "priority":
                    lines = priority_view_ui(screen, profile)
                    if lines is None:
                        message = ""
                        continue
                    proposed = settings.with_profile(tab, line1=lines[0], line2=lines[1])
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
    herdr, store = Herdr(), Store()
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
