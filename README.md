# Gramps Illness Plugin

Plugin that filters an genealogy tree for medical use and outputs it as pdf/graphviz/png/svg

## Status

This repository currently only contains a **dummy report** (`illness_report.py` /
`illness_report.gpr.py`). It does not implement any of the filtering or graph
generation described below yet. Its only purpose is to verify that the plugin
is registered correctly and shows up under **Reports > Graphs** in Gramps.

## Installation (development)

Gramps loads plugins from its user plugin directory, which on Linux is
typically:

```
~/.local/share/gramps/gramps<version>/plugins/
```

(e.g. `~/.local/share/gramps/gramps60/plugins/` for Gramps 6.0). You can find
the exact path for your installation by checking `gramps.gen.const.USER_PLUGINS`
or via *Help > About* in Gramps.

Gramps scans this directory recursively for `*.gpr.py` files, but it does
**not** follow symlinked directories. To develop against this repository
without copying files on every change, create a real directory inside the
plugins folder and symlink the individual files into it:

```sh
mkdir -p ~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin
ln -s /path/to/Gramps-Illness-Plugin/illness_report.py \
      ~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin/illness_report.py
ln -s /path/to/Gramps-Illness-Plugin/illness_report.gpr.py \
      ~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin/illness_report.gpr.py
```

Then (re)start Gramps. The dummy report appears under
**Reports > Graphs > Illness Report (Dummy)**.

Note: `illness_report.gpr.py` declares `gramps_target_version`, which must
match the major.minor version of your Gramps installation (e.g. `"6.0"`) or
the plugin will be ignored.

## Translations

The menu entry (name/description) follows Gramps' UI language. Translations
are stored as gettext catalogs, the same mechanism Gramps itself uses for
addons:

- `po/addon.pot` - template with all translatable strings
- `po/<lang>.po` - human-editable translation (e.g. `po/de.po`)
- `locale/<lang>/LC_MESSAGES/addon.mo` - compiled catalog Gramps actually reads

If Gramps has no translation for the active language, it falls back to the
original English string.

To add or update a translation:

```sh
# (re)extract translatable strings after changing illness_report*.py
xgettext --language=Python --from-code=UTF-8 --keyword=_ \
  -o po/addon.pot illness_report.gpr.py illness_report.py

# create a new language file, e.g. French
msginit --input=po/addon.pot --locale=fr --output=po/fr.po

# after editing po/<lang>.po, compile it
mkdir -p locale/<lang>/LC_MESSAGES
msgfmt po/<lang>.po -o locale/<lang>/LC_MESSAGES/addon.mo
```

When developing with the symlink setup above, also symlink the `locale`
directory into the plugin folder:

```sh
ln -s /path/to/Gramps-Illness-Plugin/locale \
      ~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin/locale
```

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