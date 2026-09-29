#
# Gramps Illness Plugin
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
plg.id = "illness_report"
plg.name = _("Illness Report")
plg.description = _(
    "Draws a genogram-style graph of the family members who are medically "
    "relevant to a chosen person: ancestors, their siblings and children, "
    "and that person's own descendants, showing birth/death dates, cause "
    "of death, and recorded illnesses."
)
plg.version = "0.2.0"
plg.gramps_target_version = MODULE_VERSION
plg.status = STABLE
plg.fname = "illness_report.py"
plg.ptype = REPORT
plg.authors = ["moonyGopher"]
plg.authors_email = ["88974951+moonyGopher@users.noreply.github.com"]
plg.category = CATEGORY_GRAPHVIZ
plg.reportclass = "IllnessReport"
plg.optionclass = "IllnessReportOptions"
plg.report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
