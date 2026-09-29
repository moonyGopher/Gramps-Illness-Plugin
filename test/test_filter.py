"""
Tests for the filter module (`illness_filter.filter_relevant_people`).

Uses the TestTree fixture from testdata/TestTree.gramps, with "Me" as the
central person. See README.md in this directory for the full list of
people expected to be included/excluded.

Covers:
- filtering starts from a chosen "me" person (handle or Person object)
- direct ancestors (parents, grandparents, ...) are included
- direct descendants (children, grandchildren, ...) are included
- ancestor/descendant depth defaults to 3 generations, and is adjustable
- siblings of ancestors (aunts/uncles), and "me"'s own siblings, are
  included, together with their children (cousins, ...)
- anyone only connected by marriage (spouses/in-laws) is excluded, even
  when their blood-relative partner is included
"""

import os
import sys
import unittest
from typing import Any

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_TEST_DIR))  # repo root, for illness_filter
sys.path.insert(0, _TEST_DIR)  # this directory, for testtree

from illness_filter import DEFAULT_ANCESTOR_GENERATIONS, filter_relevant_people
from testtree import EXPECTED_EXCLUDED_ROLES, EXPECTED_INCLUDED_ROLES, build_role_to_handle, load_test_tree


class TestIllnessFilter(unittest.TestCase):
    # Gramps ships no type stubs, so import_as_dict()'s inferred return type
    # is Optional; declared here as Any to match how mypy already treats it
    # (ignore_missing_imports in pyproject.toml), since it can't actually be
    # None once setUpClass returns without raising.
    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)
        cls.me_handle = cls.role_to_handle["Me"]

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _relevant_roles(self, me=None, **kwargs):
        """Run the filter and translate the resulting handles back to role names."""
        handles = filter_relevant_people(self.db, me or self.me_handle, **kwargs)
        return {role for role, handle in self.role_to_handle.items() if handle in handles}

    def test_matches_documented_test_tree(self):
        self.assertEqual(self._relevant_roles(), EXPECTED_INCLUDED_ROLES)

    def test_default_ancestor_generations_is_three(self):
        self.assertEqual(DEFAULT_ANCESTOR_GENERATIONS, 3)

    def test_me_is_always_included(self):
        self.assertIn("Me", self._relevant_roles())

    def test_direct_ancestors_are_included(self):
        result = self._relevant_roles()
        for role in (
            "MyFather",
            "MyMother",
            "MomsFather",
            "MomsMom",
            "MomsFathersFather",
            "MomsFathersMother",
        ):
            self.assertIn(role, result)

    def test_direct_descendants_are_included(self):
        self.assertIn("MyChild", self._relevant_roles())

    def test_ancestor_generations_is_adjustable(self):
        # Default (3 generations) reaches great-grandparents.
        self.assertIn("MomsFathersFather", self._relevant_roles(ancestor_generations=3))

        # 2 generations: grandparents yes, great-grandparents no.
        result = self._relevant_roles(ancestor_generations=2)
        self.assertIn("MomsFather", result)
        self.assertIn("MomsMom", result)
        self.assertNotIn("MomsFathersFather", result)
        self.assertNotIn("MomsFathersMother", result)

        # 1 generation: parents yes, grandparents no.
        result = self._relevant_roles(ancestor_generations=1)
        self.assertIn("MyFather", result)
        self.assertIn("MyMother", result)
        self.assertNotIn("MomsFather", result)
        self.assertNotIn("MomsMom", result)

        # 0 generations: "me" and "me"'s own siblings only, no parents.
        result = self._relevant_roles(ancestor_generations=0)
        self.assertIn("Me", result)
        self.assertIn("MyBrother", result)
        self.assertNotIn("MyFather", result)
        self.assertNotIn("MyMother", result)

    def test_descendant_generations_is_adjustable(self):
        self.assertIn("MyChild", self._relevant_roles(descendant_generations=1))
        self.assertNotIn("MyChild", self._relevant_roles(descendant_generations=0))

    def test_husband_and_his_family_are_excluded(self):
        result = self._relevant_roles()
        for role in EXPECTED_EXCLUDED_ROLES:
            self.assertNotIn(role, result)

    def test_sisters_children_are_included(self):
        self.assertIn("MomsSistersChild", self._relevant_roles())

    def test_siblings_of_ancestors_are_included(self):
        result = self._relevant_roles()
        self.assertIn("MomsSister", result)
        self.assertIn("MomsBrother", result)

    def test_spouses_of_collateral_relatives_are_excluded(self):
        # MomsSistersHusband only relates to "Me" through marriage into
        # MomsSister's family, so he must stay excluded even though
        # MomsSister and their child are included.
        result = self._relevant_roles()
        self.assertIn("MomsSister", result)
        self.assertIn("MomsSistersChild", result)
        self.assertNotIn("MomsSistersHusband", result)

    def test_accepts_person_object_or_handle(self):
        me_person = self.db.get_person_from_handle(self.me_handle)
        by_handle = self._relevant_roles(me=self.me_handle)
        by_object = self._relevant_roles(me=me_person)
        self.assertEqual(by_handle, by_object)

    def test_root_person_is_configurable(self):
        # Filtering from a different root person still excludes people who
        # are only related to *that* person by marriage.
        moms_father_handle = self.role_to_handle["MomsFather"]
        result = self._relevant_roles(me=moms_father_handle)
        self.assertNotIn("HusbandsFather", result)
        self.assertNotIn("HusbandsMother", result)


if __name__ == "__main__":
    unittest.main()
