# Changelog

## 0.2.1 - 2026-10-11

### Fixes

- Prevent flickering machine/project headings when multiple active installations
  share a connected Herdr server. Scope metadata keys with a durable installation
  UUID, preserving each installation's layout and restricting cleanup to its own keys.
- Serialize worker refreshes with Settings saves so an interrupted save cannot
  reapply an outdated layout; keep pause and cleanup responsive while a save is busy.
- Show Priority line summaries only inside Edit lines and move Save view away
  from the footer instructions.

### Defaults

- Update the factory Priority profile to Project/Machine on line 1 and Status/Agent
  on line 2, with Dark blue machines. Grouped keeps Agent view, default colors and
  separator Off. Fresh installations and Restore defaults keep both modes inactive;
  updates preserve existing saved profiles and activation.

### Documentation and validation

- Verify independent layouts and cleanup with two real connected installations,
  remote Settings interaction, concurrent saves and durable UUIDs through upgrades
  and reinstall. Keep the capture tool aligned with the new factory profiles.
- Document installation isolation and connectivity diagnostics, and remove approval
  history and duplicated guidance from AGENTS.md while retaining technical safeguards.

## 0.2.0 - 2026-10-11

### Breaking changes

- Replace Apply sidebar with explicit activation in Settings. Fresh installations
  are enabled in Herdr with both modes inactive; users choose a profile matching
  their Herdr sidebar order and set Active to Yes.
- Make Restore defaults reset both profiles and activation to the factory snapshot.
  Both Active controls set to No use Herdr's built-in native rows rather than an
  earlier native-only customization. Disable/uninstall still restore owned settings.

### Features

- Add independent Grouped and Priority Settings tabs with saved views and four
  colors per mode. Zero or one mode may be active; browsing tabs does not activate them.
- Keep Grouped's machine/project tree with Agent or Agent / Tab views, and add a
  Priority editor to show, hide and order native Status, Agent, Tab, Machine and
  Project across two lines, with draft cancellation and empty-layout validation.
- Add Dark blue for tabs. New factory profiles use Yellow/Blue/Purple/Dark blue,
  Grouped's Agent view with separator Off, and Priority's Project above Status/Agent/Tab.
- Preserve existing preferences and legacy pauses when migrating to schema 4,
  without overwriting saved colors, views or activation during updates and reinstall.

### Fixes

- Keep Herdr's native agent ordering independent of presentation settings, retain
  legacy ownership receipts and preserve unrelated edits when reapplying layouts.
- Restore native Machine context after deactivation or factory reset, rejecting
  foreign layouts and retaining recovery records if validation fails.
- Preserve profiles and activation when restarting the worker, serialize user
  operations with bounded locks, and keep paused modes inactive during navigation.
- Keep both Priority line summaries visible without overlapping the settings footer.

### Documentation and validation

- Clarify post-install activation and native ordering, and add real default Grouped
  and Priority captures side by side in the README with a repeatable capture command.
- Extend unit and isolated Herdr checks for independent profiles, configurable
  fields, native status and focus, factory resets, paused installs and durable upgrades.

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
