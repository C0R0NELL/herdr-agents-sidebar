# Rejected global status subscription

Observed on 2026-10-10 during activation with Herdr 0.9.3, protocol 22.

## Cause

`pane.agent_status_changed` requires a specific `pane_id`; subscribing with
only its type returns `invalid_request`. Most workspace and pane lifecycle
events accept global subscriptions. Treating all of them alike rejected the
entire request.

The worker initially published through periodic snapshots before reading the
rejection. Successful ticks cleared the error record and retry counter, hiding
the broken subscription behind an apparently healthy sidebar.

## Correction

Subscribe only to the required global lifecycle events. Native status indicators
remain Herdr's responsibility. Confirm `subscription_started` before allowing
reconciliation, retain event bytes received with that acknowledgement, and
process complete buffered messages without waiting for another socket read.

## Regression checks

`tests/check_herdr.py` directly subscribes and verifies a workspace rename event
from an isolated real server before exercising plugin activation. This failed
with the original request and passed after correcting its scope. Periodic
snapshots cannot satisfy this check.

`tests/test_runtime.py` checks immediate rejection and delivery of an event
coalesced with the acknowledgement. The latter also failed before the framing
correction.
