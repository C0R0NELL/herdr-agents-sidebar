# Working in this repository

Read [specs.md](specs.md) before implementation. It defines the user's sidebar
behavior and boundaries. The runtime and settings are implemented
and tested in isolated Herdr sessions. The user authorized local activation on
2026-10-10; the main environment now links this checkout using the official ID.
The user approved version `0.1.0` and authorized public GitHub publication on
2026-10-11. Review the evidence before expanding the tested behavior claims.

Keep plugin code and user-facing documentation in English. Preserve the original
specification in Portuguese. Prefer Python's standard library and a small number
of modules. Use `sidebar.py` as the runtime entrypoint; add modules only
when they hide meaningful responsibilities. This repository's `scripts/release.py`
is publication tooling, not the plugin runtime.

## Repository layout and checks

- `herdr-plugin.toml`: the only official manifest, including the stable identity.
- `sidebar.py`: runtime entrypoint and settings popup.
- `layout.py`: pure native identity/grouping and incremental token patches.
- `configuration.py`: durable preferences and reversible config ownership.
- `runtime.py`: public API transports, workers and lifecycle.
- `tests/`: all tests and check entrypoints. Run `python3 -B tests/check.py`.
  Unit checks exercise grouping, configuration and release tooling in temporary
  repositories, without accessing the user's credentials or live Herdr session.
- `scripts/`: repository tooling. `release.py` is the single release command.
- `docs/`: development, publishing, and evidence. Record investigated runtime
  issues in `docs/solutions/` when actual implementation investigations occur.
- `specs.md`: the agreed requirements; do not silently reduce their scope.
- `CHANGELOG.md`: dated, versioned notes for publication.

Before publication, run `tests/check_herdr.py` for actual isolated rendering,
focus, settings, lifecycle and multiple-machine checks, and
`tests/check_managed_upgrade.py` for the real installer with a temporary local
Git URL rewrite, upgrades, local links and durable storage. Test dependencies
are listed in `tests/requirements.txt`. These checks require Unix sockets and
PTYs; never replace failures with passing placeholders or use the main server.

## One official identity

Keep ID `c0r0nell.agents-sidebar` and name `Agents Sidebar` stable. Use the same
official manifest when editing locally and when installing from GitHub. Do not
create a second ID, display name, generated manifest, or alias for development.

For a requested local installation, link the
checkout with `herdr plugin link "$PWD/herdr-plugin.toml" --enabled`. This machine
then consumes the editable source directly. Reload behavior depends on the
runtime: use the plugin's Restart sidebar action after source changes; linking
does not hot-reload Python processes. Settings changes are applied live.

Test normal GitHub updates on a separate machine. Update availability follows the
installed Git ref's upstream commit. The Plugin Manager may show the remote
manifest version; locally linked checkouts are excluded from update checks.
Publishing does not apply updates to a user's installed plugin automatically.

## Durable storage and safe integration

Use `HERDR_PLUGIN_CONFIG_DIR` for preferences and `HERDR_PLUGIN_STATE_DIR` for
plugin-owned state. If direct CLI invocation needs defaults, derive XDG/Home
paths from the stable official ID. Never hardcode this developer's username or
repository location. Ignore inherited host paths from unrelated plugins.

Keep all runtime state and configuration outside every source checkout. Git ignore
rules do not preserve files when an installer removes source files. Preserve
preferences, schema versions, ownership receipts, and necessary recovery records
through updates, uninstall/reinstall, and local/managed installation transitions.
Use atomic writes, bounded locks, and migrations that reject ambiguous conflicts.
Never silently overwrite the user's later configuration changes.

Herdr owns agent identities, lifecycle state, order, machines, and sessions.
Settings' Active control changes presentation only. Users choose Grouped/Priority in Herdr
separately; never synchronize by reading private client preferences. Preserve
native ordering configuration and keep Priority rows self-contained.
Use only documented APIs. Scope identities by machine, session, workspace, and
pane. Publish only this plugin's tokens; never rename agents or assume authority
over their state. Detect another plugin's active projection before replacing it.
Do not read agent credentials or conversation histories. Follow the spec's cleanup
requirements when disabled or removed.

Start all integration work in disposable named sessions with separate temporary
configuration and state roots. Preserve the main server, projects, bindings, and
existing plugins. Local activation was explicitly authorized; installation in
another environment requires a user request. Do not change SSH profiles, install remotely, or restart the main server
as part of testing. Review [docs/viabilidade.md](docs/viabilidade.md) before claiming
the native grouping works; source inspection is not a visual or remote test.

## Mandatory before every commit to main

1. Read the current manifest version. Review `git diff`, `git diff --cached`,
   untracked files, and their actual contents; on an unborn branch the intended
   initial files are all untracked. Base scope and version on the actual changes.
2. Propose a specific `MAJOR.MINOR.PATCH` version to the user, stating the current
   version, proposed version, and the behavior/compatibility reason. The initial
   version `0.1.0` was approved on 2026-10-11; later releases require new agreement.
   Documentation/test-only maintenance can keep the current version; explain why.
3. Wait for agreement. Permission to commit is not approval of an unstated version.
4. Apply the agreed version, synchronize the changelog, run required checks, and
   review the final staged diff. Stage only intended files; keep private state out.

Use semantic versioning: patch for fixes, minor for compatible features, major
for stable breaking contracts. Before 1.0, breaking changes require a minor bump
and explicit release notes. Use the highest required bump in a mixed release.
Group related local edits before publication. Never amend published commits/tags.

## Commit messages and release pipeline

Write subjects and bodies in English with Conventional Commits:
`<type>(<scope>): <summary>`. Scope is optional; use `!` for breaking changes.
Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`,
`chore`, or `revert`. Describe resulting behavior rather than only a version.

For a release, write notes once under `## X.Y.Z - YYYY-MM-DD` in `CHANGELOG.md`.
The newest entry must match the official manifest; dates and versions must be valid,
versions unique, and notes nonempty English bullets. Cover the entire change since
the previous published tag, including previously committed work. Human review
checks scope, accuracy, wording, and version choice; the script only validates
structure and executes the reviewed pipeline.

After explicit version and publication approval, review and stage intended files,
then call `python3 scripts/release.py --version X.Y.Z --subject
'<type>(<scope>): <summary>'`. One invocation validates, runs repository and real
integration checks, commits, pushes main and the annotated version tag atomically,
and publishes a GitHub Release. Its body and the commit body reuse the exact
matching changelog notes. Do not replace this with separate commit/push/release
commands or stop after the local commit.

The script never chooses a version, edits notes, stages files, or assumes approval.
It rejects mismatches, missing implementation/checks, private files, dirty state,
invalid subjects, changed files during checks, and conflicting remote history,
tags, or releases. It supports the initial release of an empty repository.
Preview with `--dry-run`; that does not write or access the network.

If push or release creation fails after a commit, preserve that commit and retry
the exact same version/subject. Matching published releases are not duplicated;
conflicting tags or descriptions are never replaced. No automatic release CI is
configured. Ordinary installation will not require GitHub CLI authentication.

Documentation/test-only maintenance explicitly requested without a release may use
a normal Conventional Commit and push after version review. Contributors can send
pull requests; publication requires main and write access to the GitHub repository,
not a hardcoded owner check. Do not commit, push, create a remote, or publish until
the user requests it. Review [docs/publishing.md](docs/publishing.md) before release.
