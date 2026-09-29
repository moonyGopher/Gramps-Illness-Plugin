# Gramps Illness Plugin

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Gramps report plugin that filters a genealogy tree for medical use and draws it as a Graphviz graph (pdf/png/svg/...).

## Status
g
- `illness_filter.py` implements the filtering: given a "me" person, it
  returns the set of blood relatives that are medically relevant (ancestors,
  their siblings and children, and me's own descendants), excluding anyone
  only related by marriage. See "Filtering" below.
- `illness_graph.py` turns that filtered set into graph data (node labels,
  parent-child edges, couples, generation ordering), independent of
  Graphviz, so it can be unit tested without running a report. See "Graph
  generation" below.
- `illness_report.py` / `illness_report.gpr.py` is the real report: it
  renders `illness_graph`'s output as a Graphviz genogram and shows up
  under **Reports > Graphs** in Gramps.

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

## Graph generation

The report draws one box per person returned by the filter above:

- **Label**: by default the person's display name; the "Show relationship
  instead of name" option shows their relationship to the center person
  (e.g. "Mother", "Cousin") instead, computed with Gramps' own relationship
  calculator so it also follows Gramps' UI language.
- **Birth/death**: shown with Gramps' genealogical symbols, using
  Gramps' own locale-aware date formatting (so a "from"/"about" date
  modifier is rendered the way Gramps normally renders it, in Gramps' UI
  language).
- **Cause of death**: shown next to the death date if a "Cause Of Death"
  event is recorded.
- **Illnesses**: every "Medical Information" event is listed with its date,
  oldest first.
- **Shape**: female persons get rounded box corners, male persons plain
  ones.
- Each family connects as a bracket rather than as separate lines from
  every parent to every child: a two-parent couple converges into one
  shared point, which then diverges into every child, so it's never
  ambiguous which parents a child belongs to. Every one of these lines
  attaches to a person at a fixed side - the top for a line to an ancestor,
  the bottom for a line to a descendant - and lines sharing a point are
  pinned to its exact same spot (via Graphviz's samehead/sametail) rather
  than each getting an independently-computed, slightly-offset spot, which
  otherwise leaves a visible sliver of a gap. People are also grouped and
  ordered generation by generation (oldest generation first, each
  generation's blood siblings kept together and sorted by birthdate, with
  a person's own block oriented towards an external partner's block so a
  couple's connecting line doesn't have to reach across the whole block) to
  keep siblings in age order and reduce line crossings. See
  `illness_report._draw_family_link`/`_write_line` and
  `illness_graph._order_generation` for why this needs more than just
  "draw a line from parent to child".
- **Connecting lines are always orthogonal** (routed at right angles
  around boxes instead of diagonally through them) - this report registers
  its own fixed "Connecting lines" option ahead of the "Graphviz Layout"
  one Gramps adds to every Graphviz report, so that option only ever
  offers Orthogonal here. (Gramps still shows its own copy of that control
  under "Graphviz Layout" for every Graphviz report; changing it there has
  no effect on this one.)

The center person, ancestor/descendant generation depth, and the
name/relationship toggle are all report options; the center person option
defaults to Gramps' Home Person when left unset. See `test/README.md` and
`test/test_graph_generation.py` for a fully worked example.

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
for f in illness_filter.py illness_graph.py illness_report.py illness_report.gpr.py; do
    ln -s "/path/to/Gramps-Illness-Plugin/$f" \
          "~/.local/share/gramps/gramps60/plugins/GrampsIllnessPlugin/$f"
done
```

Then (re)start Gramps. The report appears under
**Reports > Graphs > Illness Report**.

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
python3 -m unittest discover -s test -p "test_*.py" -v
black --check --diff .
mypy illness_filter.py illness_graph.py illness_report.py test/
```

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