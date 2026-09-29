"""
Builds the data for the illness graph: which people to draw (from
illness_filter.filter_relevant_people), what their node label should say,
and how families connect to each other.

Deliberately Graphviz-agnostic: it only decides *what* to draw. Turning
that into actual Graphviz nodes/edges (shapes, escaping, samerank, ...) is
illness_report.py's job. This split lets the interesting logic (labels,
dates, relationships) be tested without running a full Gramps report.

Each family with at least one relevant parent and one relevant child
becomes one FamilyLink rather than separate parent->child edges. Drawing
two parents' lines to the same children separately makes it visually
ambiguous which child belongs to which parent when lines cross; routing
everyone through a shared bracket per family instead (illness_report.py
draws this out of small invisible points) avoids that ambiguity entirely,
since each child then has exactly one line, tracing back to one shared
point the parents connect to.
"""

from dataclasses import dataclass, field

from gramps.gen.lib import EventType
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.utils.symbols import Symbols

from illness_filter import (
    DEFAULT_ANCESTOR_GENERATIONS,
    DEFAULT_DESCENDANT_GENERATIONS,
    compute_relevant_generations,
)


@dataclass
class PersonNode:
    handle: str
    label: str
    rounded: bool  # True for female persons: box should have rounded corners
    # Number of leading lines in `label` (name, birth, death) that should
    # stay centered; the rest (the illness list) reads better aligned to
    # the reading direction instead, since it's a bullet list.
    centered_line_count: int


@dataclass
class FamilyLink:
    family_handle: str
    parent_handles: list  # relevant parents only (0-2), father before mother
    child_handles: list  # relevant children only, sorted by birthdate


@dataclass
class GraphData:
    nodes: dict = field(default_factory=dict)  # handle -> PersonNode
    family_links: list = field(default_factory=list)  # FamilyLink, only where a link is actually needed
    couples: list = field(default_factory=list)  # (father_handle, mother_handle), both relevant
    # People grouped generation by generation (ancestors first), each group
    # ordered left-to-right by birthdate with couples kept adjacent. Used to
    # keep siblings/couples visually together and in age order, and to
    # reduce line crossings, since Graphviz's own left-to-right ordering
    # within a rank otherwise ignores both.
    generation_order: list = field(default_factory=list)  # [(generation, [handle, ...]), ...]


def build_graph_data(
    database,
    me,
    get_date,
    name_display,
    relationship_calculator,
    me_label,
    ancestor_generations=DEFAULT_ANCESTOR_GENERATIONS,
    descendant_generations=DEFAULT_DESCENDANT_GENERATIONS,
    use_relationship_labels=False,
):
    """
    :param get_date: callable(date_object) -> str, e.g. a Report's
        self._get_date, or GRAMPS_LOCALE.get_date for testing
    :param name_display: a NameDisplay instance, e.g. a Report's
        self._name_display, or gramps.gen.display.name.displayer for testing
    :param relationship_calculator: a RelationshipCalculator instance, e.g.
        from gramps.gen.relationship.get_relationship_calculator()
    :param me_label: the (already translated) label to use for "me" when
        use_relationship_labels is True, since "me" has no relationship to
        themselves
    """
    me_handle = me.get_handle() if hasattr(me, "get_handle") else me
    generations = compute_relevant_generations(database, me_handle, ancestor_generations, descendant_generations)
    relevant = set(generations)
    me_person = database.get_person_from_handle(me_handle)

    symbols = Symbols()
    nodes = {}
    for handle in relevant:
        person = database.get_person_from_handle(handle)
        label, centered_line_count = _build_label(
            database,
            person,
            me_person,
            get_date,
            name_display,
            relationship_calculator,
            me_label,
            use_relationship_labels,
            symbols,
        )
        nodes[handle] = PersonNode(
            handle=handle,
            label=label,
            rounded=person.get_gender() == person.FEMALE,
            centered_line_count=centered_line_count,
        )

    family_links = []
    couples = []
    handled_families = set()
    for handle in sorted(relevant, key=lambda h: _birth_sort_key(database, h)):
        person = database.get_person_from_handle(handle)
        for family_handle in person.get_family_handle_list():
            if family_handle in handled_families:
                continue
            handled_families.add(family_handle)

            family = database.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            if father_handle in relevant and mother_handle in relevant:
                couples.append((father_handle, mother_handle))

            parent_handles = [h for h in (father_handle, mother_handle) if h and h in relevant]
            child_handles = sorted(
                (
                    ref.get_reference_handle()
                    for ref in family.get_child_ref_list()
                    if ref.get_reference_handle() in relevant
                ),
                key=lambda h: _birth_sort_key(database, h),
            )
            if parent_handles and child_handles:
                family_links.append(FamilyLink(family_handle, parent_handles, child_handles))

    generation_order = _ordered_generation_groups(database, generations, couples)

    return GraphData(nodes=nodes, family_links=family_links, couples=couples, generation_order=generation_order)


def _ordered_generation_groups(database, generations, couples):
    """
    Group handles by generation, each group ordered per _order_generation.
    """
    partner_of = {}
    for father_handle, mother_handle in couples:
        partner_of[father_handle] = mother_handle
        partner_of[mother_handle] = father_handle

    by_generation = {}
    for handle, generation in generations.items():
        by_generation.setdefault(generation, []).append(handle)

    return [
        (generation, _order_generation(database, by_generation[generation], partner_of))
        for generation in sorted(by_generation)
    ]


def _order_generation(database, handles, partner_of):
    """
    Order one generation's people left to right: group blood siblings
    (people sharing a parent family) into a contiguous block, sorted by
    birthdate, and sort the blocks themselves by birthdate.

    Keeping sibling blocks contiguous matters beyond appearances: it's
    exactly what illness_report._draw_family_link's parent-to-children
    point connects to, and a spouse splitting a block in two would force
    that connection to visually reach past them to their actual siblings.

    Someone with no siblings in this generation - typically a spouse who
    married in - needs to sit right next to their partner's block instead.
    Rather than just birthdate-sorting each block and hoping the in-block
    partner already happens to be at the edge nearest the other block, each
    block is oriented (which end its birthdate order starts from) so that
    member ends up at whichever edge faces the partner's block; that avoids
    a couple's own connecting line having to reach across the whole block
    (and everyone else's lines dangling below it) to find each other.
    """
    handle_set = set(handles)

    sibling_group_of = {}
    for handle in handles:
        person = database.get_person_from_handle(handle)
        sibling_group_of[handle] = person.get_main_parents_family_handle() or handle

    blocks = {}
    for handle in handles:
        blocks.setdefault(sibling_group_of[handle], []).append(handle)
    for members in blocks.values():
        members.sort(key=lambda h: _birth_sort_key(database, h))

    block_order = sorted(blocks, key=lambda key: _birth_sort_key(database, blocks[key][0]))
    block_index = {key: index for index, key in enumerate(block_order)}

    for key in block_order:
        members = blocks[key]
        for handle in members:
            partner = partner_of.get(handle)
            if not partner or partner not in handle_set or sibling_group_of[partner] == key:
                continue
            wants_right_edge = block_index[sibling_group_of[partner]] > block_index[key]
            if wants_right_edge and members[0] == handle and members[-1] != handle:
                members.reverse()
            elif not wants_right_edge and members[-1] == handle and members[0] != handle:
                members.reverse()
            break  # one orienting member is enough; further members can't all be satisfied anyway

    ordered = [handle for key in block_order for handle in blocks[key]]

    for handle in list(ordered):
        partner = partner_of.get(handle)
        if not partner or partner not in handle_set:
            continue
        if len(blocks[sibling_group_of[handle]]) > 1:
            continue  # has blood siblings here; leave this block as-is

        partner_block = blocks[sibling_group_of[partner]]
        block_positions = [ordered.index(member) for member in partner_block if member in ordered]
        if not block_positions:
            continue
        left_edge, right_edge = min(block_positions), max(block_positions)
        current_position = ordered.index(handle)
        if left_edge - 1 <= current_position <= right_edge + 1:
            continue  # already right next to the block

        ordered.remove(handle)
        block_positions = [ordered.index(member) for member in partner_block if member in ordered]
        left_edge, right_edge = min(block_positions), max(block_positions)
        insert_at = right_edge + 1 if current_position > right_edge else left_edge
        ordered.insert(insert_at, handle)

    return ordered


def _build_label(
    database,
    person,
    me_person,
    get_date,
    name_display,
    relationship_calculator,
    me_label,
    use_relationship_labels,
    symbols,
):
    lines = [
        _person_heading(
            database, person, me_person, name_display, relationship_calculator, me_label, use_relationship_labels
        )
    ]

    birth_event = get_birth_or_fallback(database, person)
    if birth_event:
        birth_symbol = symbols.get_symbol_for_string(symbols.SYMBOL_BIRTH)
        lines.append(f"{birth_symbol} {get_date(birth_event.get_date_object())}")

    death_event = get_death_or_fallback(database, person)
    if death_event:
        death_symbol = symbols.get_death_symbol_fallback(symbols.DEATH_SYMBOL_LATIN_CROSS)
        death_line = f"{death_symbol} {get_date(death_event.get_date_object())}"
        cause_of_death = _find_event(database, person, EventType.CAUSE_DEATH)
        if cause_of_death and cause_of_death.get_description():
            death_line += f" ({cause_of_death.get_description()})"
        lines.append(death_line)

    centered_line_count = len(lines)

    for illness in _find_events(database, person, EventType.MED_INFO):
        date_str = get_date(illness.get_date_object())
        if date_str:
            lines.append(f"- {illness.get_description()} ({date_str})")
        else:
            lines.append(f"- {illness.get_description()}")

    return "\n".join(lines), centered_line_count


def _person_heading(
    database, person, me_person, name_display, relationship_calculator, me_label, use_relationship_labels
):
    if not use_relationship_labels:
        return name_display.display(person)
    if person.get_handle() == me_person.get_handle():
        return me_label
    relationship = relationship_calculator.get_one_relationship(database, me_person, person)
    return relationship.capitalize() if relationship else name_display.display(person)


def _find_event(database, person, event_type):
    for event_ref in person.get_event_ref_list():
        event = database.get_event_from_handle(event_ref.get_reference_handle())
        if event.get_type() == event_type:
            return event
    return None


def _find_events(database, person, event_type):
    events = [
        database.get_event_from_handle(event_ref.get_reference_handle()) for event_ref in person.get_event_ref_list()
    ]
    events = [event for event in events if event.get_type() == event_type]
    events.sort(key=lambda event: event.get_date_object().get_sort_value())
    return events


def _birth_sort_key(database, handle):
    person = database.get_person_from_handle(handle)
    birth_event = get_birth_or_fallback(database, person)
    if birth_event and birth_event.get_date_object().get_valid():
        return birth_event.get_date_object().get_sort_value()
    return float("inf")
