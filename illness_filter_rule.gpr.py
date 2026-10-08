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
# Plugin registration file.
#
from gramps.gen.plug._pluginreg import *

# Note: do not define our own `_` here. When a `locale/` directory sits
# next to this file, Gramps automatically injects a translator (with a
# fallback chain: this plugin's own catalog -> Gramps' catalog -> the
# original string) as `_` before executing this file. Defining `_`
# ourselves would silently discard that and break translations.
# See gramps.gen.plug._pluginreg.PluginRegister.scan_dir().

# Must match the major.minor version of the Gramps installation this
# plugin is loaded into (e.g. "6.0" for Gramps 6.0.x).
MODULE_VERSION = "6.0"

plg = newplugin()
plg.id = "illness_filter_rule"
plg.name = _("Medically relevant people")
plg.description = _(
    "Person filter rule that matches the people medically relevant to a "
    "chosen person: their ancestors, the siblings and children of those "
    "ancestors, and the chosen person's own descendants. A ready-to-use "
    "filter based on it, named after the tree's Home Person, is available "
    "immediately in every Person filter list once a Home Person is set; "
    "build a custom filter from this rule in the Filter Editor instead if "
    "you want a different person or generation depth."
)
plg.version = "0.3.0"
plg.gramps_target_version = MODULE_VERSION
plg.status = STABLE
plg.fname = "illness_filter_rule.py"
plg.ptype = RULE
plg.authors = ["moonyGopher"]
plg.authors_email = ["88974951+moonyGopher@users.noreply.github.com"]
plg.ruleclass = "IsMedicallyRelevantTo"
plg.namespace = "Person"

# Also contribute a ready-made filter for the tree's Home Person, built
# from the rule above, directly into every Person filter list, via Gramps'
# "Filters" general-plugin data pathway (see
# gramps.gen.filters._filterlist.FilterList.get_filters()). This is what
# makes the filter selectable immediately, without the user having to
# build a custom filter from the rule by hand first.
plg = newplugin()
plg.id = "illness_filter_builtin_filter"
plg.name = _("Medically relevant people (built-in filter)")
plg.description = _(
    "Contributes a ready-to-use 'Medically relevant people of <Home "
    "Person's name>' entry to every Person filter list, built from the "
    "'Medically relevant people' rule."
)
plg.version = "0.3.0"
plg.gramps_target_version = MODULE_VERSION
plg.status = STABLE
plg.fname = "illness_filter_rule.py"
plg.ptype = GENERAL
plg.category = "Filters"
plg.load_on_reg = True
plg.authors = ["moonyGopher"]
plg.authors_email = ["88974951+moonyGopher@users.noreply.github.com"]
