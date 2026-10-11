# Flickering machine labels and interrupted settings saves

Investigated on 2026-10-11 after switching modes, colors and views, including
access to a machine through another Herdr installation.

Two isolated servers ran the same plugin with Priority on the viewer and Grouped
on the connected machine. The connected server's machine tokens continuously
alternated between Local, machine02 and missing values. Each worker used the same
five global keys, repeatedly undoing the other's updates and clearing headers.

The [public token contract](https://herdr.dev/docs/socket-api/#agent-state-reporting)
uses resource-wide keys: the latest accepted update wins, regardless of source.
Tokens permit at most 32 ASCII characters, with 32 keys retained per resource.
Changing the source string alone cannot isolate these writes.

An installation UUID is now saved atomically in private durable `instance.json`.
Its compact representation scopes five wire keys, each 28 characters long.
Configuration rows and snapshot/publish adapters use the same mapping; layout
computation still uses logical fields. The official plugin identity and metadata
source remain unchanged. Updates, Restore and reinstall preserve this UUID;
invalid/newer identity files are rejected without replacement. Other installations
and unrelated token reporters retain their keys, including during cleanup.

A separate deterministic worker regression reproduced an interrupted Settings
save: the config already had Priority rows, while preferences still had Grouped.
The worker reapplied Grouped, then retained those rows after the new preferences
were saved. Worker refresh now shares the settings operation lock, skipping a
busy update rather than failing. Pause/disable checks remain outside that lock
so an operation waiting for worker cleanup cannot deadlock it.

Validation uses real disposable servers, clients and Settings, different local
and remote layouts, multiple reconciliation intervals and independent cleanup.
Unit checks cover durable/private identity, invalid state and the save race.
The complete integration suite and 77 unit checks passed. Managed upgrade checks
also preserve the UUID across upgrade, source transitions and reinstall. After
isolated validation, the linked local plugin worker was restarted alone; the
stored preferences and unrelated Herdr settings remained unchanged, config check
passed, and its metadata stayed present over ten seconds of observation.
No main-server restart or agent credentials are involved. The separately reported
Windows screenshot was not available in the VPS and has not been visually checked.
