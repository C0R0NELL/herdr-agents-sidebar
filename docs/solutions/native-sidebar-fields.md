# Native pane, state and terminal details

Validated on 2026-10-12 with Herdr 0.9.3, protocol 22, in isolated local/remote
sessions. The [native row contract](https://herdr.dev/docs/configuration/#sidebar-row-layouts)
provides `pane`, `state_text`, `terminal_title` and `terminal_title_stripped`.
`pane` uses Herdr's reported metadata title when present, otherwise the manual
pane label, independently of agent name and tab label. Terminal titles
are supplied by the terminal program; the clean title removes one recognized
leading activity glyph. These fields do not describe an inferred task or read chats.

Use native tokens directly, preserving missing-value handling, live rename/title
updates, semantic state and focus. No new plugin-owned metadata keys are needed.
Grouped exposes one ordered line with fixed machine/project headings; Priority
exposes two. Both use the same field labels, draft editing and field colors.
The new fields start Hidden, with Default resolving to Dark blue. The existing
factory views, activation and saved profiles stay unchanged.

Schema 5 stores Grouped `line1` instead of its two presets. Schemas 1–4 remain
readable; Agent and Agent/Tab migrate to the same native field order. Loading
does not rewrite settings, and old runtimes reject schema 5 without overwriting it.

`tests/check_herdr.py::check_native_fields` uses native pane renames and controlled
OSC titles, verifies raw/clean text, per-field colors, cancel/save, remote focus,
and a blank row before Save. Popup option lists scroll to protect the footer at
short heights; the manifest requests 24 rows for the complete editor.
