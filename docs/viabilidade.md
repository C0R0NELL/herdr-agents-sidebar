# Verified behavior and limits

Validated on 2026-10-11 with **Herdr 0.9.3, protocol 22**, Python 3.12 and Linux.
The runtime uses Python 3.11+ standard-library facilities. After explicit user
authorization, the main session also uses a local link to this checkout. Its
configuration was validated and reloaded without restarting Herdr or agents.
These runtime checks use disposable sessions rather than a user's remote machine.
GitHub publication is a separate release step described in [publishing](publishing.md).

## Evidence

`tests/check_herdr.py` exercises the actual installed binary with isolated config,
state and runtime roots. Two real Herdr servers use a local SSH transport shim:
authentication/network transport is simulated; native API forwarding, bridge,
metadata, rendering and focus routing are real.

The terminal checks cover widths 18, 22 and 36, marker-free name indentation,
bold headings, colors, native status marks, selective `·`, Unicode/control
normalization and mouse focus of local/remote anchors. The captured cells are
exported as [SVG](evidence/native-sidebar.svg) with a small
[evidence report](evidence/native-sidebar.json), using fictitious names only.
The README capture shows the default Show separator Off. The same visual check
also exercises optional machine gaps when enabled.

The runtime check covers applying the manifest, live settings keyboard interaction,
color changes, hiding the separator, Esc dismissal, native mouse afterward,
workspace renaming, moving panes between workspaces, removal/restoration of an
anchor, remote-server reconnect, foreign projection detection,
source-only cleanup and exact config restoration on disable.
It also verifies subscription acceptance and actual event delivery directly;
periodic snapshots cannot hide a rejected subscription.
Factory checks verify a fresh installation is enabled in Herdr with both profiles
inactive, and native navigation cannot activate them. The actual Settings popup
activates the chosen mode, accepting reversible native-only rows. Restart preserves
active and inactive choices. Restore defaults resets both customized profiles to
the factory snapshot with both inactive. Offline installer checks verify startup
respects saved activation, applying active layouts before further navigation.
The latest factory snapshot uses native Status/Project/Agent above Machine in Priority,
with Dark blue machines; its actual activation and Restore checks passed after
the user's snapshot update. The earlier README images remain unchanged by request.
Herdr 0.9.3 has no synchronous post-install hook; saved active modes start at
startup or the next matching native event.
See [the activation investigation](solutions/automatic-activation.md).

`tests/check_managed_upgrade.py` runs the real installer against a temporary Git
URL rewrite. Installation, a changed upstream version, uninstall, local link and
unlink preserve preferences and ownership records outside the source checkout.
Unit checks cover independent machine/session/workspace/pane identities, diffs,
stale cache handling, config conflicts, later edits and interrupted config updates.

## Public contracts

The [Socket API](https://herdr.dev/docs/socket-api/) provides native snapshots,
events and display-only metadata. This plugin publishes only `has_machine`,
`has_project`, `has_agent_prefix`, `has_agent` and `has_gap`, with source
`plugin:c0r0nell.agents-sidebar` and 60-second TTL renewed every 20 seconds.
Old anchors are cleared before new ones on each endpoint. Updates are per-token,
so a short intermediate display is possible; the API does not offer a tree transaction.

The [0.9.3 token renderer](https://github.com/herdrdev/herdr/blob/v0.9.3/src/ui/sidebar/tokens.rs)
omits unresolved rows. The [native sidebar](https://github.com/herdrdev/herdr/blob/v0.9.3/src/client/shell/agent_sidebar.rs)
uses different first/continuation offsets, compensated by U+2800 blank cells.
The blank-only prefix precedes the native status token, followed by the agent
name. It compensates both native offsets so icons and names stay in fixed
columns with and without headings. Herdr inserts ` · ` before the icon; the
user explicitly accepted that dot on 2026-10-11 to align icons. No `>` markers
are generated. Icons and colors update natively; narrow text clips while
keeping the indicator visible. The optional machine separator remains `·`,
and the global row gap remains zero.

Saved profiles come from [native machine APIs](https://herdr.dev/docs/connecting-machines/).
Remote requests target explicit profile IDs and never fall back to Local. No
remote plugin installation is needed for metadata publication. Remote snapshots
are polled at five-second intervals in a bounded pool, independently of local
events. Cached disconnected machines remain grouped in memory; Herdr supplies
its own stale styling. No credential store or network scanning is used.

Settings has Grouped and Priority tabs. Grouped retains the tree; Priority defaults to two
native rows: project above, native status, agent and tab below. The default colors
are yellow, blue, purple and dark blue, with the machine separator off. This factory
snapshot was captured from the user's approved preferences on 2026-10-11; it
contains presentation preferences only, without user paths or agent data. Priority hides
machine labels by default without changing the machine-scoped identities.
At 36 columns, both local and
remote rows were checked with native priority transitions, configured colors and
mouse focus on the context and agent lines.
Switching Mode leaves native ordering unchanged; the user selects Grouped or
Priority in Herdr independently. Old preferences default to Grouped, and machine
gaps are absent in Priority even if Show separator is saved as On.

Grouped View follows Active and offers Agent or Agent / Tab. Both were exercised
through the real popup at 36 columns on 2026-10-11, retaining one machine heading
per machine, one project heading per project, and aligned native status/name cells.
Tab uses the native label inline after the agent, with its own Dark blue default.

Priority View edits an ordered draft of Status, Agent, Tab, Machine and Project
across two lines. Real popup checks built Machine/Project above Status/Agent/Tab,
verified that drafts and Escape did not change preferences or config, and applied
both lines with working local/remote mouse focus. Native Status was then moved
to the end of line 2 and between Machine and Project on line 1; Working kept its
native glyph and color. Empty lines are omitted, without changing agent identities.
The same test hid all fields except Tab, retained six native agents and verified
local/remote focus. Saving a completely empty draft was rejected without changing
the valid preferences or presentation.

The tabbed popup checks also changed all four colors and the ordered View in an
inactive Priority profile while the active configuration remained byte-identical.
Activating either profile restored its own preferences. Deactivating the active
profile left both No, stopped the worker, cleared owned tokens and restored the
native default layout, including Machine, by removing the owned Rows/Row gap
overrides. The older check used a native config without these overrides;
the missing-Machine regression also starts from custom native rows without
Machine and checks its presence in the real renderer after Restore defaults.
Disable/unlink/uninstall continue to restore the original configuration.
Reopening Settings, real navigation and
inactive edits preserved that pause; Yes resumed only the chosen profile.
Native Working icons retained their glyph/color. Reopening preserved
profile selection and values. Unit checks cover fixed Grouped headings, field
validation and schema 1/2/3 migration to schema 4, including old Restore pauses.
Failure to save during reactivation restored native rows and kept both modes No.
Older Priority presets become
ordered lines; Grouped retains optional Tab with the requested fixed tree.
Ambiguous formats are rejected before writing. Managed install/update/uninstall
and local link/unlink preserve external preferences. An actual offline reinstall
and startup kept both No, with no worker or presentation receipt created.

On 2026-10-11, a two-installation regression reproduced global token conflicts
between an active Grouped machine and a Priority viewer. Installation-scoped keys
now keep both real sidebars stable while remote Settings is opened and edited from
the connected viewer. Disabling the viewer clears only its own keys. The real
installer preserves the private installation UUID across upgrades and reinstall.
A deterministic unit worker regression also reproduced and fixed rollback of new
rows during the config/preference save gap. Details are in
[independent installations](solutions/independent-installations.md).

## Limits

- The public Herdr 0.9.3 token API cannot pad an icon without also adding an
  inline dot. The user accepted `· ○ name` for aligned native icons and names.
  Show separator controls the machine gap only, not this native punctuation.
- Server tokens are shared while machine catalogs belong to each client. A
  local-only client can see a trailing `·` if another client sees more machines.
  The user accepted this; Show separator can disable it.
- Headings belong to real agent rows: clicking them focuses their anchor. Empty
  workspaces stay in the upper Spaces section. There is no tab level or collapse.
- Both Grouped and Priority presentation modes are supported. The ordering
  requirement applies only to the Grouped tree: select native Grouped (spaces
  order) so machines and projects remain contiguous. Priority rows carry their
  own context and remain valid under either native order.
  Settings does not synchronize the native heading; users select it separately.
  Native Priority sorts by activity, which can separate a Grouped tree's anchors.
  A foreign projection may also override native ordering.
  The plugin does not set projections and refuses a detected local conflict.
  The public CLI does not expose remote projection queries; remove conflicting
  projections on remote endpoints before relying on grouped order.
  A manually selected Priority mode is client-local and is not exposed by the
  public 0.9.3 API. Two isolated clients confirmed different UI orders with the
  same server snapshot; see [the ordering investigation](solutions/client-agent-sort.md).
- Default group colors are the Settings palette's Yellow (`#f1fa8c`),
  Blue (`#89b4fa`), Purple (`#bd93f9`) and Dark blue tabs (`#6272a4`).
  The three group defaults were selected by the user on 2026-10-11.
  Herdr still owns the background and status palette. Group defaults do not
  switch with the host theme; explicit Settings colors are preserved and take
  precedence. The popup offers Dracula accents alongside the existing Blue option.
- Cleanup cannot reach an offline machine. Its tokens expire by TTL. Failed config
  validation preserves the recovery receipt rather than overwriting user settings.
- Actual SSH authentication, macOS and Herdr Web UI have not been tested. The
  manifest advertises Linux only. No integration with the Web UI is claimed.
