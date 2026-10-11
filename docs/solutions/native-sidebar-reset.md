# Missing Machine after Restore defaults

Investigated on 2026-10-11 after the user requested the complete native sidebar
whenever both modes are No.

The main environment had both modes inactive, no ownership receipt, and an
explicit native-only Rows override containing Status/Workspace/Tab above Agent.
Machine was absent from that override. The earlier Restore correctly recovered
the pre-plugin bytes, but that behavior did not meet the user's clarified request
for Herdr's built-in layout. It was not a metadata cache issue.

Explicit No and Restore defaults now remove only the Rows and Row gap overrides
after reversible cleanup. Herdr supplies its default rows, which include Machine,
without copying a built-in theme into plugin configuration. Native ordering,
bindings and unrelated fields stay unchanged. Foreign custom tokens and
per-agent row overrides are rejected before configuration changes.
Machine visibility remains native: Herdr 0.9.3 supplies machine context for
multiple endpoints and omits it in a local-only client. The real regression uses
two disposable servers so its Machine assertion exercises that native path.

Lifecycle cleanup on disable/unlink/uninstall, errors and an active Restart
still restores the original owned fields. Active Restart temporarily pauses the
worker without normalizing that baseline. Passive navigation while inactive does
not overwrite subsequent native edits or activate a worker.

The focused regression checks failed before implementation and passed after it.
They cover a missing-Machine override with and without a receipt, validation
failure, foreign layouts, idempotence, and active Restart's original baseline.
The real disposable-session Restore check starts with Machine hidden and asserts
Machine/Project/Tab for each native entry afterward. No agent identities, histories
or credentials are changed.
