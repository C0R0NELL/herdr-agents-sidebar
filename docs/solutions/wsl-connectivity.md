# WSL endpoint unavailable after a sidebar restart

Investigated on 2026-10-11 after the user reported a disconnected WSL machine
near the end of local sidebar validation. Diagnostics did not modify SSH profiles,
network services or the machine connection.

The VPS Herdr client recorded `endpoint health check timed out` at
18:31:29.422800 UTC. The plugin's two configuration reloads completed successfully
at 18:30:36.667655 and 18:30:37.171539 UTC. The VPS server remained running and the
saved endpoint remained enabled; the earlier plugin restart verification had
also compared unrelated Herdr configuration before and after without changes.

The official `herdr machine status <label> --json` probe failed to connect to the
WSL SSH port with `Connection timed out`. Tailscale reported the VPS and the
notebook's Windows endpoint online, but the WSL endpoint offline. Its reported
last-seen timestamp was 18:30:00.1 UTC and its last handshake was
18:29:57.385497376 UTC. An independent `tailscale ping` received no reply.

These observations establish current WSL network unavailability outside the
sidebar presentation. They do not establish why WSL lost its Tailscale connection
or prove a causal relationship with the plugin restart. Last-seen timestamps are
not precise disconnection timestamps. Diagnosing shutdown, a stopped daemon or
another WSL-side network failure requires checking the WSL environment itself;
the unreachable SSH endpoint cannot supply those logs from this VPS.

The user subsequently reported that starting WSL from PowerShell itself failed
with `Wsl/Service/0x80072746`. This adds evidence of a WSL startup problem, rather
than a sidebar-only connection failure, without establishing its underlying
cause. No recovery result was provided, so the WSL issue remains unverified.
