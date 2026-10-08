#
# Gramps Illness Plugin
#
# Copyright (C) 2026  moonyGopher
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Gramps Person filter rule wrapping illness_filter.filter_relevant_people().

Registering the filtering logic as a rule (rather than as a report or a
standalone export plugin) lets it plug into Gramps' own tools: it shows up
in the Filter Editor like any built-in rule, and a custom filter built from
it can then be picked in the "Filter" dropdown of any export - including
GEDCOM, so the selected people can be opened and laid out in a dedicated
tool such as yED.

`make_filters`/`load_on_reg` additionally contribute a ready-made filter for
the tree's current Home Person directly into every Person filter list - see
illness_filter_rule.gpr.py's second plugin entry - so it's already
selectable wherever a Person filter is, named after that person (e.g.
"Medically relevant people of <Name>", the same naming convention Gramps'
own built-in "Ancestors of <Name>"/"Descendants of <Name>" export filters
use), with no manual Filter Editor step needed. It isn't offered at all
until a Home Person is set (Edit > Set Home Person).
"""

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.filters import GenericFilterFactory
from gramps.gen.filters.rules import Rule

from illness_filter import DEFAULT_ANCESTOR_GENERATIONS, DEFAULT_DESCENDANT_GENERATIONS, filter_relevant_people

_ = glocale.get_addon_translator(__file__).gettext

# Captured from load_on_reg() below so make_filters() can look up the
# current tree's Home Person: Gramps' "Filters" general-plugin data pathway
# only ever calls make_filters(namespace), with no database access of its
# own. Holding the DbState object itself (not a snapshot of its .db
# attribute) keeps this correct across switching to a different family
# tree, since Gramps updates DbState.db in place on the same instance.
_dbstate = None


class IsMedicallyRelevantTo(Rule):
    """Matches the people medically relevant to a chosen person (see illness_filter.py)."""

    labels = [_("ID:"), _("Generations of ancestors:"), _("Generations of descendants:")]
    name = _("People medically relevant to <person>")
    category = _("Family filters")
    description = _(
        "Matches a chosen person's ancestors, the siblings and children of those ancestors, "
        "and the chosen person's own descendants, excluding anyone only related by marriage."
    )

    def prepare(self, db, user):
        # A blank ID (as used by the ready-made filter from make_filters()
        # below) falls back to the Home Person, the same default the old
        # report used for its center-person option.
        person = db.get_person_from_gramps_id(self.list[0]) if self.list[0] else db.get_default_person()
        if person is None:
            self.selected_handles = set()
            return
        ancestor_generations = _parse_generations(self.list[1], DEFAULT_ANCESTOR_GENERATIONS)
        descendant_generations = _parse_generations(self.list[2], DEFAULT_DESCENDANT_GENERATIONS)
        self.selected_handles = filter_relevant_people(db, person, ancestor_generations, descendant_generations)

    def reset(self):
        self.selected_handles = set()

    def apply_to_one(self, db, person):
        return person.handle in self.selected_handles


def _parse_generations(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def make_filters(namespace):
    """
    Build a ready-made filter for the current tree's Home Person, for
    `namespace`, or None if this plugin has nothing to contribute (wrong
    namespace, no tree open, or no Home Person set - matching how Gramps'
    own built-in "Ancestors of <person>"/etc. export filters are likewise
    omitted when there's no person to build them from).

    Rebuilt on every lookup (Gramps calls this each time a Person filter
    list is shown) instead of being saved to disk, so it always reflects
    the current Home Person and never needs manual upkeep.
    """
    if namespace != "Person" or _dbstate is None or not _dbstate.is_open():
        return None
    home_person = _dbstate.db.get_default_person()
    if home_person is None:
        return None

    name = name_displayer.display(home_person)
    person_filter = GenericFilterFactory("Person")()
    person_filter.set_name(_("Medically relevant people of %s") % name)
    person_filter.add_rule(IsMedicallyRelevantTo([home_person.get_gramps_id(), "", ""]))
    return person_filter


def load_on_reg(dbstate, uistate, plugin):
    """Gramps plugin-loading hook: capture `dbstate` and hand `make_filters` to the "Filters" pathway."""
    global _dbstate
    _dbstate = dbstate
    return [make_filters]
