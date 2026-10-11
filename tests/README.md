# Checks

`python3 -B tests/check.py` runs grouping, config/ownership and publication tests
using temporary files and fictitious local Git repositories. It does not control
Herdr or contact GitHub/provider APIs.

For integration checks, install `tests/requirements.txt` in an isolated Python
environment. `check_herdr.py` uses real Herdr servers, PTYs and a local SSH shim
under temporary XDG roots. It checks the runtime, settings popup, native renderer,
mouse routing and cleanup. `check_visual.py` can additionally export the actual
captured cells with `--evidence docs/evidence/native-sidebar.json`.

`check_managed_upgrade.py` uses Herdr's actual installer with a temporary Git URL
rewrite to a local bare repository. It checks managed updates, uninstall and local
links while preserving preferences outside source checkouts.

No integration check uses the user's main server, SSH profiles, projects, agent
credentials or conversation history. Unix socket/PTY permission is required.
