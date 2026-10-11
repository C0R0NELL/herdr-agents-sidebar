# Local editing

Agents Sidebar has one official identity: `c0r0nell.agents-sidebar`. Local links
and managed installations use the same manifest and durable preferences. The
development machine links this checkout directly after user-authorized activation
on 2026-10-10. The user approved the first release, `0.1.0`, on 2026-10-11.

Runtime requires Python 3.11+ with curses and Herdr 0.9.3+ on Linux. Modules are
`sidebar.py` (entrypoint/settings), `layout.py` (pure grouping), `configuration.py`
(preferences/config ownership) and `runtime.py` (public transports/lifecycle).

## Local source and normal installation

For a requested local installation, run from this checkout:

```sh
herdr plugin link "$PWD/herdr-plugin.toml" --enabled
herdr plugin action invoke apply --plugin c0r0nell.agents-sidebar
```

Linking does not run startup hooks immediately. Apply sidebar activates it now;
startup and native activity hooks ensure it runs in later server sessions. Use
Restart sidebar after code edits or managed updates; Settings changes apply live.
Restore sidebar stops its workers and restores only its owned presentation.
Disabling/unlinking/uninstalling also triggers worker cleanup without ending agents.

GitHub installs on another machine consume published commits. The Plugin Manager
excludes local links from update checks. Users explicitly apply available updates.
The release script in `scripts/` is publication tooling, not an installer.

## Durable storage

Respect matching `HERDR_PLUGIN_CONFIG_DIR` / `HERDR_PLUGIN_STATE_DIR` and XDG roots.
Default paths are:

```text
~/.config/herdr/plugins/config/c0r0nell.agents-sidebar/settings.toml
~/.local/state/herdr/plugins/c0r0nell.agents-sidebar/presentation.json
~/.local/state/herdr/plugins/c0r0nell.agents-sidebar/control.json
```

Settings use schema 1 and private atomic writes. State contains config ownership,
bounded worker locks and small error records, without persisted agent snapshots
or transcripts. The ownership receipt includes the original Herdr configuration
for restoration, including any private values already in that configuration.
Directories use owner-only permissions (0700), and files use 0600. The plugin
does not read agent credentials. Updates and source removal preserve these directories.

Configuration changes are limited to `ui.agent_panel_sort`,
`ui.sidebar.agents.row_gap` and `ui.sidebar.agents.rows`. Explicit Apply sidebar
can replace a layout containing only known native tokens, preserving it for
restoration. Automatic startup refuses nondefault layouts. Foreign custom tokens
and `rows_by_agent` conflict. Later edits to owned fields are preserved on restoration;
unrelated sections, comments and shortcuts are preserved. Native config check
validates every proposed change before publishing it.

## Checks

Install `tests/requirements.txt` in an isolated Python environment, then run:

```sh
python3 -B tests/check.py
python3 -B tests/check_herdr.py
python3 -B tests/check_managed_upgrade.py
python3 -B scripts/release.py --dry-run
```

Integration checks need Unix sockets/PTY permissions. They use separate temporary
config/state/runtime roots, controlled agent fixtures and a local SSH shim.
Managed checks rewrite only a temporary Git config to a local bare repository;
they never contact GitHub.

See [verified limits](viabilidade.md) and [publication rules](publishing.md).
