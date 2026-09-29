"""
Tests for the graph-building module (`illness_graph.build_graph_data`).

Uses the same TestTree fixture as test_filter.py (see README.md in this
directory). Since build_graph_data is Graphviz-agnostic (see illness_graph's
module docstring), these tests check the underlying data - node labels,
family links, couples, and generation ordering - without needing a running
Gramps report or Graphviz itself.

Covers:
- exactly the filtered set of people (from illness_filter) get a node
- a node's label uses the display name by default, or the relationship to
  "me" (e.g. mother, cousin) when that option is enabled, with "me"
  themselves shown as a fixed label
- birth date, death date, cause of death, and illnesses (with dates) show
  up in a person's label when present
- female persons are marked for rounded box corners, male persons are not
- family links (which imply parent-child edges) and couples only ever
  reference people in the filtered set (in-laws never appear, matching
  illness_filter's exclusions)
- people are grouped generation by generation, each group ordered by
  birthdate with couples kept adjacent
"""

import os
import sys
import unittest
from typing import Any

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_TEST_DIR))  # repo root, for illness_graph
sys.path.insert(0, _TEST_DIR)  # this directory, for testtree

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import displayer
from gramps.gen.relationship import get_relationship_calculator

from illness_graph import build_graph_data
from testtree import EXPECTED_INCLUDED_ROLES, build_role_to_handle, load_test_tree

ME_LABEL = "Me"


class TestBuildGraphData(unittest.TestCase):
    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)
        cls.handle_to_role = {handle: role for role, handle in cls.role_to_handle.items()}
        cls.me_handle = cls.role_to_handle["Me"]
        cls.relationship_calculator = get_relationship_calculator()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _build(self, **kwargs):
        return build_graph_data(
            self.db,
            self.me_handle,
            glocale.get_date,
            displayer,
            self.relationship_calculator,
            ME_LABEL,
            **kwargs,
        )

    def _role(self, handle):
        return self.handle_to_role[handle]

    @staticmethod
    def _implied_edges(graph):
        """Flatten each FamilyLink's junction into the (parent, child) pairs it implies."""
        return {
            (parent_handle, child_handle)
            for link in graph.family_links
            for parent_handle in link.parent_handles
            for child_handle in link.child_handles
        }

    def test_nodes_match_the_filtered_set(self):
        graph = self._build()
        roles = {self._role(handle) for handle in graph.nodes}
        self.assertEqual(roles, EXPECTED_INCLUDED_ROLES)

    def test_default_label_is_the_display_name(self):
        graph = self._build()
        my_mother = graph.nodes[self.role_to_handle["MyMother"]]
        self.assertIn("MyMothersFirstName", my_mother.label)
        self.assertIn("MyMothersLastName", my_mother.label)

    def test_relationship_label_shows_relationship_instead_of_name(self):
        graph = self._build(use_relationship_labels=True)

        me_node = graph.nodes[self.me_handle]
        self.assertEqual(me_node.label.splitlines()[0], ME_LABEL)

        my_mother = graph.nodes[self.role_to_handle["MyMother"]]
        heading = my_mother.label.splitlines()[0]
        self.assertNotIn("MyMothersFirstName", heading)
        self.assertNotEqual(heading, "")

    def test_birth_date_is_shown(self):
        graph = self._build()
        my_mother = graph.nodes[self.role_to_handle["MyMother"]]
        self.assertIn("1960", my_mother.label)

    def test_death_date_and_cause_are_shown(self):
        graph = self._build()
        great_grandfather = graph.nodes[self.role_to_handle["MomsFathersFather"]]
        self.assertIn("1900", great_grandfather.label)  # birth
        self.assertIn("1980", great_grandfather.label)  # death
        self.assertIn("Cancer", great_grandfather.label)  # cause of death

    def test_centered_line_count_covers_name_birth_death_only(self):
        # Me: name, birth -> 2 lines stay centered; the 2 illness lines after
        # that are meant to be aligned to the reading direction instead.
        graph = self._build()
        me_node = graph.nodes[self.me_handle]
        self.assertEqual(me_node.centered_line_count, 2)

        # MomsFathersFather: name, birth, death -> 3 lines stay centered.
        great_grandfather = graph.nodes[self.role_to_handle["MomsFathersFather"]]
        self.assertEqual(great_grandfather.centered_line_count, 3)

        # MyFather: name only, no birth/death/illness data at all.
        my_father = graph.nodes[self.role_to_handle["MyFather"]]
        self.assertEqual(my_father.centered_line_count, 1)
        self.assertEqual(my_father.label.count("\n"), 0)

    def test_illnesses_are_shown_with_dates_in_chronological_order(self):
        graph = self._build()
        me_node = graph.nodes[self.me_handle]
        first_illness_pos = me_node.label.index("MyFirstIllness")
        second_illness_pos = me_node.label.index("MySecondIllness")
        self.assertLess(first_illness_pos, second_illness_pos)
        self.assertIn("2000", me_node.label)
        self.assertIn("2001", me_node.label)

    def test_older_illness_events_are_shown_for_ancestors_too(self):
        graph = self._build()
        great_grandfather = graph.nodes[self.role_to_handle["MomsFathersFather"]]
        self.assertIn("Asthma", great_grandfather.label)
        self.assertIn("1940", great_grandfather.label)

    def test_female_persons_get_rounded_corners(self):
        graph = self._build()
        for role in ("Me", "MyMother", "MomsMom", "MomsSister", "MomsFathersMother"):
            with self.subTest(role=role):
                self.assertTrue(graph.nodes[self.role_to_handle[role]].rounded)

    def test_male_persons_do_not_get_rounded_corners(self):
        graph = self._build()
        for role in ("MyFather", "MyBrother", "MomsFather", "MomsBrother", "MomsFathersFather"):
            with self.subTest(role=role):
                self.assertFalse(graph.nodes[self.role_to_handle[role]].rounded)

    def test_family_links_only_reference_included_people(self):
        graph = self._build()
        included_handles = set(graph.nodes)
        for link in graph.family_links:
            for handle in link.parent_handles + link.child_handles:
                self.assertIn(handle, included_handles)

    def test_expected_edges_are_present(self):
        graph = self._build()
        edge_roles = {(self._role(parent), self._role(child)) for parent, child in self._implied_edges(graph)}
        for expected in (
            ("MyFather", "Me"),
            ("MyMother", "Me"),
            ("MyFather", "MyBrother"),
            ("MyMother", "MyBrother"),
            ("Me", "MyChild"),
            ("MomsFather", "MyMother"),
            ("MomsMom", "MyMother"),
            ("MomsFather", "MomsSister"),
            ("MomsMom", "MomsSister"),
            ("MomsSister", "MomsSistersChild"),
            ("MomsFathersFather", "MomsFather"),
            ("MomsFathersMother", "MomsFather"),
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, edge_roles)

    def test_in_laws_never_appear_in_a_family_link(self):
        graph = self._build()
        in_law_roles = {"MyHusband", "HusbandsFather", "HusbandsMother", "MomsSistersHusband"}
        for link in graph.family_links:
            for handle in link.parent_handles + link.child_handles:
                self.assertNotIn(self._role(handle), in_law_roles)

    def test_couples_are_only_pairs_where_both_partners_are_included(self):
        graph = self._build()
        couple_roles = {frozenset((self._role(a), self._role(b))) for a, b in graph.couples}
        self.assertIn(frozenset(("MyFather", "MyMother")), couple_roles)
        self.assertIn(frozenset(("MomsFather", "MomsMom")), couple_roles)
        self.assertIn(frozenset(("MomsFathersFather", "MomsFathersMother")), couple_roles)
        # MomsSistersHusband is excluded, so this couple must not appear.
        self.assertNotIn(frozenset(("MomsSister", "MomsSistersHusband")), couple_roles)

    def test_generation_order_covers_every_node_exactly_once(self):
        graph = self._build()
        handles_in_groups = [handle for _generation, handles in graph.generation_order for handle in handles]
        self.assertEqual(sorted(handles_in_groups), sorted(graph.nodes))

    def test_generation_order_is_sorted_ancestors_first(self):
        graph = self._build()
        generations = [generation for generation, _handles in graph.generation_order]
        self.assertEqual(generations, sorted(generations))

    def test_couples_are_adjacent_within_their_generation_group(self):
        graph = self._build()
        for generation, handles in graph.generation_order:
            role_order = [self._role(handle) for handle in handles]
            if "MomsFather" in role_order and "MomsMom" in role_order:
                self.assertEqual(abs(role_order.index("MomsFather") - role_order.index("MomsMom")), 1)

    def test_ancestor_and_descendant_generations_are_forwarded(self):
        # ancestor_generations=0 means "me"'s own parents are never reached,
        # so MomsSister (and thus MomsSistersChild) never get discovered
        # either - only "me" and "me"'s own siblings remain.
        graph = self._build(ancestor_generations=0, descendant_generations=0)
        roles = {self._role(handle) for handle in graph.nodes}
        self.assertEqual(roles, {"Me", "MyBrother"})


if __name__ == "__main__":
    unittest.main()
