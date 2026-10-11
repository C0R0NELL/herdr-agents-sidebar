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

The runtime check covers applying the manifest, live settings keyboard interaction,
color changes, hiding the separator, Esc dismissal, native mouse afterward,
workspace renaming, moving panes between workspaces, removal/restoration of an
anchor, remote-server reconnect, foreign projection detection,
source-only cleanup and exact config restoration on disable.
It also verifies subscription acceptance and actual event delivery directly;
periodic snapshots cannot hide a rejected subscription.

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

## Limits

- The public Herdr 0.9.3 token API cannot pad an icon without also adding an
  inline dot. The user accepted `· ○ name` for aligned native icons and names.
  Show separator controls the machine gap only, not this native punctuation.
- Server tokens are shared while machine catalogs belong to each client. A
  local-only client can see a trailing `·` if another client sees more machines.
  The user accepted this; Show separator can disable it.
- Headings belong to real agent rows: clicking them focuses their anchor. Empty
  workspaces stay in the upper Spaces section. There is no tab level or collapse.
- Grouping requires native spaces order without a foreign active agent projection.
  The plugin does not set projections and refuses a detected local conflict.
  The public CLI does not expose remote projection queries; remove conflicting
  projections on remote endpoints before relying on grouped order.
- Default group colors are the Settings palette's Yellow (`#f1fa8c`),
  Blue (`#89b4fa`) and Purple (`#bd93f9`), selected by the user on 2026-10-11.
  Herdr still owns the background and status palette. Group defaults do not
  switch with the host theme; explicit Settings colors are preserved and take
  precedence. The popup offers Dracula accents alongside the existing Blue option.
- Cleanup cannot reach an offline machine. Its tokens expire by TTL. Failed config
  validation preserves the recovery receipt rather than overwriting user settings.
- Actual SSH authentication, macOS and Herdr Web UI have not been tested. The
  manifest advertises Linux only. No integration with the Web UI is claimed.
