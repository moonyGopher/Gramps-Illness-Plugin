# Gramps Illnes Plugin

Plugin that filters an genealogy tree for medical use and outputs it as pdf/graphviz/png/svg

Data which should be shown in the Graph:
- Birthdate
- Deathdate
- Case of Death
- Desisess / Illnesses with date

- Graph should use the language used by gramps.
- Me (the central person) should be the one set by gramps
- the box for females should have roundet corners
- the boxes for males have normal corners
- use symbols for birth and death
- it should be selectible wether to print the names of the persons or the position (me, child, uncle, sister, grandmother, ...) instead of the names
- the lines in the graph should not cross eachother
- the lines in the graph should all be orthogonal
- the Persons of one generation (me, sisters, brothers) in the graph should be sorted by birthdate if possible, do not cross lines
- the plugin should be found unter diagrams in graph after installation



## Example view

-----------------------------------     -----------------------------------
| Mother                          |     | Father                          |
| * 03.03.1960                    |     | *                               |
| +                               |     | +                               |
-----------------------------------     -----------------------------------
                |                                       |
                -----------------------------------------
                                     |
                -----------------------------------------
                |                                       |
-----------------------------------     -----------------------------------
| Me                               |    | Brother                         |
| * 01.01.1990                     |    | *                               |
| +                                |    | +                               |
|                                  |    -----------------------------------
| - MyFirstIllness (since  2000)   |
| - MySecondIllness (2001)         |
-----------------------------------