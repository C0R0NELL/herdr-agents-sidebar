# Working in this repository

Read [specs.md](specs.md) before implementation and follow its behavior and boundaries.
Use [docs/viabilidade.md](docs/viabilidade.md) for verified behavior and known limits.
Keep code and documentation in English; preserve the specification in Portuguese.
Prefer Python's standard library and add modules only for meaningful responsibilities.

## Repository layout and checks

- `herdr-plugin.toml`: the only official manifest.
- `sidebar.py`: runtime entrypoint and Settings popup.
- `layout.py`: native identities, grouping and incremental token patches.
- `configuration.py`: durable preferences and reversible config ownership.
- `runtime.py`: public API transports, workers and lifecycle.
- `tests/`: all tests and check entrypoints; dependencies in `tests/requirements.txt`.
- `scripts/release.py`: the single publication command, outside the plugin runtime.
- `CHANGELOG.md` and `docs/`: release notes, development guidance and evidence.

Run `python3 -B tests/check.py` for isolated unit and release-tooling checks.
Before publication, also run `tests/check_herdr.py` for real rendering, focus,
Settings, lifecycle and multiple-machine behavior, and `tests/check_managed_upgrade.py`
for actual installation, upgrades, local links and durable storage. The release script
runs all three. Integration needs Unix sockets and PTYs; never weaken checks or
substitute passing placeholders.

## Official identity and local development

Keep ID `c0r0nell.agents-sidebar` and name `Agents Sidebar` stable. Local and managed
installations use the same manifest; do not create development aliases or identities.
For a requested local installation, use
`herdr plugin link "$PWD/herdr-plugin.toml" --enabled`.
Source changes require Restart sidebar; linking does not hot-reload Python workers.
Settings changes apply live.

Test GitHub updates on a separate machine. Managed updates follow upstream commits
and require user action; linked checkouts are excluded from update checks.
Publishing does not update or restart users' installations automatically.

## Storage and integration

Use `HERDR_PLUGIN_CONFIG_DIR` for preferences and `HERDR_PLUGIN_STATE_DIR` for state.
Direct CLI defaults derive XDG/Home paths from the official ID; ignore inherited
paths belonging to other plugins. Never hardcode this developer's paths.

Keep state outside every checkout: installer source replacement ignores Git exclusions.
Preserve preferences, schema versions, ownership receipts, installation UUID and
recovery records through updates, reinstall and local/managed transitions.
Use private permissions (directories 0700, files 0600), atomic writes, bounded locks
and migrations that reject ambiguous conflicts. Preserve later user config edits.

Herdr owns identities, lifecycle, ordering, machines and sessions. Scope identities
by machine, session, workspace and pane. Use documented APIs; never rename agents,
assume authority over their state, or read credentials or conversation histories.
Active changes presentation only; users select native Grouped/Priority separately.
Never read private client preferences to synchronize ordering. Keep Priority rows
self-contained and preserve native ordering configuration.

Metadata keys are server-global: scope wire keys with the durable installation UUID,
keeping logical fields and the official metadata source stable. Publish/clear only
this installation's tokens. Settings saves and worker refresh share the operation
lock; workers skip busy refreshes so pause and cleanup cannot deadlock.
Reject another plugin's active projection or conflicting layout before replacing it.
Disable/remove must clear owned tokens and restore owned config without overwriting
later edits or disturbing other plugins.

## Validation boundaries

Start integration in disposable named sessions with separate temporary config and
state roots. Preserve the main server, projects, bindings and existing plugins.
Do not change SSH profiles, install remotely or restart the main server for testing.
Activate/install in a user's environment only within the authorized scope.
Source inspection alone does not prove visual or remote behavior.
Record actual investigations in `docs/solutions/`; keep history out of this file.

## Before every commit to main

1. Read the manifest version; review `git diff`, `git diff --cached`, untracked files
   and their actual contents. Determine scope from the full changes.
2. Propose a specific `MAJOR.MINOR.PATCH`, naming the current/proposed versions and
   behavior/compatibility reason. Wait for agreement: permission to commit does not
   approve an unstated version. Documentation/test-only maintenance may retain the
   version with an explanation.
3. Apply the agreed version and matching changelog, verify the changes, and review
   the final staged diff. Stage only intended files; exclude private state.

Use semantic versioning: patch for fixes, minor for compatible features, major for
stable breaking contracts. Before 1.0, breaking changes need a minor bump and explicit
release notes. Use the highest required bump and group related edits before publishing.
Never amend published commits or tags.

## Commit and release pipeline

Use English Conventional Commits: `<type>(<scope>): <summary>`, optional scope,
`!` for breaking changes. Types: feat, fix, docs, style, refactor, perf, test, build,
ci, chore, revert. Describe resulting behavior, not just a version.

Read [docs/publishing.md](docs/publishing.md) before release. Write notes once under
`## X.Y.Z - YYYY-MM-DD` in `CHANGELOG.md`: newest version matches the manifest,
valid dates/unique versions, nonempty English bullets covering everything since the
previous published tag. Human review checks accuracy; tooling validates structure.

After version agreement and publication authorization, stage reviewed files and run:
`python3 scripts/release.py --version X.Y.Z --subject '<type>(<scope>): <summary>'`.
One invocation validates, runs all checks, commits, pushes main and its annotated tag
atomically, and publishes the GitHub Release. Commit and release bodies reuse the
exact matching notes. Do not replace this pipeline with separate commands.
The script does not choose versions, edit notes, stage files or assume approval.
Preview with `--dry-run`; it performs no writes or network access.

If push/release fails after committing, preserve the commit and retry the exact same
version/subject. Never replace conflicting remote history, tags or releases.
There is no automatic release CI. Normal installation needs no GitHub CLI login.
Contributors submit PRs; publication requires main and repository write access.
Requested documentation/test-only maintenance without a release may use a normal
commit and push after version review. Do not commit, push, create a remote or publish without a request.
