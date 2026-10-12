# Grouped indentation limits

Investigated on 2026-10-12 with real Herdr 0.9.3 rendering in a disposable session.
The [native renderer](https://github.com/herdrdev/herdr/blob/v0.9.3/src/client/shell/agent_sidebar.rs#L345)
fixes the first rendered row at column 1 and continuation rows at column 3.
The [token separator](https://github.com/herdrdev/herdr/blob/v0.9.3/src/ui/sidebar/tokens.rs#L171)
inserts ` · ` after a custom spacer. Neither exposes a configurable indent.

With the default Status/Agent line, measured name columns (zero-based) were:

| Prefix policy | First agent | Next agent | Next project |
| --- | --- | --- | --- |
| Current: 2/4 U+2800 cells | 10 | 10 | 10 |
| Minimum nonempty aligned prefix: 1/3 cells | 9 | 9 | 9 |
| No prefix | 5 | 3 | 5 |

Removing one cell from each prefix saves one column and preserves native icon/name
alignment. Removing the prefix entirely misaligns both icons and names. Project
headings stay at column 3; one-space indentation per level cannot be represented
by these public row controls. The comparison did not change the user's session or
the runtime's current padding. Keep any chosen change confined to Grouped.
