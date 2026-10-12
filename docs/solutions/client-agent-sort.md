# Client-local Grouped/Priority ordering

Investigated on 2026-10-11 with Herdr 0.9.3, protocol 22.

After adding both presentation modes, the plugin is no longer restricted to
native Grouped ordering. Priority repeats context per agent and supports either
native order. The original tree-order requirement remains specific to Grouped:
its machine/project anchors need native Grouped order. Settings chooses the
presentation without synchronizing the client-local native heading.

## Symptom

Clicking the native Agents heading from Grouped to Priority moves agents across
workspace and machine boundaries. This plugin's headings move with their real
anchor agents, so the resulting list no longer represents a grouped tree.

## Verified cause

The native click handler updates that client's in-memory `agent_panel_sort` and
its chrome preferences. It does not publish the choice through the socket API.
The client preserves manually selected ordering when configuration is reloaded.
The public schema bundled with 0.9.3 has no `agent_panel_sort` field, client sort
query, or event for this choice. `session.snapshot` reports server agent order,
not a particular client's rendered order. Reading `config.toml` therefore cannot
identify a client's current choice either.

Two real PTY clients were attached to one disposable server using the existing
`HerdrHarness`, separate temporary XDG roots and fictitious agent fixtures.
After marking `agente03` Working and clicking Priority in only the second client:

| Observation | Result |
| --- | --- |
| First client's heading | Grouped |
| First client's order | agente01, agente02, agente03 |
| Second client's heading | Priority |
| Second client's order | agente03, agente02, agente01 |
| Public snapshot's agent order | Unchanged |
| Second client's configuration | Still `agent_panel_sort = "spaces"` |

The second client was switched back to Grouped and its original order verified.
Only temporary servers, panes and terminals were used; the main server and user
agents were untouched. This is a native terminal proof, not a Web UI test.

## Integration boundary

Owned metadata tokens are shared by clients. Even detecting one window's mode
would not provide separate heading anchors for another window using a different
mode. Automatic adaptation requires a supported way to observe each client's
order and render presentation in that client's context.

The user approved manual Mode selection in Settings. Grouped keeps the tree
when the native heading uses Grouped;
Priority's factory snapshot shows native Status/Project/Agent above Machine.
Priority View can arrange or hide those fields plus Tab, Pane, Status text and
raw/clean Terminal title across two lines. Grouped retains fixed machine/project
headings and one editable agent line. Choices are remembered per mode.
Identities remain machine-scoped. Users choose
Herdr's native order independently; Priority rows support either choice. The runtime leaves `ui.agent_panel_sort`
unchanged and does not read private chrome preferences, infer UI mode from
lifecycle state, or replace another plugin's projection. Real runtime checks
exercise both layouts, independent native sort changes, colors and remote focus.

## Primary sources

- [Bundled public schema and snapshot contract](https://herdr.dev/docs/socket-api/).
- [Local click handler](https://github.com/herdrdev/herdr/blob/v0.9.3/src/client/shell/mouse.rs#L1987).
- [Manual order survives config reload](https://github.com/herdrdev/herdr/blob/v0.9.3/src/client/shell/config.rs#L71).
- [Combined native priority sorting](https://github.com/herdrdev/herdr/blob/v0.9.3/src/client/shell/aggregate_navigation.rs#L150).
