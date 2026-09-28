"""
Dummy report for the Illness Plugin.

This is a minimal, working Graphviz report that only draws a single
placeholder node. Its only purpose is to prove that the plugin loads
correctly and shows up under Reports > Graphs in Gramps, before any of
the real filtering/graph-generation logic is written.
"""

from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions


class IllnessReport(Report):
    """Minimal report that draws a single placeholder node."""

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)

    def write_report(self):
        self.doc.add_node("dummy", "Illness Plugin\\n(placeholder report)")


class IllnessReportOptions(MenuReportOptions):
    """No options yet - this will grow once the real report is implemented."""

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        pass
