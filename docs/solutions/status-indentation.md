# Native indicator indentation

Observed in a user screenshot on 2026-10-11 with Herdr 0.9.3.

## Cause

The native agent renderer indents an entry's first visible row by one cell and
subsequent rows by three cells. With the native status token before the custom
label, agents without headings placed their indicator two cells to the left.
Padding the label aligned only the text, leaving the indicator displaced.
The original visual check stripped whitespace before comparing the icon, which
failed to detect its inconsistent column.

## Correction

Place a blank-only `has_agent_prefix` before `state_icon`, followed by the plain
`has_agent` name. Prefix lengths of two cells with headings and four without
headings compensate the native offsets. Every native icon stays at column 8,
and every name at column 10; project names remain at column 3. No `>` is added.

Herdr inserts ` · ` between the blank token and its native icon. On 2026-10-11
the user first requested removing the dot as well as the markers. That left
icons at native columns 3 and 1 while names aligned. A fresh two-server terminal
check reproduced the two displaced icons. After reviewing an isolated
blank-prefix alternative, the user explicitly accepted the inline dot for
aligned icons. The optional machine separator remains independent.

The public API offers no indentation or separator override to remove that dot
while keeping icons aligned. Preserve native state and colors rather than
copying state, adding blank rows or modifying Herdr. Existing prefix tokens
containing `>` are replaced with blanks during reconciliation; owned cleanup
still removes the whole token on disable or agent removal.

## Regression checks

An exact-column assertion first reproduced the old leading-icon shift in a real
isolated terminal. `tests/test_layout.py` covers headings and subsequent agents.
`tests/check_visual.py` checks exact aligned icon/name columns, absence of `>`
markers, the accepted native dot, clipping at 18/22/36 columns, and real
idle/working/blocked fixture changes without republishing display tokens.
Unit checks cover replacement of old visible markers and owned prefix cleanup.
