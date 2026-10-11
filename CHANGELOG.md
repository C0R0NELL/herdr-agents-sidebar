# Changelog

## 0.1.0 - 2026-10-11

### Features

- Group native agents by machine and workspace with indented names, aligned
  native status indicators and optional machine separators.
- Add Settings for machine, project and agent colors, including Default,
  and Show separator with On/Off. Use yellow machines, blue projects and
  purple names by default, preserving native status colors and explicit preferences.
- Publish owned metadata incrementally through public Herdr APIs, with bounded
  remote reconciliation, TTL renewal and source-only cleanup.
- Preserve preferences outside source checkouts and restore owned configuration
  without overwriting later user edits.
- Validate native rendering, settings, focus, disable/uninstall, managed upgrades
  and local links in isolated Herdr environments.

### Maintenance

- Establish the official plugin identity and repository layout for local editing
  and managed GitHub installation.
- Document durable storage, isolated validation, and the existing sidebar specification.
- Add a single-command release workflow with matching manifest/changelog checks,
  Conventional Commits, atomic push, tags, and GitHub Release notes.
- Test publication in temporary repositories and require actual runtime and
  Herdr integration checks before every plugin release.
- Exclude local screenshots and runtime artifacts from Git, and reject them
  during publication even if ignore rules are removed.
