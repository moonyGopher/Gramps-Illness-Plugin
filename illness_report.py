"""
Illness report: draws a Graphviz genogram of the people who are medically
relevant to a chosen center person (see illness_filter.py / illness_graph.py
for the filtering and label logic this only renders).

Female persons get boxes with rounded corners, male persons plain boxes.
Each person's name is bold, birth/death stay centered, and the illness list
below them is set off with extra spacing and aligned to the reading
direction (see _dot_label).

Each family is connected as a bracket, not as separate lines from every
parent to every child (see README.md's "Example view"): a two-parent
couple is joined by one small invisible point between them, and multiple
children hang off a chain of invisible points forming a horizontal bus one
rank below - so each child has exactly one line tracing back to one shared
point, and it's never ambiguous which parents a child belongs to. Building
this out of nodes that are each other's *only* neighbor (rather than one
point wired directly to everyone) is what keeps Graphviz from bending the
connecting lines into visually crossing curves.
"""

import html

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import ReportError
from gramps.gen.plug.menu import BooleanOption, NumberOption, PersonOption
from gramps.gen.plug.report import MenuReportOptions, Report, stdoptions
from gramps.gen.relationship import get_relationship_calculator

from illness_filter import DEFAULT_ANCESTOR_GENERATIONS, DEFAULT_DESCENDANT_GENERATIONS
from illness_graph import build_graph_data

_ = glocale.get_addon_translator(__file__).gettext


class IllnessReport(Report):
    """Draws the illness graph for the chosen center person."""

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        menu = options.menu

        self.set_locale(menu.get_option_by_name("trans").get_value())
        stdoptions.run_name_format_option(self, menu)

        pid = menu.get_option_by_name("pid").get_value()
        self.center_person = database.get_person_from_gramps_id(pid)
        if self.center_person is None:
            raise ReportError(_("Person %s is not in the Database") % pid)

        self.ancestor_generations = menu.get_option_by_name("ancestor_generations").get_value()
        self.descendant_generations = menu.get_option_by_name("descendant_generations").get_value()
        self.use_relationship_labels = menu.get_option_by_name("use_relationship_labels").get_value()
        self.relationship_calculator = get_relationship_calculator(clocale=self._locale)

    def write_report(self):
        graph = build_graph_data(
            self.database,
            self.center_person,
            self._get_date,
            self._name_display,
            self.relationship_calculator,
            _("Me"),
            ancestor_generations=self.ancestor_generations,
            descendant_generations=self.descendant_generations,
            use_relationship_labels=self.use_relationship_labels,
        )

        rtl = self._locale.rtl_locale
        for handle, node in graph.nodes.items():
            self.doc.add_node(
                self._gramps_id(handle),
                _dot_label(node.label, node.centered_line_count, rtl),
                shape="box",
                style="rounded" if node.rounded else "solid",
                htmloutput=True,
            )

        # Chain each generation's people together left-to-right (in the
        # birthdate/couple order computed by build_graph_data) with
        # invisible edges, and pin them to the same rank. This keeps
        # siblings sorted by age and couples adjacent, which Graphviz's
        # own crossing-reduction heuristic would otherwise not respect.
        for _generation, handles in graph.generation_order:
            ids = [self._gramps_id(handle) for handle in handles]
            for first_id, second_id in zip(ids, ids[1:]):
                self.doc.add_link(first_id, second_id, style="invis")
                self.doc.add_samerank(first_id, second_id)

        for link in graph.family_links:
            self._draw_family_link(link)

    def _draw_family_link(self, link):
        """
        Connect a family as a bracket: a shared point between two parents
        (if there are two), feeding into a chain of points - one per child -
        that forms a horizontal bus one rank above the children. Every edge
        here connects two nodes that share no other edge between them, which
        is what keeps Graphviz from bending them into curves (see the
        module docstring).
        """
        base_id = f"family-{link.family_handle}"

        if len(link.parent_handles) == 2:
            parents_id = f"{base_id}-parents"
            self.doc.add_node(parents_id, "", shape="point", style="invis")
            first_parent_id = self._gramps_id(link.parent_handles[0])
            second_parent_id = self._gramps_id(link.parent_handles[1])
            self.doc.add_link(first_parent_id, parents_id, head="none", tail="none")
            self.doc.add_link(parents_id, second_parent_id, head="none", tail="none")
            self.doc.add_samerank(first_parent_id, parents_id)
            self.doc.add_samerank(parents_id, second_parent_id)
            top_id = parents_id
        else:
            top_id = self._gramps_id(link.parent_handles[0])

        if len(link.child_handles) == 1:
            self.doc.add_link(top_id, self._gramps_id(link.child_handles[0]), head="none", tail="none")
            return

        drop_ids = [f"{base_id}-drop-{index}" for index in range(len(link.child_handles))]
        for drop_id in drop_ids:
            self.doc.add_node(drop_id, "", shape="point", style="invis")
        for first_drop_id, second_drop_id in zip(drop_ids, drop_ids[1:]):
            self.doc.add_link(first_drop_id, second_drop_id, head="none", tail="none")
            self.doc.add_samerank(first_drop_id, second_drop_id)
        for drop_id, child_handle in zip(drop_ids, link.child_handles):
            self.doc.add_link(drop_id, self._gramps_id(child_handle), head="none", tail="none")

        middle_drop_id = drop_ids[len(drop_ids) // 2]
        self.doc.add_link(top_id, middle_drop_id, head="none", tail="none")

    def _gramps_id(self, handle):
        return self.database.get_person_from_handle(handle).get_gramps_id()


def _dot_label(label, centered_line_count, rtl):
    """
    Build a Graphviz HTML-like label from `label` (see PersonNode.label):
    the name (the first line) is bold; the rest of the header
    (`centered_line_count` lines total - name, birth, death) stays
    centered; the illness list after that is set off with extra vertical
    spacing and aligned to the reading direction (left for LTR languages,
    right for RTL) instead of Graphviz's default centering, which reads
    poorly for a bullet list.
    """
    align = "RIGHT" if rtl else "LEFT"
    lines = [html.escape(line) for line in label.split("\n")]
    lines[0] = f"<B>{lines[0]}</B>"

    parts = []
    for index, line in enumerate(lines):
        if index < centered_line_count:
            parts.append(f"{line}<BR/>")
        else:
            if index == centered_line_count:
                parts.append("<BR/>")  # extra gap between the header and the illness list
            parts.append(f'{line}<BR ALIGN="{align}"/>')
    return "".join(parts)


class IllnessReportOptions(MenuReportOptions):
    """Options for the illness report."""

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        category_name = _("Report Options")

        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the graph. Defaults to the Home Person set in Gramps."))
        menu.add_option(category_name, "pid", pid)

        ancestor_generations = NumberOption(_("Generations of ancestors"), DEFAULT_ANCESTOR_GENERATIONS, 0, 15)
        ancestor_generations.set_help(
            _("The number of generations of ancestors (and their siblings and children) to include.")
        )
        menu.add_option(category_name, "ancestor_generations", ancestor_generations)

        descendant_generations = NumberOption(_("Generations of descendants"), DEFAULT_DESCENDANT_GENERATIONS, 0, 15)
        descendant_generations.set_help(
            _(
                "The number of generations of descendants to include, both for the center "
                "person and for collateral relatives (aunts/uncles/cousins, ...)."
            )
        )
        menu.add_option(category_name, "descendant_generations", descendant_generations)

        use_relationship_labels = BooleanOption(_("Show relationship instead of name"), False)
        use_relationship_labels.set_help(
            _(
                "Show each person's relationship to the center person (e.g. mother, uncle, "
                "cousin) instead of their name."
            )
        )
        menu.add_option(category_name, "use_relationship_labels", use_relationship_labels)

        ################################
        category_name = _("Report Options (2)")
        ################################

        stdoptions.add_name_format_option(menu, category_name)
        stdoptions.add_localization_option(menu, category_name)
