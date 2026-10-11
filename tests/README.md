# Checks

`python3 -B tests/check.py` runs grouping, config/ownership and publication tests
using temporary files and fictitious local Git repositories. It does not control
Herdr or contact GitHub/provider APIs.

For integration checks, install `tests/requirements.txt` in an isolated Python
environment. `check_herdr.py` uses real Herdr servers, PTYs and a local SSH shim
under temporary XDG roots. It checks the runtime, settings popup, native renderer,
mouse routing and cleanup. Runtime checks exercise Grouped/Priority mode changes
with explicit saved active layouts and worker startup by native navigation, without an Apply action,
independently of native order, two-line entries, configured colors and remote
focus from either line. View checks exercise both Grouped choices with fixed
headings and native tabs, then build ordered Priority lines in the real popup.
Draft/cancel behavior, native status repositioning, colors, unchanged ordering
and local/remote mouse focus are checked. A Tab-only view preserves every native
agent, and a completely empty draft is rejected without writes.
Profile checks browse and edit the inactive tab, preserving active config bytes,
then activate/deactivate each mode and check its own colors, view and native status.
Factory checks begin with both modes No, activate from the actual Settings popup,
verify Project above Status/Agent/Tab, and exercise Restart preserving activation
and Restore defaults resetting both profiles to No. The Restore regression
starts from native-only rows that omit Machine and requires its native context
to reappear in the open client with multiple machines. Both line summaries must
remain visible without overlapping the footer.
Use `--priority-evidence PATH.json` with `check_herdr.py` to capture Priority.
`check_visual.py` can additionally export the actual
captured cells with `--evidence docs/evidence/native-sidebar.json`.
Captures follow the default separator Off; `--show-separator` checks optional gaps.

`python3 -B tests/capture_previews.py` regenerates the README's Grouped and Priority
SVGs and their JSON evidence under `docs/evidence/`. It activates each factory
profile through the real Settings popup, verifies native rows and default colors,
and captures terminal cells from two isolated servers. These previews show each
mode after activation; a fresh installation still starts with both modes No.

`check_managed_upgrade.py` uses Herdr's actual installer with a temporary Git URL
rewrite to a local bare repository. It checks managed updates, uninstall and local
links while preserving preferences outside source checkouts. A fresh installation
must be enabled in Herdr but leave both modes No until the user chooses in Settings.
It also installs with the temporary server stopped and verifies startup applies
the saved layout before further navigation or agent activity.

No integration check uses the user's main server, SSH profiles, projects, agent
credentials or conversation history. Unix socket/PTY permission is required.
