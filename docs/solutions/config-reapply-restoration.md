# Preserve later user edits through presentation changes

Investigated on 2026-10-11 while introducing visual Mode selection.

The ownership receipt stores original and installed configuration text. If a
user changed an unrelated setting and then the plugin reapplied its own rows,
the new installed text included that edit but the original text still referred
to the first activation. Restoring an unchanged installed file could therefore
replace the later user edit with the old original.

A failing regression changed native order after activation, switched Mode and
then restored the presentation. The user's order was lost. Reapplication now
rebases the restoration text using source-owned fields only, preserving other
edits before recording the next installed version. Exact original bytes are
still restored when there were no later edits.

`tests/test_configuration.py` checks native order edits, legacy 0.1.0 ownership
receipts, an unrelated toast setting, mode changes, validation failures and
disable restoration using temporary files only. Native order is no longer
written or checked by new applications; legacy receipts remain restorable.
