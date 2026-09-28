# Gramps Illness Plugin

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Plugin that filters an genealogy tree for medical use and outputs it as pdf/graphviz/png/svg

## Status

- `illness_filter.py` implements the filtering: given a "me" person, it
  returns the set of blood relatives that are medically relevant (ancestors,
  their siblings and children, and me's own descendants), excluding anyone
  only related by marriage. See "Filtering" below.
- `illness_report.py` / `illness_report.gpr.py` is still a **dummy report**.
  It does not use the filter yet and only draws a single placeholder node.
  Its purpose is to verify that the plugin is registered correctly and
  shows up under **Reports > Graphs** in Gramps. Wiring the filter into an
  actual graph is still to do.

## Filtering

`illness_filter.filter_relevant_people(database, me, ancestor_generations=3, descendant_generations=3)`
returns the set of person handles relevant to `me` (a Person or a handle):

- direct ancestors (parents, grandparents, ...), up to `ancestor_generations`
  levels (both parents of an ancestor are included)
- at every one of those levels, including me's own, the siblings of that
  generation's blood relative (aunts/uncles, or me's own siblings), plus
  their descendants (cousins, ...) up to `descendant_generations` levels
- me's own descendants (children, grandchildren, ...), up to
  `descendant_generations` levels

Anyone only connected by marriage (spouses/in-laws) is excluded, even when
their blood-relative partner is included. See `test/README.md` and
`test/test_filter.py` for a fully worked example.

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

## Development

CI (`.github/workflows/ci.yml`) runs the tests, [black](https://github.com/psf/black)
(line length 120, see `pyproject.toml`) and [mypy](https://mypy-lang.org/) on
every push/PR. To run the same checks locally (in a venv with access to the
system Gramps install, e.g. `python3 -m venv --system-site-packages .venv`):

```sh
python3 -m unittest test.test_filter -v
black --check --diff .
mypy illness_filter.py illness_report.py test/
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