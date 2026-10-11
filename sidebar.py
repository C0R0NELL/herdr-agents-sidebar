#!/usr/bin/env python3
"""Native sidebar plugin entrypoint and its four-option settings popup."""

import argparse
import curses
from dataclasses import replace
from pathlib import Path
import sys
import tomllib

from configuration import Conflict, DRACULA_COLORS, PLUGIN_ID, Settings, Store

# Intent: a developer choosing visual groups while staying in Herdr.
# Palette: yellow machines, blue projects, purple names; native status.
# Depth/surfaces: Herdr owns the popup frame; do not add a second decorative box.
# Typography: the user's terminal font, bold title, reversed selected row.
# Spacing: one terminal cell, one blank line below the title and before the footer.
OPTIONS = (("Default", "default"), ("Blue", "#89b4fa")) + tuple(
    (name, DRACULA_COLORS[name])
    for name in ("Yellow", "White", "Green", "Red", "Cyan", "Pink", "Purple", "Orange"))
FIELDS = (("Machine color", "machine_color"), ("Project color", "project_color"),
          ("Agent color", "agent_color"), ("Show separator", "show_separator"))


def display(value):
    if type(value) is bool:
        return "On" if value else "Off"
    return next((name for name, code in OPTIONS if code == value), value)


def settings_ui(herdr, store):
    """No terminal mouse reporting: Herdr retains sidebar and tab navigation."""
    def run(screen):
        curses.curs_set(0)
        screen.keypad(True)
        curses.set_escdelay(25)
        settings = store.load()
        selected, choosing, option = 0, False, 0
        message = ""
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            def write(y, x, text, attributes=0):
                if 0 <= y < height and x < width - 1:
                    try:
                        screen.addnstr(y, x, text, width-x-1, attributes)
                    except curses.error:
                        pass
            write(1, 2, FIELDS[selected][0] if choosing else "Settings", curses.A_BOLD)
            if choosing:
                for index, (name, _) in enumerate(OPTIONS):
                    write(index + 3, 2, f"  {name}", curses.A_REVERSE if option == index else 0)
            else:
                for index, (name, field) in enumerate(FIELDS):
                    text = f"  {name:<19} [{display(getattr(settings, field))}]"
                    write(index + 3, 2, text, curses.A_REVERSE if selected == index else 0)
            write(height-3, 2, message)
            write(height-2, 2, "'enter' select | 'esc' back" if choosing else "'enter' change | 'esc' close")
            screen.refresh()
            key = screen.getch()
            if key == 27:
                if choosing:
                    choosing = False
                else:
                    return
            elif key in (curses.KEY_UP, ord("k")):
                if choosing:
                    option = (option - 1) % len(OPTIONS)
                else:
                    selected = (selected - 1) % len(FIELDS)
            elif key in (curses.KEY_DOWN, ord("j")):
                if choosing:
                    option = (option + 1) % len(OPTIONS)
                else:
                    selected = (selected + 1) % len(FIELDS)
            elif key in (10, 13, curses.KEY_ENTER):
                field = FIELDS[selected][1]
                if not choosing and selected < 3:
                    choosing = True
                    option = next((i for i, (_, code) in enumerate(OPTIONS)
                                   if code == getattr(settings, field)), 0)
                    message = ""
                    continue
                value = OPTIONS[option][1] if choosing else not settings.show_separator
                proposed = replace(settings, **{field: value})
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
