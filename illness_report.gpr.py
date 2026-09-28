#
# Gramps Illness Plugin
#
# Plugin registration file.
#
# This currently registers only a dummy placeholder report so that the
# plugin's integration into Gramps (menu placement, loading, etc.) can be
# verified before the real report logic is implemented.
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
plg.name = _("Illness Report (Dummy)")
plg.description = _(
    "Placeholder report used to verify that the Illness Plugin is "
    "correctly registered and appears under Reports > Graphs. "
    "Does not yet produce any real output."
)
plg.version = "0.1.0"
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
