# Automatic activation without an Apply action

Investigated on 2026-10-11 with Herdr 0.9.3, protocol 22. A later user decision
requires an explicit first choice in Settings: fresh installations remain enabled
in Herdr, with both profiles inactive. The automatic lifecycle described below
now applies only after a profile is activated or to preserved active preferences.

The user expects installation to enable the sidebar without another Plugin Manager
action. The previous menu and README required Apply, and automatic worker startup
refused even a customized layout containing only native tokens. Explicit Apply
had been the only path that could replace those rows with a reversible receipt.

The manifest exposes Settings, Restart sidebar and Restore defaults. Startup,
workspace/tab/pane focus, agent detection and status changes ensure the worker is
running. Initial activation accepts native-only rows and keeps the restoration
receipt; foreign custom tokens/projections and later user edits remain protected.
Both Active controls set to No pause activation, including subsequent activity
hooks, while preserving preferences. Restore defaults instead resets preferences
to the factory snapshot with both inactive. Restart reloads code while preserving
the activation choice; it never resumes a paused profile.

Herdr 0.9.3 has no post-install hook. Its installer registers the plugin after
build commands, which lack runtime socket/session context. Startup hooks run
when the server starts, rather than on install/link/enable. A running session
therefore starts an already activated profile on the next matching native activity;
an offline installation starts a saved active profile at the next startup. This is automatic activation without
an Apply step, not a synchronous post-install guarantee. No changes to Herdr or
alternative installer are required.

Tests use actual navigation changes: refocusing the same workspace does not emit
a focus-change event. Isolated checks cover real installer activation, native
custom rows, all Settings layouts, Restore defaults, Restart preserving activation, offline startup,
uninstall and durable preferences. Unit checks retain config conflict coverage.

Primary references:

- [Build and startup hooks](https://herdr.dev/docs/plugins/#build-commands).
- [Public plugin API](https://herdr.dev/docs/socket-api/#plugin-apis).
- [0.9.3 installer](https://github.com/herdrdev/herdr/blob/v0.9.3/src/cli/plugin.rs).
- [0.9.3 hook runtime](https://github.com/herdrdev/herdr/blob/v0.9.3/src/app/api/plugins/runtime.rs).
