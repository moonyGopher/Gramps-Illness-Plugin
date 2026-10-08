# Gramps Illness Plugin

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![License: GPL v2 or later](https://img.shields.io/badge/license-GPL--2.0--or--later-blue.svg)](LICENSE)

Gramps addon that filters a family tree down to the people medically
relevant to a chosen person, then lets you export that selection as GEDCOM
or as a styled [GraphML](https://www.yworks.com/products/yed) file for yEd
(rounded bordeaux boxes for women, square navy boxes for men, bold names,
birth/death/illness rows).

## Installation

**Easiest:** download `GrampsIllnessPlugin.zip` from this repository's
**Releases** page, extract it, and move the resulting `GrampsIllnessPlugin`
folder into your Gramps user plugin directory - typically
`~/.local/share/gramps/gramps<version>/plugins/` on Linux (see
`gramps.gen.const.USER_PLUGINS` or *Help > About* in Gramps for the exact
path on your system). Then (re)start Gramps.

To track `main` instead of a release: clone or download this repository and
copy `illness_filter.py`, `illness_filter_rule.py`, `illness_filter_rule.gpr.py`,
`illness_graphml.py`, `illness_graphml.gpr.py`, and the `locale/` folder into
a new folder inside your Gramps plugin directory instead.

Note: both `.gpr.py` files declare `gramps_target_version`, which must match
your Gramps version (e.g. `"6.0"`) or the plugin is ignored.

## Usage

Once installed and a **Home Person** is set for the tree (**Edit > Set Home
Person**), a filter named after that person - e.g. **"Medically relevant
people of John Doe"** - is already selectable wherever Gramps lists Person
filters (it won't appear at all without a Home Person). To use a different
person or generation depth instead, add the underlying rule, **"People
medically relevant to \<person\>"**, to a custom filter via **Edit > Person
Filter Editor** (category **Family filters**).

To export just those people: **File > Export...**, choose **GEDCOM** or
**GraphML (yEd)**, and pick the filter in the Options page. GraphML export
also offers a **"Show relationship instead of name"** checkbox (labels boxes
"Mother", "Cousin", etc. instead of names) and lays people out generation by
generation as a starting point - use yEd's own layout tools to refine it.

## Filtering rules

`illness_filter.filter_relevant_people(database, me, ancestor_generations=3, descendant_generations=3)`
includes: `me`'s direct ancestors, the siblings (and their descendants) of
every ancestor along the way, and `me`'s own descendants - excluding anyone
only connected by marriage. See `test/README.md` for a fully worked example.

## Development

```sh
python3 -m unittest discover -s test -p "test_*.py" -v   # tests
black --check --diff .                                    # formatting (line length 120)
mypy illness_filter.py illness_filter_rule.py illness_graphml.py test/   # types
```

All three also run in CI (`.github/workflows/ci.yml`) on every push/PR;
`.github/workflows/package.yml` builds the Release zip mentioned above.

Translations are gettext catalogs (`po/addon.pot`, `po/<lang>.po`, compiled
to `locale/<lang>/LC_MESSAGES/addon.mo`) - the same mechanism Gramps itself
uses for addons, falling back to English where untranslated:

```sh
xgettext --language=Python --from-code=UTF-8 --keyword=_ \
  -o po/addon.pot illness_filter_rule.gpr.py illness_filter_rule.py illness_graphml.gpr.py illness_graphml.py
msginit --input=po/addon.pot --locale=fr --output=po/fr.po   # new language
msgfmt po/fr.po -o locale/fr/LC_MESSAGES/addon.mo             # after editing po/fr.po
```

For local development without copying files on every change, symlink the
individual files (Gramps doesn't follow symlinked directories) plus
`locale/` into a folder under your Gramps plugin directory instead of
copying them.

## License

GPL-2.0-or-later, matching Gramps itself (this plugin directly imports and
extends Gramps' own GPL-licensed classes). See [LICENSE](LICENSE).
