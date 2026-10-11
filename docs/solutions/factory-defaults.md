# Factory defaults and explicit activation

Implemented on 2026-10-11 after the user requested explicit first activation and
adopted their configured profiles as the factory snapshot.

Settings in configuration.py defines the immutable factory defaults: Grouped has
the fixed tree, Agent view and separator Off. The user's later snapshot on the same
day replaces Priority with Project/Machine on line 1, Status/Agent on line 2 and
Dark blue machines. Other colors retain the Yellow/Blue/Purple/Dark blue default
palette. Both modes start inactive. No personal paths, identities or state are included. A fresh installer
registers the plugin enabled in Herdr; Settings is available immediately, while
startup and navigation leave the native sidebar intact until Active becomes Yes.

Existing settings and legacy activation are preserved through upgrades. Restore
defaults uses the same snapshot as first installation, stopping workers and
restoring Herdr's built-in native presentation, including Machine. Active No
removes Rows and Row gap overrides to use those same native defaults
without resetting profiles. Restart preserves settings and activation, including
both modes No. Full user operations share a bounded lock, separate from worker
cleanup and atomic preference writes.

The later missing-Machine report exposed an earlier native-only customization
being restored from the receipt. Both No and Restore defaults now explicitly
remove those two overrides. Disable/uninstall, failures and an active Restart
keep the reversible original configuration. See [native reset](native-sidebar-reset.md).

The actual popup check reproduced the Priority line-2 summary being overwritten
by the footer in the 60x18 popup. Moving both summaries directly below the color
fields initially left the footer separate. A later user request removed these
summaries from Settings entirely: Line 1 and Line 2 now appear only inside
Edit lines, and Save view sits higher with space before the instructions. The
real popup check verifies both conditions. Factory rendering verifies native
status glyphs/colors and Dark blue machines. The view checks also cover an
independently styled Tab when selected.

The later Dark blue factory machine color exposed a test assumption: the profile
check counted color-picker movement from Default, selecting Cyan instead of Pink.
Its navigation now starts from the saved color. The expected saved values and real
rendered colors remain independently asserted; the application did not require a
color-picker behavior change.

The release gate also caught a Priority view check accepting six agent rows before
their remote machine context was present. Since config reloads and remote metadata
updates are asynchronous, the check now waits for the complete expected layout
within its existing timeout before inspecting colors or focus. Persistent missing
context still fails the check; no fixed sleep or weaker assertion was introduced.

Unit checks observed the old fresh activation, non-resetting Restore and
reactivating Restart failing the new requirements before implementation. Active
Restart has a regression check against recursive operation-lock acquisition.
Real disposable-session checks cover Settings selection, factory rendering,
Restart and Restore. The actual installer checks fresh enabled/both No behavior,
updates, uninstall/reinstall, local links and offline startup without contacting
GitHub or using the main server.
