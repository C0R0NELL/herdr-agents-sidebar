# Independent presentation profiles

Updated on 2026-10-11 after the user requested Grouped and Priority Settings tabs.
The earlier format remembered View per mode but shared all colors. Editing an
inactive layout therefore needed independent durable profiles, not a temporary
change to the selected mode.

Schema 4 stores a selected `mode`, boolean `enabled` and `[grouped]` / `[priority]`
profiles. Zero or one profile may be active. Both Active controls set to No stops
workers, clears owned tokens and uses Herdr's default native rows, including
Machine, while retaining the last
mode and both profiles. Yes on either profile activates only that one. Browsing
a tab does not activate it, and inactive edits leave
the native presentation unchanged. Native order remains a separate Herdr choice.

The reader accepts schemas 1, 2 and 3 without rewriting them. Shared colors become
independent profiles, and the active mode is preserved. The latest user request
fixes Grouped's machine/project tree and limits its View to Agent or Agent / Tab;
old presets retain optional Tab. Priority presets become explicit ordered fields
on two lines, retaining their previous layout. Visible tabs inherit their earlier
agent color during migration; new Tab color defaults to Dark blue. Schema 4 saves
four colors per mode, Grouped View/Show separator, and Priority line1/line2 arrays.
Mixed formats, unknown/misplaced fields and newer schemas are rejected before
replacing preferences.
Legacy runtime pause records are included when reading old preferences, and are
ignored after schema 4 is saved. Settings and Restore now share one activation
record; startup and event hooks cannot reactivate a paused profile.

The migration regression was observed failing before implementation and passing
afterward. Priority editing uses a bounded draft until Save view; Escape cancels
without writing. Empty layouts and repeated fields are rejected. Native status
positions and colors are handled by Herdr, without copied lifecycle state.
Actual popup and installer checks are described in [verified behavior](../viabilidade.md).
