# Gramps Illness Plugin

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Gramps addon that filters a genealogy tree down to the people medically
relevant to a chosen person. The filtering logic is registered as a Gramps
Person filter rule, so it plugs into Gramps' own Filter Editor and, from
there, into any export - GEDCOM, so the filtered family tree can be opened
in any GEDCOM-aware tool, or this plugin's own **GraphML (yEd)** export,
which additionally styles each person for
[yEd](https://www.yworks.com/products/yed) (rounded/bordeaux boxes for
women, square/navy boxes for men, bold names, birth/death/illness rows).

## Status

- `illness_filter.py` implements the filtering: given a "me" person, it
  returns the set of blood relatives that are medically relevant (ancestors,
  their siblings and children, and me's own descendants), excluding anyone
  only related by marriage. See "Filtering" below.
- `illness_filter_rule.py` / `illness_filter_rule.gpr.py` wrap that filter as
  a Gramps Person filter rule, **"People medically relevant to \<person\>"**,
  under the **Family filters** category in the Filter Editor, and also
  contribute a ready-made filter for the tree's Home Person, e.g.
  **"Medically relevant people of John Doe"**, directly to every Person
  filter list - no manual setup required (beyond setting a Home Person, if
  the tree doesn't have one yet). See "Using the filter rule" below.
- `illness_graphml.py` / `illness_graphml.gpr.py` add a **GraphML (yEd)**
  entry to **File > Export...**, which applies whatever Person filter is
  picked there (e.g. the one above) and writes the result as a styled
  GraphML file. See "Exporting to GraphML (yEd)" below.

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

## Using the filter rule

Once installed and a **Home Person** is set for the tree (**Edit > Set Home
Person**, if not already done), a filter named after that person - e.g.
**"Medically relevant people of John Doe"** - is already selectable wherever
Gramps lists Person filters, the same way Gramps' own built-in "Ancestors of
\<person\>"/"Descendants of \<person\>" export filters are. No manual setup
needed; if no Home Person is set, the entry simply doesn't appear (rather
than appearing and matching nobody).

To export only those people: **File > Export...**, choose **GEDCOM** (or
**GraphML (yEd)**, see below), and pick that filter in the export options'
"Filter" dropdown. A GEDCOM export's `.ged` file contains just the filtered
people (ancestors/descendants/siblings of the Home Person, 3 generations
each way) and can be opened in yEd (or any other GEDCOM-aware tool) for
layout and drawing.

To use a different center person, or a different generation depth, build
your own filter from the underlying rule instead:

1. Open **Edit > Person Filter Editor** (or the filter sidebar's "Edit"
   button in the People view).
2. Create a new filter, choose rule category **Family filters**, and add
   **People medically relevant to \<person\>**.
3. Fill in the person's Gramps ID (and, optionally, how many generations of
   ancestors/descendants to include - both default to 3 if left blank), then
   save the filter under a name of your choice. It then shows up in the same
   "Filter" dropdown as the ready-made one above.

## Exporting to GraphML (yEd)

**File > Export...** also offers **GraphML (yEd)** as a format, alongside
GEDCOM. Its **Options** page has the same privacy/living/filter controls
every Gramps export has - including the "Filter" dropdown to apply the
ready-made filter, a custom one built from the rule, or none ("Include all
selected people") - plus one extra checkbox, **"Show relationship instead
of name"**, which labels each box with its relationship to the Home Person
(e.g. "Mother", "Cousin", computed with Gramps' own relationship calculator,
so it follows Gramps' UI language) instead of their name. It then writes
everyone left as a `.graphml` file that opens directly in yEd, pre-styled to
match the conventions worked out by hand in `test/testdata/TestTree.graphml`:

- Female persons get rounded-corner boxes with a bordeaux border; male
  persons get square-corner boxes with a navy border. Every box is filled
  white.
- Each box shows the person's name (or relationship, see above) in bold,
  centered at the top; birth date (bottom-left) and death date
  (bottom-right, same row); cause of death directly below the death date
  (same column); and a bulleted illness list (oldest first, below that) -
  each row only appears if the corresponding Gramps event exists ("Cause of
  Death"/"Medical Information" events; see `illness_graphml._build_rows`).
- Each family is drawn as a small point that every parent connects into and
  every child connects out of (a "bracket"), rather than a separate line
  from every parent to every child.
- People are arranged generation by generation, oldest at the top, as a
  starting layout - not a final one. This export does not try to minimize
  line crossings; use yEd's own layout tools (**Layout > Tree**, etc.)
  afterward the same way you would for any other yEd diagram.

## Installation

Gramps loads plugins from its user plugin directory, which on Linux is
typically:

```
~/.local/share/gramps/gramps<version>/plugins/
```

(e.g. `~/.local/share/gramps/gramps60/plugins/` for Gramps 6.0; on Windows
it's typically `%USERPROFILE%\AppData\Roaming\gramps\gramps<version>\plugins\`,
on macOS `~/Library/Application Support/gramps/gramps<version>/plugins/`).
You can find the exact path for your installation by checking
`gramps.gen.const.USER_PLUGINS` or via *Help > About* in Gramps.

**Easiest:** go to this repository's **Releases** page, download
`GrampsIllnessPlugin.zip` from the latest release, and extract it - the zip
already contains just the files Gramps needs, bundled into a single
`GrampsIllnessPlugin` folder, so there's no picking individual files. Move
that folder into your Gramps user plugin directory, then (re)start Gramps.

To track the latest `main` branch instead of a release:

1. Download this repository - either `git clone` its URL (the one shown
   under GitHub's green **Code** button), or use **Code > Download ZIP** on
   GitHub and extract it - to any folder on your computer.
2. Create a new folder for the plugin inside your Gramps user plugin
   directory (e.g. `GrampsIllnessPlugin`) and copy these files into it:
   `illness_filter.py`, `illness_filter_rule.py`,
   `illness_filter_rule.gpr.py`, `illness_graphml.py`,
   `illness_graphml.gpr.py`, and the `locale/` folder (for translated
   labels; optional, but needed for anything other than English).
3. (Re)start Gramps.

The filter rule and its ready-made filter are now available wherever Gramps
lists Person filters (see "Using the filter rule" below), and **GraphML
(yEd)** appears as a format under **File > Export...** (see "Exporting to
GraphML (yEd)" below).

Note: `illness_filter_rule.gpr.py` and `illness_graphml.gpr.py` declare
`gramps_target_version`, which must match the major.minor version of your
Gramps installation (e.g. `"6.0"`) or the plugin will be ignored - edit that
line in both files if you're on a different version.

To update later, replace the copied files with the newer versions the same
way.

## Installation (development)

Gramps scans the plugin directory recursively for `*.gpr.py` files, but it
does **not** follow symlinked directories. To develop against this
repository without copying files on every change, create a real directory
inside the plugins folder and symlink the individual files into it instead
of copying them:

```sh
mkdir -p ~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin
for f in illness_filter.py illness_filter_rule.py illness_filter_rule.gpr.py \
         illness_graphml.py illness_graphml.gpr.py; do
    ln -s "/path/to/Gramps-Illness-Plugin/$f" \
          "~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin/$f"
done
```

Then (re)start Gramps - see "Installation" above for what to expect to show
up, and the `gramps_target_version` compatibility note.

## Translations

The filter's labels and description follow Gramps' UI language. Translations
are stored as gettext catalogs, the same mechanism Gramps itself uses for
addons:

- `po/addon.pot` - template with all translatable strings
- `po/<lang>.po` - human-editable translation (e.g. `po/de.po`)
- `locale/<lang>/LC_MESSAGES/addon.mo` - compiled catalog Gramps actually reads

If Gramps has no translation for the active language, it falls back to the
original English string.

To add or update a translation:

```sh
# (re)extract translatable strings after changing illness_filter_rule*.py / illness_graphml.gpr.py
xgettext --language=Python --from-code=UTF-8 --keyword=_ \
  -o po/addon.pot illness_filter_rule.gpr.py illness_filter_rule.py illness_graphml.gpr.py

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
python3 -m unittest discover -s test -p "test_*.py" -v
black --check --diff .
mypy illness_filter.py illness_filter_rule.py illness_graphml.py test/
```
