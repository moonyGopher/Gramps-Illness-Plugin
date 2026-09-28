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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gramps.cli.user import User
from gramps.gen.db.utils import import_as_dict

from illness_filter import DEFAULT_ANCESTOR_GENERATIONS, filter_relevant_people

TESTDATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")
TEST_TREE_PATH = os.path.join(TESTDATA_DIR, "TestTree.gramps")

# Maps the role names used in README.md to the (unique) first names used in
# testdata/TestTree.gramps.
ROLE_TO_FIRST_NAME = {
    "Me": "MyFirstName",
    "MyHusband": "MyHusbandsFirstName",
    "MyChild": "MyChildsFirstName",
    "HusbandsFather": "HusbandsFathersFirstName",
    "HusbandsMother": "HusbandsMothersFirstName",
    "MyBrother": "MyBrothersFirstName",
    "MyMother": "MyMothersFirstName",
    "MyFather": "MyFathersFirstName",
    "MomsMom": "MomsMomsFirstName",
    "MomsFather": "MomsFathersFirstName",
    "MomsSister": "MomsSistersFirstName",
    "MomsBrother": "MomsBrothersFirstName",
    "MomsSistersHusband": "MomsSistersHusbandsFirstName",
    "MomsSistersChild": "MomsSistersChildsFirstName",
    "MomsFathersMother": "MomsFathersMothersFirstName",
    "MomsFathersFather": "MomsFathersFathersFirstName",
}

# Everyone in the TestTree that is medically relevant to "Me" with the
# default ancestor/descendant depth of 3 generations.
EXPECTED_INCLUDED_ROLES = {
    "Me",
    "MyBrother",
    "MyChild",
    "MyFather",
    "MyMother",
    "MomsMom",
    "MomsFather",
    "MomsSister",
    "MomsBrother",
    "MomsSistersChild",
    "MomsFathersMother",
    "MomsFathersFather",
}

# In-laws: only connected to "Me" by marriage, never included.
EXPECTED_EXCLUDED_ROLES = {
    "MyHusband",
    "HusbandsFather",
    "HusbandsMother",
    "MomsSistersHusband",
}


class TestIllnessFilter(unittest.TestCase):
    # Gramps ships no type stubs, so import_as_dict()'s inferred return type
    # is Optional; declared here as Any to match how mypy already treats it
    # (ignore_missing_imports in pyproject.toml), since it can't actually be
    # None once setUpClass returns without raising.
    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = import_as_dict(TEST_TREE_PATH, User(quiet=True))
        cls.role_to_handle = {
            role: cls._find_handle_by_first_name(first_name) for role, first_name in ROLE_TO_FIRST_NAME.items()
        }
        cls.me_handle = cls.role_to_handle["Me"]

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    @classmethod
    def _find_handle_by_first_name(cls, first_name):
        for person in cls.db.iter_people():
            if person.get_primary_name().get_first_name() == first_name:
                return person.get_handle()
        raise LookupError(f"No person with first name {first_name!r} in TestTree")

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
