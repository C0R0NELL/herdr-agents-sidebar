# Publishing Agents Sidebar

The source repository is [C0R0NELL/herdr-agents-sidebar](https://github.com/C0R0NELL/herdr-agents-sidebar).
The user approved the initial version `0.1.0` and authorized public GitHub
publication on 2026-10-11. Future releases require their own approval.

The official identity remains `c0r0nell.agents-sidebar` / **Agents Sidebar** for
both local links and GitHub installations. The manifest includes the validated runtime
actions, startup hooks and settings popup; Linux is the tested platform.

## Verification before publication

The runtime under [specs.md](../specs.md), isolated visual proof, multiple-machine
behavior, restoration and managed upgrades have been validated. Results and limits
are recorded in [viabilidade.md](viabilidade.md). Test the plugin in the intended
user environment before approving a release. Herdr `0.9.3` is the tested minimum;
older versions are not claimed. The repository includes an MIT license.

Keep `sidebar.py`, `tests/check_herdr.py`, and `tests/check_managed_upgrade.py`
available and passing. The release helper blocks publication when they are missing
or fail. Do not replace them with no-op scripts or weaken the gate to hide missing
verification. Integration checks cover lifecycle, durable preferences/recovery
records and real focus/rendering in isolated sessions.

## One-command release workflow

The maintainer needs Python 3.11+, Git, and authenticated GitHub CLI (`gh`) with
write permission. Configure `origin` to the intended GitHub repository after its
creation is authorized. Fetch/push URLs must point to the same repository. Human
version approval and publication authorization remain required under [AGENTS.md](../AGENTS.md).

1. Review the actual diff and agree on a semantic version. Update
   `herdr-plugin.toml` and the newest `CHANGELOG.md` heading to that version.
   Use `## X.Y.Z - YYYY-MM-DD` and nonempty English bullet notes, covering all
   changes since the last published tag. For the first release, describe the
   complete delivered behavior and its tested limitations.
2. Review the notes and intended files. Optionally preview:

   ```sh
   python3 scripts/release.py --dry-run --version X.Y.Z --subject 'feat(sidebar): describe the delivered behavior'
   ```

   The preview reads local files only. Stage only reviewed files; the script
   never stages or rewrites them.
3. Once release is authorized, call:

   ```sh
   python3 scripts/release.py --version X.Y.Z --subject 'feat(sidebar): describe the delivered behavior'
   ```

   One call validates the staged version, changelog, subject, exclusions, source,
   integration check availability, GitHub prerequisites, and history. It runs
   `tests/check.py`, `tests/check_herdr.py`, and `tests/check_managed_upgrade.py`,
   creates the commit, pushes main and its annotated tag atomically without force,
   and creates the GitHub Release. The commit subject is the supplied Conventional
   Commit; both its body and the release body use the exact matching changelog notes.

The script supports the initial commit on an empty main branch. Mismatches stop
before committing. The helper extracts notes; it does not summarize commits,
judge note accuracy, or choose a version. Its credential-pattern checks supplement
manual review and `.gitignore`; they are not proof that arbitrary content is safe.

Push and GitHub Release creation are separate external operations. If a later
step fails, preserve any created commit and retry the exact same invocation.
Matching published releases are a no-op. Existing conflicting tags/releases are
not moved or replaced. There is no release CI; execution is explicitly local.
Documentation/test-only maintenance requested without publication may use a
normal commit and push after the mandatory version review. Contributors without
write permission submit a pull request; the helper does not publish from a PR
branch or apply an owner-specific whitelist.

## Herdr distribution

For marketplace discovery, Herdr requires a public GitHub repository with the
`herdr-plugin` topic and a parseable official manifest on its default branch.
The index refreshes automatically; release creation by itself does not list a
private repository. See the [marketplace documentation](https://herdr.dev/docs/marketplace/).

Normal users install from the public GitHub source through Herdr, without the
release script or GitHub CLI authentication. The [Plugin Manager](https://github.com/speardragon/herdr-plugin-manager)
compares the installed commit with its requested upstream ref and displays the
remote manifest version when available. Users explicitly apply updates; linked
checkouts are excluded. Publishing does not restart users' running plugin processes.

Keep configuration and state outside the installed source directories, following
the [Herdr plugin contract](https://herdr.dev/docs/plugins/#commands-and-environment).
Uninstall/reinstall and source replacement must preserve these private records.
