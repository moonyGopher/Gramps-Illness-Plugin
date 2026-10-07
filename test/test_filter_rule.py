"""
Tests for the Person filter rule (`illness_filter_rule.IsMedicallyRelevantTo`)
and the ready-made filter built from it (`make_filters`/`load_on_reg`), which
together let the filter be used in Gramps' Filter Editor and, from there (or
directly, for the ready-made one), as an export filter (e.g. for GEDCOM).

Uses the same TestTree fixture and expected roles as test_filter.py, since
the rule is a thin Gramps-facing wrapper around the same filtering logic;
see test_filter.py for the full generation/in-law coverage of the
underlying algorithm. This file instead covers the wrapper itself: how
Gramps' string-based rule parameters (`self.list`) are turned into the
filter's arguments, the prepare/apply_to_one/reset lifecycle Gramps drives
it through, the Home Person fallback for a blank ID, and the ready-made
filter contributed via `make_filters`.
"""

import os
import sys
import unittest
from typing import Any

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_TEST_DIR))  # repo root, for illness_filter_rule
sys.path.insert(0, _TEST_DIR)  # this directory, for testtree

from gramps.gen.display.name import displayer as name_displayer

from illness_filter_rule import _, IsMedicallyRelevantTo, load_on_reg, make_filters
from testtree import EXPECTED_EXCLUDED_ROLES, EXPECTED_INCLUDED_ROLES, build_role_to_handle, load_test_tree


class _FakeDbState:
    """Minimal stand-in for gramps.gen.dbstate.DbState, enough for make_filters()."""

    def __init__(self, db):
        self.db = db

    def is_open(self):
        return True


class TestIsMedicallyRelevantTo(unittest.TestCase):
    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)
        cls.me_handle = cls.role_to_handle["Me"]
        cls.me_gramps_id = cls.db.get_person_from_handle(cls.me_handle).get_gramps_id()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _relevant_roles(self, gramps_id=None, ancestor_generations="", descendant_generations=""):
        """Prepare the rule and translate the people it matches back to role names."""
        # Note: `gramps_id` can deliberately be "" (to test the blank-ID/
        # Home Person fallback), so it must be distinguished from "not
        # passed at all" via `is None`, not a falsy check.
        if gramps_id is None:
            gramps_id = self.me_gramps_id
        rule = IsMedicallyRelevantTo([gramps_id, ancestor_generations, descendant_generations])
        rule.prepare(self.db, user=None)
        try:
            matched = {
                role
                for role, handle in self.role_to_handle.items()
                if rule.apply_to_one(self.db, self.db.get_person_from_handle(handle))
            }
        finally:
            rule.reset()
        return matched

    def test_matches_documented_test_tree_with_default_generations(self):
        # Empty strings are what Gramps passes for a rule parameter the
        # user left blank, so the rule must fall back to illness_filter's
        # own defaults (3/3) rather than crashing on int("").
        self.assertEqual(self._relevant_roles(), EXPECTED_INCLUDED_ROLES)

    def test_in_laws_are_excluded(self):
        result = self._relevant_roles()
        for role in EXPECTED_EXCLUDED_ROLES:
            self.assertNotIn(role, result)

    def test_generation_parameters_are_parsed_as_integers(self):
        result = self._relevant_roles(ancestor_generations="1", descendant_generations="0")
        self.assertIn("MyFather", result)
        self.assertNotIn("MomsFather", result)
        self.assertNotIn("MyChild", result)

    def test_non_numeric_generation_parameter_falls_back_to_default(self):
        result = self._relevant_roles(ancestor_generations="not a number")
        self.assertEqual(result, EXPECTED_INCLUDED_ROLES)

    def test_unknown_gramps_id_matches_nobody(self):
        self.assertEqual(self._relevant_roles(gramps_id="I9999"), set())

    def test_root_person_is_configurable(self):
        moms_father_id = self.db.get_person_from_handle(self.role_to_handle["MomsFather"]).get_gramps_id()
        result = self._relevant_roles(gramps_id=moms_father_id)
        self.assertNotIn("HusbandsFather", result)
        self.assertNotIn("HusbandsMother", result)

    def test_reset_clears_selected_handles(self):
        rule = IsMedicallyRelevantTo([self.me_gramps_id, "", ""])
        rule.prepare(self.db, user=None)
        self.assertTrue(rule.selected_handles)
        rule.reset()
        self.assertEqual(rule.selected_handles, set())

    def test_blank_id_falls_back_to_home_person(self):
        self.db.set_default_person_handle(self.me_handle)
        try:
            self.assertEqual(self._relevant_roles(gramps_id=""), EXPECTED_INCLUDED_ROLES)
        finally:
            self.db.set_default_person_handle(None)

    def test_blank_id_matches_nobody_without_a_home_person(self):
        self.db.set_default_person_handle(None)
        self.assertEqual(self._relevant_roles(gramps_id=""), set())


class TestMakeFilters(unittest.TestCase):
    """
    Tests for make_filters()/load_on_reg(), which contribute a filter for
    the tree's current Home Person to every Person filter list. Since
    Gramps only ever calls make_filters(namespace) - no database access of
    its own - load_on_reg() must first capture a (fake, here) DbState so
    make_filters() can look up that Home Person; see illness_filter_rule.py.
    """

    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)
        cls.me_handle = cls.role_to_handle["Me"]
        cls.me_name = name_displayer.display(cls.db.get_person_from_handle(cls.me_handle))

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        load_on_reg(dbstate=_FakeDbState(self.db), uistate=None, plugin=None)
        self.db.set_default_person_handle(self.me_handle)

    def tearDown(self):
        self.db.set_default_person_handle(None)
        load_on_reg(dbstate=None, uistate=None, plugin=None)

    def test_contributes_a_person_filter_named_after_the_home_person(self):
        # Compare against the module's own translator output rather than a
        # hardcoded English literal: Gramps' addon translator follows the
        # active locale, so the filter's actual name may be translated.
        person_filter = make_filters("Person")
        self.assertIsNotNone(person_filter)
        self.assertEqual(person_filter.get_name(), _("Medically relevant people of %s") % self.me_name)

    def test_contributes_nothing_for_other_namespaces(self):
        self.assertIsNone(make_filters("Note"))
        self.assertIsNone(make_filters("Family"))

    def test_contributes_nothing_without_a_home_person(self):
        self.db.set_default_person_handle(None)
        self.assertIsNone(make_filters("Person"))

    def test_contributes_nothing_without_a_registered_dbstate(self):
        load_on_reg(dbstate=None, uistate=None, plugin=None)
        self.assertIsNone(make_filters("Person"))

    def test_contributed_filter_matches_the_home_person(self):
        person_filter = make_filters("Person")
        matched = {role for role, handle in self.role_to_handle.items() if person_filter.match(handle, self.db)}
        self.assertEqual(matched, EXPECTED_INCLUDED_ROLES)

    def test_load_on_reg_returns_make_filters(self):
        self.assertEqual(load_on_reg(dbstate=_FakeDbState(self.db), uistate=None, plugin=None), [make_filters])


if __name__ == "__main__":
    unittest.main()
