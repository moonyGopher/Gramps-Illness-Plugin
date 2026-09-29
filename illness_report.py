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
couple converges into one small invisible point below them, which then
diverges into every child - so each child has exactly one line tracing
back to one shared point, and it's never ambiguous which parents a child
belongs to (see _draw_family_link for why these points must each sit on
their own rank rather than share one with the people beside them).

Every one of those lines attaches to a person at a fixed side - the top
for a line leading to an ancestor, the bottom for a line leading to a
descendant - and lines sharing an invisible point are pinned to the exact
same spot on it via Graphviz's samehead/sametail, rather than each getting
its own slightly-offset spot (which otherwise leaves a visible sliver of a
gap). Neither compass-point sides nor samehead/sametail are exposed by
Gramps' own add_link/add_node helpers, so _write_line bypasses them and
writes these specific lines directly (see also _draw_family_link).
"""

import html

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import ReportError
from gramps.gen.plug.menu import BooleanOption, EnumeratedListOption, NumberOption, PersonOption
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
        Connect a family as a bracket: parents converge into one shared
        point (if there are two of them), which then diverges into every
        child. A point never shares a rank with the people it connects to:
        pinning it to the *same* rank as neighbouring people still keeps
        the minimum node spacing ("nodesep") between them, which shows up
        as a visible gap in the line; a point on its own rank has no such
        neighbor, so lines through it stay seamless.

        The connector from the parents is given weight=0 so it doesn't
        pull the children-point away from being centered among the
        (equally-weighted) lines to the children - otherwise Graphviz
        places the point wherever minimizes total edge bend across *all*
        of its lines, which usually isn't the midpoint of the children.

        Every line into a parent attaches at that parent's south (bottom)
        side and every line into a child at that child's north (top) side.
        Lines sharing a point as their head, or as their tail, are grouped
        with samehead/sametail so Graphviz anchors them all at its exact
        same spot instead of computing a slightly different one for each
        (see _write_edges).
        """
        base_id = f"family-{link.family_handle}"
        edges = []  # (source_id, target_id, source_port, target_port, weight)

        if len(link.parent_handles) == 2:
            parents_id = f"{base_id}-parents"
            self.doc.add_node(parents_id, "", shape="point", style="invis")
            for parent_handle in link.parent_handles:
                edges.append((self._gramps_id(parent_handle), parents_id, "s", None, 1))
            top_id, top_port = parents_id, None
        else:
            top_id, top_port = self._gramps_id(link.parent_handles[0]), "s"

        if len(link.child_handles) == 1:
            edges.append((top_id, self._gramps_id(link.child_handles[0]), top_port, "n", 1))
            self._write_edges(edges)
            return

        children_id = f"{base_id}-children"
        self.doc.add_node(children_id, "", shape="point", style="invis")
        edges.append((top_id, children_id, top_port, None, 0))
        for child_handle in link.child_handles:
            edges.append((children_id, self._gramps_id(child_handle), None, "n", 1))

        self._write_edges(edges)

    def _write_edges(self, edges):
        """
        Write plain (no-arrowhead) connecting lines, grouping any edges
        that share a head (target) or a tail (source) node with
        samehead/sametail so Graphviz anchors them all at its exact same
        spot rather than computing a slightly different one for each
        (see _write_line).
        """
        head_counts = {}
        tail_counts = {}
        for source, target, _, _, _ in edges:
            head_counts[target] = head_counts.get(target, 0) + 1
            tail_counts[source] = tail_counts.get(source, 0) + 1

        for source, target, source_port, target_port, weight in edges:
            samehead = f"{target}-head" if head_counts[target] > 1 else None
            sametail = f"{source}-tail" if tail_counts[source] > 1 else None
            self._write_line(
                source,
                target,
                port1=source_port,
                port2=target_port,
                samehead=samehead,
                sametail=sametail,
                weight=weight,
            )

    def _write_line(self, id1, id2, port1=None, port2=None, samehead=None, sametail=None, weight=None):
        """
        Write a single plain connecting line directly to the Graphviz
        output, bypassing self.doc.add_link: it has no way to request a
        compass-point port (":n"/":s", to force which side of a box a line
        attaches to), the samehead/sametail attributes (to force multiple
        lines meeting at one point to share its exact anchor - without
        them, Graphviz computes each line's endpoint independently, which
        can leave a visible sliver of a gap), or a custom edge weight (to
        control how much a line's pull influences an invisible point's
        position).
        """
        ref1 = _node_ref(id1, port1)
        ref2 = _node_ref(id2, port2)
        attrs = ["arrowhead=none", "arrowtail=none", "dir=both"]
        if samehead:
            attrs.append(f'samehead="{samehead}"')
        if sametail:
            attrs.append(f'sametail="{sametail}"')
        if weight is not None:
            attrs.append(f"weight={weight}")
        self.doc.write(f"  {ref1} -> {ref2} [ {' '.join(attrs)} ];\n")

    def _gramps_id(self, handle):
        return self.database.get_person_from_handle(handle).get_gramps_id()


def _node_ref(node_id, port=None):
    ref = '"{}"'.format(node_id.replace('"', '\\"'))
    if port:
        ref += f":{port}"
    return ref


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

        # Gramps adds its own "Connecting lines" choice (straight/curved/
        # orthogonal) to every Graphviz report under "Graphviz Layout", with
        # "Curved" as the default. This report only ever looks right with
        # orthogonal routing (see the module docstring and README.md's
        # "Graph generation" section), so it registers its own "spline"
        # option here, before that shared one is added. Since both end up
        # under the same name in the same menu and lookups return the first
        # match, this one wins for actually building the graph - the later,
        # still-visible "Graphviz Layout" control has no effect.
        spline = EnumeratedListOption(_("Connecting lines"), "ortho")
        spline.add_item("ortho", _("Orthogonal"))
        spline.set_help(
            _(
                "This report always uses orthogonal connecting lines: they route around "
                "boxes instead of through them, which avoids ambiguous-looking crossings "
                "in family connections."
            )
        )
        menu.add_option(category_name, "spline", spline)

        ################################
        category_name = _("Report Options (2)")
        ################################

        stdoptions.add_name_format_option(menu, category_name)
        stdoptions.add_localization_option(menu, category_name)
