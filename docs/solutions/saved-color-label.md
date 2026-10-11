# A saved yellow appeared as a hexadecimal value

Investigated on 2026-10-11 after the user selected Yellow again.

The earlier saved machine color was `#f9e2af`. Settings currently offers
Dracula Yellow as `#f1fa8c`. `sidebar.display()` resolves color names by exact
value; other hexadecimal colors retain their value in the label. The chooser
always lists the current palette, so choosing Yellow replaces the older tone
with `#f1fa8c` and the label then resolves to Yellow.

A direct check reproduced `display('#f9e2af') == '#f9e2af'` and confirmed
`display('#f1fa8c') == 'Yellow'`. The saved preferences after the user's selection
contained `#f1fa8c`, displayed as Yellow. This behavior did not require a cache
reset. No runtime or preference changes were made during the investigation;
custom colors must remain exact instead of silently changing to a named palette.
