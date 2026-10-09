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
GraphML (yEd) export: writes the people surviving the active export filter
(typically illness_filter_rule.py's ready-made "Medically relevant people of
<Home Person>" filter, or a custom filter built from its "People medically
relevant to <person>" rule) as a GraphML file that opens directly in yEd,
following the layout conventions worked out by hand in
test/testdata/TestTree.graphml:

- Female persons get rounded-corner boxes with a bordeaux border; male
  persons get square-corner boxes with a navy border. Every box is filled
  white. See _person_shape().
- Every box is the same width - just wide enough for the single widest name
  among the people included, so every name fits on its own one line - but
  each is only as tall as the rows it actually has. See
  _compute_box_width()/_box_height().
- Each box's name is bold and centered at the top. Birth date (bottom-left)
  and death date (bottom-right, sharing the birth row) follow, then cause of
  death directly below the death date (same, right-aligned column, and as
  close under it as consecutive illness lines are to each other), then a
  bulleted illness list (left-aligned; dated ones oldest first, then any
  undated ones alphabetically) - each row is only added if the data exists.
  See _build_rows()/_Row.
- Every row is positioned as a fixed pixel offset from the box's own top
  edge (via nodeRatioY=-0.5/labelRatioY=-0.5, i.e. "anchor at the top edge,
  then place the label's own top edge `offset` pixels down"), not as a
  fraction of the box's height - so the same row layout looks right
  regardless of how tall any individual box ends up. See _node_label_xml().
- Each family is drawn as a small point node that every parent connects
  into and every child connects out of (a "bracket"), rather than a
  separate line from every parent to every child - the same convention the
  deleted Graphviz-based report used, and the one already used by hand in
  the reference file. See _build_family_links()/_write_family_node().
- People are arranged generation by generation (oldest at the top), each
  generation's people left-to-right by birth date. This is a reasonable
  starting layout, not a final one - yEd's own layout tools (Layout > Tree,
  etc.) can tidy up crossing lines from here same as with any other yEd
  diagram; this export does not attempt to minimize crossings itself.

Unlike a real yEd GEDCOM import, this does not also attach the raw GEDCOM
fields as separate, inspectable node properties - only the rendered labels
above, since that's the only thing anyone has asked this export to show.
"""

import html

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.lib import EventType, Person
from gramps.gen.relationship import get_relationship_calculator
from gramps.gui.plug.export import WriterOptionBox

_ = glocale.get_addon_translator(__file__).gettext

_BIRTH_SYMBOL = "*"
_DEATH_SYMBOL = "✝"  # latin cross, Gramps' own default death symbol

_FEMALE_BORDER_COLOR = "#800020"  # Bordeaux/Weinrot
_MALE_BORDER_COLOR = "#000080"  # Navy/Dunkelblau
_FILL_COLOR = "#FFFFFF"

_BOX_MIN_WIDTH = 200.0  # every box uses the same width - this, or wider if some name needs it (see _compute_box_width)
_CHAR_WIDTH_ESTIMATE = 6.05  # px/char for Dialog 11pt, calibrated against the reference file
_SIDE_MARGIN = 10.0
_LEFT_MARGIN = 5.78  # calibrated from the reference file's left-aligned rows

_NAME_ROW_Y = 4.0
_LINE_HEIGHT = 17.0  # one line of Dialog 11pt text, as laid out by yEd
_ROW_GAP_AFTER_NAME = 2.4  # gap observed between the end of the name block and the next row
_ROW_GAP = 12.0  # gap between any two stacked content rows below the name
_TIGHT_ROW_GAP = 0.0  # gap before the cause-of-death row: as tight as the gap between illness lines
_DATE_ROW_WIDTH = 100.0
_DATE_ROW_HEIGHT = 20.0
_TEXT_ROW_PADDING = 4.0  # autoSizePolicy="content" box padding, calibrated from the reference
_TEXT_LINE_HEIGHT = 14.98  # additional height per extra line in a content-sized row
_BOTTOM_MARGIN = 10.0

_GENERATION_ROW_HEIGHT = 180.0
_COLUMN_GAP = 40.0  # horizontal gap between boxes in the same generation, on top of box_width
_DOT_SIZE = 15.0


class _Row:
    """
    One row below the name: `cells` is a list of (text, align) pairs
    sharing that row (e.g. birth+death). `tight_gap_before`, if set, uses
    _TIGHT_ROW_GAP instead of _ROW_GAP before this row (see the
    cause-of-death row in _build_rows()).
    """

    def __init__(self, cells, is_date_row, tight_gap_before=False):
        self.cells = cells
        self.is_date_row = is_date_row
        self.tight_gap_before = tight_gap_before

    @property
    def height(self):
        if self.is_date_row:
            return _DATE_ROW_HEIGHT
        line_count = max(text.count("\n") + 1 for text, _align in self.cells)
        return _TEXT_ROW_PADDING + _TEXT_LINE_HEIGHT * line_count


def export_data(database, filename, user, option_box=None, callback=None):
    """
    Gramps EXPORT plugin entry point (see illness_graphml.gpr.py). Applies
    the user's chosen export filter (privacy/living/person/... - the same
    proxy chain GEDCOM export uses), then writes everyone left as GraphML.
    """
    use_relationship_labels = False
    if option_box:
        option_box.parse_options()
        database = option_box.get_filtered_database(database)
        use_relationship_labels = getattr(option_box, "use_relationship_labels", False)

    people = list(database.iter_people())
    document = _build_document(database, people, use_relationship_labels)

    with open(filename, "w", encoding="utf-8") as the_file:
        the_file.write(document)
    return True


def _build_document(database, people, use_relationship_labels=False):
    family_links = _build_family_links(database, people)
    generations = _compute_generations(people, family_links)

    # A relationship term ("Mother", "Cousin", ...) needs a person to be relative to; the tree's
    # Home Person is the natural choice, since it's also what the ready-made export filter uses.
    # Without one, there's nothing to compute a relationship against, so fall back to real names.
    home_person = database.get_default_person() if use_relationship_labels else None
    relationship_calculator = get_relationship_calculator() if home_person else None

    names_by_handle = {
        person.handle: _person_name_text(database, person, home_person, relationship_calculator) for person in people
    }
    box_width = _compute_box_width(names_by_handle.values())

    positions, family_positions = _compute_layout(database, people, generations, family_links, box_width)

    person_ids = {person.handle: f"n{index}" for index, person in enumerate(people)}
    family_ids = {link["family_handle"]: f"f{index}" for index, link in enumerate(family_links)}

    parts = [_HEADER]
    for person in people:
        parts.append(
            _write_person_node(
                database,
                person,
                person_ids[person.handle],
                positions[person.handle],
                names_by_handle[person.handle],
                box_width,
            )
        )
    for link in family_links:
        parts.append(_write_family_node(family_ids[link["family_handle"]], family_positions[link["family_handle"]]))
        parts.append(_write_family_edges(link, person_ids, family_ids[link["family_handle"]]))
    parts.append(_FOOTER)
    return "".join(parts)


def _person_name_text(database, person, home_person, relationship_calculator):
    """The name block's text (a single line): the real name, or - if enabled - the relationship to the Home Person."""
    if home_person is None:
        name = person.get_primary_name()
        given, surname = name.get_first_name(), name.get_surname()
        return f"{given} {surname}" if surname else given

    if person.handle == home_person.handle:
        return _("Me")
    return relationship_calculator.get_one_relationship(database, home_person, person) or _("Me")


# ---------------------------------------------------------------------------
# Family structure / generations / layout
# ---------------------------------------------------------------------------


def _build_family_links(database, people):
    """
    Return one entry per family that has at least one included parent and
    at least one included child, restricted to the included people (a
    parent or child outside the filtered set is dropped from that family's
    own lists, same as the deleted illness_graph.py did for the Graphviz
    report).
    """
    included = {person.handle for person in people}
    links = []
    seen_families = set()
    for person in people:
        family_handles = list(person.get_family_handle_list())
        parent_family_handle = person.get_main_parents_family_handle()
        if parent_family_handle:
            family_handles.append(parent_family_handle)
        for family_handle in family_handles:
            if family_handle in seen_families:
                continue
            seen_families.add(family_handle)
            family = database.get_family_from_handle(family_handle)
            if family is None:
                continue
            parent_handles = [
                handle
                for handle in (family.get_father_handle(), family.get_mother_handle())
                if handle and handle in included
            ]
            child_handles = [
                ref.get_reference_handle()
                for ref in family.get_child_ref_list()
                if ref.get_reference_handle() in included
            ]
            if parent_handles and child_handles:
                links.append({"family_handle": family_handle, "parents": parent_handles, "children": child_handles})
    return links


def _compute_generations(people, family_links):
    """
    Assign each person a generation number via the parent/child edges
    implied by family_links (parent = child's generation - 1), relative to
    an arbitrary starting person per connected component, then normalize so
    the oldest generation overall is 0.
    """
    neighbours = {person.handle: [] for person in people}
    for link in family_links:
        for parent_handle in link["parents"]:
            for child_handle in link["children"]:
                neighbours[parent_handle].append((child_handle, 1))
                neighbours[child_handle].append((parent_handle, -1))

    generation = {}
    for person in people:
        if person.handle in generation:
            continue
        generation[person.handle] = 0
        queue = [person.handle]
        while queue:
            current = queue.pop()
            for neighbour_handle, delta in neighbours[current]:
                if neighbour_handle not in generation:
                    generation[neighbour_handle] = generation[current] + delta
                    queue.append(neighbour_handle)

    minimum = min(generation.values(), default=0)
    return {handle: value - minimum for handle, value in generation.items()}


def _birth_sort_key(database, person):
    birth = _find_event(database, person, EventType.BIRTH)
    if birth is None:
        return (1, 0)
    return (0, birth.get_date_object().get_sort_value())


def _compute_layout(database, people, generations, family_links, box_width):
    by_generation: dict = {}
    for person in people:
        by_generation.setdefault(generations[person.handle], []).append(person)

    column_width = box_width + _COLUMN_GAP
    positions = {}
    for generation, generation_people in by_generation.items():
        generation_people.sort(key=lambda person: _birth_sort_key(database, person))
        for index, person in enumerate(generation_people):
            positions[person.handle] = (index * column_width, generation * _GENERATION_ROW_HEIGHT)

    family_positions = {}
    for link in family_links:
        child_xs = [positions[handle][0] for handle in link["children"]]
        parent_xs = [positions[handle][0] for handle in link["parents"]]
        x = sum(child_xs) / len(child_xs) if child_xs else sum(parent_xs) / len(parent_xs)
        parent_generation = min(generations[handle] for handle in link["parents"])
        child_generation = min(generations[handle] for handle in link["children"])
        y = (parent_generation + child_generation + 1) / 2 * _GENERATION_ROW_HEIGHT
        family_positions[link["family_handle"]] = (x + box_width / 2 - _DOT_SIZE / 2, y)

    return positions, family_positions


# ---------------------------------------------------------------------------
# Person node content
# ---------------------------------------------------------------------------


def _find_event(database, person, event_type):
    for event_ref in person.get_event_ref_list():
        event = database.get_event_from_handle(event_ref.ref)
        if event.get_type() == event_type:
            return event
    return None


def _find_cause_of_death(database, person):
    """
    Like _find_event(..., EventType.CAUSE_DEATH), but also matches a cause
    of death recorded as a custom "Cause Of Death" event type - which is
    what a person's cause-of-death event becomes after a round trip through
    GEDCOM (export turns it into a generic EVEN/TYPE pair, and re-importing
    that doesn't map it back to Gramps' own built-in CAUSE_DEATH type).
    """
    for event_ref in person.get_event_ref_list():
        event = database.get_event_from_handle(event_ref.ref)
        event_type = event.get_type()
        if event_type == EventType.CAUSE_DEATH or (event_type.is_custom() and event_type.string == "Cause Of Death"):
            return event
    return None


def _find_events(database, person, event_type):
    """
    Collect `person`'s events of `event_type`, dated ones first (oldest
    first), then undated ones alphabetically by description (there's no
    date to sort those by).
    """
    events = []
    for event_ref in person.get_event_ref_list():
        event = database.get_event_from_handle(event_ref.ref)
        if event.get_type() == event_type:
            events.append(event)
    events.sort(key=_event_sort_key)
    return events


def _event_sort_key(event):
    date_obj = event.get_date_object()
    if date_obj and not date_obj.is_empty():
        return (0, date_obj.get_sort_value(), "")
    return (1, 0, (event.get_description() or "").lower())


def _date_text(date_obj):
    """
    Format `date_obj` via Gramps' own date displayer, using whichever date
    format is currently configured (Edit > Preferences > Dates in Gramps) -
    deliberately not forcing a specific one: the exact format index for a
    given style (e.g. "numeric with leading zeros") isn't stable across
    locales, since the list of available formats is locale-specific.
    """
    if date_obj is None or date_obj.is_empty():
        return None
    return date_displayer.display(date_obj)


def _build_rows(database, person):
    """Return the _Row list to show below the name - birth/death, cause of death, illnesses - as present."""
    rows = []

    birth = _find_event(database, person, EventType.BIRTH)
    birth_text = _date_text(birth.get_date_object()) if birth else None
    death = _find_event(database, person, EventType.DEATH)
    death_text = _date_text(death.get_date_object()) if death else None
    date_cells = []
    if birth_text:
        date_cells.append((f"{_BIRTH_SYMBOL} {birth_text}", "left"))
    if death_text:
        date_cells.append((f"{_DEATH_SYMBOL} {death_text}", "right"))
    if date_cells:
        rows.append(_Row(date_cells, is_date_row=True))

    cause = _find_cause_of_death(database, person)
    if cause and cause.get_description():
        # Right-aligned, like the death date directly above it, so the cause reads as belonging to it;
        # tight_gap_before keeps it close under that date, as tight as consecutive illness lines are.
        rows.append(_Row([(f"({cause.get_description()})", "right")], is_date_row=False, tight_gap_before=True))

    illness_lines = []
    for illness in _find_events(database, person, EventType.MED_INFO):
        date_text = _date_text(illness.get_date_object())
        description = illness.get_description()
        illness_lines.append(f"- {description} ({date_text})" if date_text else f"- {description}")
    if illness_lines:
        rows.append(_Row([("\n".join(illness_lines), "left")], is_date_row=False))

    return rows


def _text_width(text):
    return max((len(line) for line in text.split("\n")), default=0) * _CHAR_WIDTH_ESTIMATE


def _compute_box_width(name_texts):
    """
    Every box uses this same width, computed once for the whole export:
    wide enough for the single widest name among the people included (so
    every name fits on its one line), or _BOX_MIN_WIDTH if that's already
    wide enough.
    """
    widest_name = max((_text_width(text) for text in name_texts), default=0.0)
    return max(_BOX_MIN_WIDTH, widest_name + _LEFT_MARGIN + _SIDE_MARGIN)


def _box_height(rows):
    rows_height = sum(row.height for row in rows)
    gaps = [_TIGHT_ROW_GAP if row.tight_gap_before else _ROW_GAP for row in rows[1:]]
    gaps_height = (_ROW_GAP_AFTER_NAME if rows else 0) + sum(gaps)
    height = _NAME_ROW_Y + _LINE_HEIGHT + gaps_height + rows_height + _BOTTOM_MARGIN
    return max(height, 70.0)


def _node_label_xml(text, align, width, height, is_bold, auto_size, y_offset):
    font_style = "bold" if is_bold else "plain"
    auto_size_policy = "content" if auto_size else "none"
    if align == "center":
        node_ratio_x, label_ratio_x, offset_x = 0.0, 0.0, 0.0
    elif align == "right":
        node_ratio_x, label_ratio_x, offset_x = 0.5, 0.5, -_LEFT_MARGIN
    else:
        node_ratio_x, label_ratio_x, offset_x = -0.5, -0.5, _LEFT_MARGIN

    escaped_text = html.escape(text).replace("\n", "&#10;")
    return (
        f'<y:NodeLabel alignment="{align}" autoSizePolicy="{auto_size_policy}" fontFamily="Dialog" fontSize="11" '
        f'fontStyle="{font_style}" hasBackgroundColor="false" hasLineColor="false" height="{height}" '
        f'horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" '
        f'verticalTextPosition="bottom" visible="true" width="{width}" x="0.0" xml:space="preserve" '
        f'y="{y_offset}">{escaped_text}'
        f'<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter>'
        f'<y:SmartNodeLabelModelParameter labelRatioX="{label_ratio_x}" labelRatioY="-0.5" '
        f'nodeRatioX="{node_ratio_x}" nodeRatioY="-0.5" offsetX="{offset_x}" offsetY="{y_offset}" '
        f'upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>'
    )


def _write_person_node(database, person, node_id, position, name_text, box_width):
    rows = _build_rows(database, person)
    height = _box_height(rows)
    is_female = person.get_gender() == Person.FEMALE
    border_color = _FEMALE_BORDER_COLOR if is_female else _MALE_BORDER_COLOR
    shape_type = "roundrectangle" if is_female else "rectangle"

    labels = [_node_label_xml(name_text, "center", box_width - 2 * _SIDE_MARGIN, _LINE_HEIGHT, True, True, _NAME_ROW_Y)]

    row_y = _NAME_ROW_Y + _LINE_HEIGHT + _ROW_GAP_AFTER_NAME
    for index, row in enumerate(rows):
        for text, align in row.cells:
            label_width = _DATE_ROW_WIDTH if row.is_date_row else _text_width(text) + 4.0
            labels.append(_node_label_xml(text, align, label_width, row.height, False, not row.is_date_row, row_y))
        if index + 1 < len(rows):
            gap = _TIGHT_ROW_GAP if rows[index + 1].tight_gap_before else _ROW_GAP
            row_y += row.height + gap

    x, y = position
    content = "".join(labels)
    return (
        f'<node id="{node_id}">\n'
        f'  <data key="d0">\n'
        f"    <y:ShapeNode>\n"
        f'      <y:Geometry height="{height}" width="{box_width}" x="{x}" y="{y}"/>\n'
        f'      <y:Fill color="{_FILL_COLOR}" transparent="false"/>\n'
        f'      <y:BorderStyle color="{border_color}" type="line" width="1.0"/>\n'
        f"      {content}\n"
        f'      <y:Shape type="{shape_type}"/>\n'
        f"    </y:ShapeNode>\n"
        f"  </data>\n"
        f"</node>\n"
    )


def _write_family_node(family_id, position):
    x, y = position
    return (
        f'<node id="{family_id}">\n'
        f'  <data key="d0">\n'
        f"    <y:ShapeNode>\n"
        f'      <y:Geometry height="{_DOT_SIZE}" width="{_DOT_SIZE}" x="{x}" y="{y}"/>\n'
        f'      <y:Fill color="#000000" transparent="false"/>\n'
        f'      <y:BorderStyle color="#000000" type="line" width="1.0"/>\n'
        f'      <y:Shape type="ellipse"/>\n'
        f"    </y:ShapeNode>\n"
        f"  </data>\n"
        f"</node>\n"
    )


def _write_family_edges(link, person_ids, family_id):
    edges = [(person_ids[handle], family_id) for handle in link["parents"]]
    edges += [(family_id, person_ids[handle]) for handle in link["children"]]
    return "".join(_plain_edge(source, target) for source, target in edges)


def _plain_edge(source_id, target_id):
    return (
        f'<edge source="{source_id}" target="{target_id}">\n'
        f'  <data key="d1">\n'
        f"    <y:PolyLineEdge>\n"
        f'      <y:LineStyle color="#000000" type="line" width="1.0"/>\n'
        f'      <y:Arrows source="none" target="none"/>\n'
        f'      <y:BendStyle smoothed="false"/>\n'
        f"    </y:PolyLineEdge>\n"
        f"  </data>\n"
        f"</edge>\n"
    )


class GraphMLWriterOptionBox(WriterOptionBox):
    """
    The options page for this export (see illness_graphml.gpr.py's
    export_options): the standard privacy/living/filter/reference/note
    options every Gramps export has (including the Person filter dropdown -
    this plugin's own ready-made filter or a custom one - and "Include all
    selected people" to ignore filtering entirely), plus one extra checkbox
    to show each person's relationship to the Home Person instead of their
    name (see _person_name_text()).
    """

    def __init__(self, person, dbstate, uistate, track=None, window=None):
        WriterOptionBox.__init__(self, person, dbstate, uistate, track=track or [], window=window)
        self.use_relationship_labels = False
        self._relationship_labels_check = None

    def get_option_box(self):
        from gi.repository import Gtk

        option_box = WriterOptionBox.get_option_box(self)
        self._relationship_labels_check = Gtk.CheckButton(label=_("Show relationship instead of name"))
        self._relationship_labels_check.set_active(self.use_relationship_labels)
        option_box.pack_start(self._relationship_labels_check, False, True, 0)
        return option_box

    def parse_options(self):
        WriterOptionBox.parse_options(self)
        if self._relationship_labels_check:
            self.use_relationship_labels = self._relationship_labels_check.get_active()


_HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:java="http://www.yworks.com/xml/yfiles-common/1.0/java" xmlns:sys="http://www.yworks.com/xml/yfiles-common/markup/primitives/2.0" xmlns:x="http://www.yworks.com/xml/yfiles-common/markup/2.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:y="http://www.yworks.com/xml/graphml" xmlns:yed="http://www.yworks.com/xml/yed/3" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <key for="node" id="d0" yfiles.type="nodegraphics"/>
  <key for="edge" id="d1" yfiles.type="edgegraphics"/>
  <graph edgedefault="directed" id="G">
"""

_FOOTER = """  </graph>
</graphml>
"""
