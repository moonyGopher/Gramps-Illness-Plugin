"""
Filters a Gramps family tree down to the people who are medically relevant
to a chosen "me" person: blood relatives only, in-laws excluded.

Included, starting from "me":
- direct ancestors (parents, grandparents, ...), up to `ancestor_generations`
  levels. Both parents of an ancestor are included, since both are blood
  relatives.
- at every ancestor level (including "me"'s own level), the siblings of
  that generation's blood relative (aunts/uncles, or "me"'s own siblings),
  together with their descendants, up to `descendant_generations` levels
  (i.e. cousins, ...).
- direct descendants of "me" (children, grandchildren, ...), up to
  `descendant_generations` levels.

Excluded: anyone only connected by marriage (spouses/in-laws) who is not
also a blood relative through one of the paths above.
"""

DEFAULT_ANCESTOR_GENERATIONS = 3
DEFAULT_DESCENDANT_GENERATIONS = 3


def filter_relevant_people(
    database,
    me,
    ancestor_generations=DEFAULT_ANCESTOR_GENERATIONS,
    descendant_generations=DEFAULT_DESCENDANT_GENERATIONS,
):
    """
    Return the set of person handles considered medically relevant to `me`.

    :param database: a Gramps database (anything implementing DbReadBase)
    :param me: the central Person, or its handle
    :param ancestor_generations: how many generations of ancestors to
        include (1 = parents, 2 = grandparents, ...)
    :param descendant_generations: how many generations of descendants to
        include, both directly from `me` and from each collateral relative
        (sibling/aunt/uncle/...) found while walking up the ancestor line
    :rtype: set[str]
    """
    me_handle = me.get_handle() if hasattr(me, "get_handle") else me

    relevant = set()
    _add_ancestors_and_collaterals(
        database,
        me_handle,
        ancestor_generations,
        descendant_generations,
        relevant,
        processed=set(),
    )
    _add_descendants(database, me_handle, descendant_generations, relevant)
    return relevant


def _add_ancestors_and_collaterals(
    database,
    person_handle,
    remaining_ancestor_generations,
    descendant_generations,
    relevant,
    processed,
):
    """
    Add `person_handle`, their siblings (with the siblings' descendants),
    and recurse into both parents while ancestor generations remain.
    """
    if person_handle in processed:
        return
    processed.add(person_handle)
    relevant.add(person_handle)

    person = database.get_person_from_handle(person_handle)
    parent_family_handle = person.get_main_parents_family_handle()
    if parent_family_handle is None:
        return
    parent_family = database.get_family_from_handle(parent_family_handle)

    for child_ref in parent_family.get_child_ref_list():
        sibling_handle = child_ref.get_reference_handle()
        if sibling_handle == person_handle:
            continue
        relevant.add(sibling_handle)
        _add_descendants(database, sibling_handle, descendant_generations, relevant)

    if remaining_ancestor_generations <= 0:
        return

    for parent_handle in (
        parent_family.get_father_handle(),
        parent_family.get_mother_handle(),
    ):
        if parent_handle:
            _add_ancestors_and_collaterals(
                database,
                parent_handle,
                remaining_ancestor_generations - 1,
                descendant_generations,
                relevant,
                processed,
            )


def _add_descendants(database, person_handle, remaining_generations, relevant, processed=None):
    """
    Add `person_handle` and recurse into their children while descendant
    generations remain. Partners are deliberately not added: only blood
    descendants are followed.
    """
    if processed is None:
        processed = set()
    if person_handle in processed:
        return
    processed.add(person_handle)
    relevant.add(person_handle)

    if remaining_generations <= 0:
        return

    person = database.get_person_from_handle(person_handle)
    for family_handle in person.get_family_handle_list():
        family = database.get_family_from_handle(family_handle)
        for child_ref in family.get_child_ref_list():
            _add_descendants(
                database,
                child_ref.get_reference_handle(),
                remaining_generations - 1,
                relevant,
                processed,
            )
