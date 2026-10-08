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
plg.id = "illness_export_graphml"
plg.name = _("GraphML (yEd)")
plg.name_accell = _("Graph_ML (yEd)")
plg.description = _(
    "Exports the people selected by the chosen export filter as a GraphML "
    "file, ready to open and lay out in yEd: female persons get "
    "rounded-corner, bordeaux-bordered boxes, male persons square-corner, "
    "navy-bordered ones, each showing the person's name (bold), birth/death "
    "dates, cause of death, and recorded illnesses. Families are drawn as a "
    "shared connecting point between parents and children, and people are "
    "arranged generation by generation as a starting layout to refine in "
    "yEd."
)
plg.version = "0.4.0"
plg.gramps_target_version = MODULE_VERSION
plg.status = STABLE
plg.fname = "illness_graphml.py"
plg.ptype = EXPORT
plg.export_function = "export_data"
plg.export_options = "GraphMLWriterOptionBox"
plg.export_options_title = _("GraphML (yEd) export options")
plg.extension = "graphml"
plg.authors = ["moonyGopher"]
plg.authors_email = ["88974951+moonyGopher@users.noreply.github.com"]
