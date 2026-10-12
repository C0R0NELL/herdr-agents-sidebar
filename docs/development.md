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
```

New installations are enabled in Herdr, but both modes start inactive. Open
Settings and set the chosen profile's Active to Yes; this applies its layout
immediately. Existing preferences and activation survive updates and reinstall.
Once a profile is active, startup and native workspace/tab/pane focus or agent
detection/status events ensure its worker is running. Herdr 0.9.3 has no post-install
hook: install/link/enable do not run startup hooks, and build commands have no
session socket context. A running session therefore applies the sidebar on the
next real navigation or agent event if a saved mode is active; offline installs
also respect the saved activation at startup.
There is no Apply action in the Plugin Manager. Use
Restart sidebar after code edits or managed updates; Settings changes apply live.
Restart never activates an inactive mode or resets preferences. Restore defaults
resets both profiles to the factory snapshot, stops workers and restores only
the owned native presentation. Both Active controls become No. Setting either
to Yes resumes that profile without a separate restart. Turning Active to No
also restores native presentation, but preserves both customized profiles.
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
~/.local/state/herdr/plugins/c0r0nell.agents-sidebar/instance.json
```

Settings use schema 4 and private atomic writes. Schemas 1, 2 and 3 remain readable
without modifying files. Shared colors become independent profiles; older
Priority presets become ordered fields on two lines. Grouped restores the fixed
tree, retaining optional Tab. Existing visible tabs retain their previous color;
new tabs default to Dark blue (#6272a4). The selected mode and Grouped separator are preserved.
The next save writes the new format, rejecting unknown fields, mixed formats,
misplaced mode-specific fields and newer schemas.
The selected `mode` and boolean `enabled` are the single activation record.
When neither mode is active, the selected profile is remembered for reopening
Settings. Legacy `control.json` pause records are read during migration; schema 4
is authoritative afterward, so old runtime flags cannot override new settings.
State contains config ownership,
an installation UUID, bounded worker locks and small error records, without persisted agent snapshots
or transcripts. The ownership receipt includes the original Herdr configuration
for restoration, including any private values already in that configuration.
Directories use owner-only permissions (0700), and files use 0600. The plugin
does not read agent credentials. Updates and source removal preserve these directories.

The installation UUID names this viewer's five metadata keys, so another installation
on a connected machine cannot replace or clear them. The official plugin ID and
metadata source remain stable. Logical layout fields remain `has_machine`,
`has_project`, `has_agent_prefix`, `has_agent` and `has_gap`; actual server keys
include a compact UUID. Keep `instance.json` through reinstall and source updates.
Malformed identities are rejected rather than regenerated. Settings saves and
worker configuration refresh share a lock; the worker skips busy refreshes while
still checking for pause/disable, avoiding a cleanup deadlock.

The factory snapshot is defined by Settings in configuration.py. It follows the
user-approved profiles captured on 2026-10-11: Grouped's fixed tree with View Agent
and Show separator Off; Priority has native Status/Project/Agent on line 1 and
Machine on line 2, with its Machine color set to Dark blue. Other colors retain the default
Yellow/Blue/Purple/Dark blue palette. Both modes
are inactive. Factory reset uses the same defaults as a new installation;
existing saves, including old active modes, are not reset by upgrades.
User operations serialize under a bounded operation lock; workers have their own
lock so cleanup can finish before reactivation without competing config writes.
Existing saved choices, including Show separator On,
are preserved. Settings without a `mode` field load as Grouped. Priority uses two
native rows per agent: native status, project and agent above, machine below.
Its factory view hides Tab and gaps; identities remain scoped by machine.
Settings has Grouped and Priority tabs, each with Active, View and four colors.
Left/right or Tab changes the inspected profile without activating it. Active
allows zero or one active profile: Yes deactivates the other profile, and No on
the active profile stops workers, clears owned tokens and removes the Rows and
Row gap overrides so Herdr supplies its default native layout, including Machine.
Both No persists across startup, navigation and reinstall. Editing
inactive profiles does not activate them or change the live rows.
Show separator appears only in Grouped.
Grouped View selects Agent or Agent / Tab; machine/project headings remain fixed.
Priority View opens a draft editor for Status, Agent, Tab, Machine and Project.
Line summaries appear only inside Edit lines. Save view sits above the footer
with two blank rows separating the action from the instructions.
Enter cycles a field through Hidden, Line 1, Line 2 and Hidden; left/right reorders
it within its assigned line. Save view applies the draft; Escape discards it.
Each field appears at most once, at least one field must remain, and empty lines
are omitted. The native renderer supplies separators, offsets and clipping.
`[grouped]` saves View and Show separator; `[priority]` saves ordered `line1` and
`line2` arrays. Both save their own four colors. Tab uses the native `tab` token
and an independent color, without another tree level or a copied label. Status
remains the unstyled native `state_icon` at its chosen position. Hidden Priority
fields clear owned tokens; native identities and ordering remain unchanged.
Mode chooses presentation only. For the Grouped tree, select Grouped using
Herdr's native heading so machines and projects stay together. Priority rows
keep their context under either native order; choosing native Priority adds
activity-based sorting. Settings never synchronizes that client-local choice.
No private client preferences are read.

Configuration changes are limited to `ui.sidebar.agents.row_gap` and
`ui.sidebar.agents.rows`. Native `ui.agent_panel_sort` is preserved. Existing
0.1.0 receipts retain old sort ownership for safe cleanup, without new sort writes.
Automatic activation can replace a layout containing only known native tokens,
preserving it for lifecycle restoration. Both No and Restore defaults explicitly
request Herdr's built-in rows rather than that earlier native customization.
Disable/unlink/uninstall, failures and an active Restart still use the reversible
receipt. Foreign custom tokens and `rows_by_agent` conflict. Later edits to owned
fields are preserved by lifecycle restoration;
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
