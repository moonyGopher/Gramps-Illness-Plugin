"""
Tests for the GraphML (yEd) export (`illness_graphml.export_data`), which
writes whichever people survive the active export filter as a GraphML file
following the layout conventions worked out by hand in
test/testdata/TestTree.graphml (see illness_graphml.py's module docstring).

Uses the same TestTree fixture as test_filter.py/test_filter_rule.py, with
the "People medically relevant to <person>" rule as the export filter (the
same mechanism a real GEDCOM/GraphML export in Gramps would use), so the
included people are exactly EXPECTED_INCLUDED_ROLES.
"""

import os
import sys
import unittest
import xml.etree.ElementTree as ET
from typing import Any

import gi

# illness_graphml imports gramps.gui.plug.export (for its export-options box), which pulls in
# GTK; real Gramps always pins this version at its own startup (see gramps/grampsapp.py) before
# loading any plugin, but a standalone test process needs to do it itself, before that first import.
gi.require_version("Gtk", "3.0")

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_TEST_DIR))  # repo root, for illness_graphml
sys.path.insert(0, _TEST_DIR)  # this directory, for testtree

from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.filters import GenericFilter, reload_custom_filters
from gramps.gen.lib import Date
from gramps.gen.proxy import FilterProxyDb
from gramps.gen.relationship import get_relationship_calculator

import illness_graphml as ig
from illness_filter_rule import IsMedicallyRelevantTo
from testtree import EXPECTED_INCLUDED_ROLES, build_role_to_handle, load_test_tree

_GRAPHML_NS = {"g": "http://graphml.graphdrawing.org/xmlns", "y": "http://www.yworks.com/xml/graphml"}


class TestExportData(unittest.TestCase):
    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)
        me_id = cls.db.get_person_from_handle(cls.role_to_handle["Me"]).get_gramps_id()
        rule = IsMedicallyRelevantTo([me_id, "", ""])
        person_filter = GenericFilter()
        person_filter.add_rule(rule)
        cls.filtered_db = FilterProxyDb(cls.db, person_filter)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.path = os.path.join(_TEST_DIR, "_tmp_test_export.graphml")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def _export_and_parse(self):
        ig.export_data(self.filtered_db, self.path, user=None)
        tree = ET.parse(self.path)
        return tree.getroot().find("g:graph", _GRAPHML_NS)

    def _node_label_texts(self, node):
        return [(label.get("fontStyle"), (label.text or "")) for label in node.findall(".//y:NodeLabel", _GRAPHML_NS)]

    def test_writes_well_formed_graphml(self):
        ig.export_data(self.filtered_db, self.path, user=None)
        ET.parse(self.path)  # raises if malformed

    def test_includes_exactly_the_filtered_people(self):
        graph = self._export_and_parse()
        bold_names = {
            label.text.split(" ")[0]
            for node in graph.findall("g:node", _GRAPHML_NS)
            for label in node.findall(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS)
        }
        first_names = {
            self.db.get_person_from_handle(handle).get_primary_name().get_first_name()
            for role, handle in self.role_to_handle.items()
            if role in EXPECTED_INCLUDED_ROLES
        }
        self.assertEqual(bold_names, first_names)

    def test_family_links_form_parent_child_brackets(self):
        graph = self._export_and_parse()
        node_ids = {node.get("id") for node in graph.findall("g:node", _GRAPHML_NS)}
        person_node_ids = {
            node.get("id")
            for node in graph.findall("g:node", _GRAPHML_NS)
            if node.find(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS) is not None
        }
        dot_node_ids = node_ids - person_node_ids
        # Every edge touches exactly one dot and one person - never person-to-person directly.
        for edge in graph.findall("g:edge", _GRAPHML_NS):
            source, target = edge.get("source"), edge.get("target")
            self.assertEqual(
                len({source, target} & dot_node_ids),
                1,
                f"edge {source}->{target} should connect exactly one family dot and one person",
            )

    def test_female_gets_rounded_bordeaux_box(self):
        graph = self._export_and_parse()
        me_node = self._find_node_by_name(graph, "MyFirstName")
        shape = me_node.find(".//y:Shape", _GRAPHML_NS).get("type")
        border = me_node.find(".//y:BorderStyle", _GRAPHML_NS).get("color")
        self.assertEqual(shape, "roundrectangle")
        self.assertEqual(border, "#800020")

    def test_male_gets_square_navy_box(self):
        graph = self._export_and_parse()
        node = self._find_node_by_name(graph, "MyBrothersFirstName")
        shape = node.find(".//y:Shape", _GRAPHML_NS).get("type")
        border = node.find(".//y:BorderStyle", _GRAPHML_NS).get("color")
        self.assertEqual(shape, "rectangle")
        self.assertEqual(border, "#000080")

    def test_boxes_are_filled_white(self):
        graph = self._export_and_parse()
        for node in graph.findall("g:node", _GRAPHML_NS):
            fill = node.find(".//y:Fill", _GRAPHML_NS)
            if fill is not None and fill.get("color") != "#000000":  # skip the black family dots
                self.assertEqual(fill.get("color"), "#FFFFFF")

    def test_birth_and_death_rows_only_appear_when_the_data_exists(self):
        graph = self._export_and_parse()
        # MomsFathersFather has birth, death, cause of death and an illness recorded.
        node = self._find_node_by_name(graph, "MomsFathersFathersFirstName")
        texts = " ".join(text for _style, text in self._node_label_texts(node))
        self.assertIn(ig._BIRTH_SYMBOL, texts)
        self.assertIn(ig._DEATH_SYMBOL, texts)
        self.assertIn("(Cancer)", texts)
        self.assertIn("- Asthma", texts)

        # MyBrother has none of that - only the name label should be present.
        brother = self._find_node_by_name(graph, "MyBrothersFirstName")
        self.assertEqual(len(brother.findall(".//y:NodeLabel", _GRAPHML_NS)), 1)

    def test_illnesses_are_listed_oldest_first(self):
        graph = self._export_and_parse()
        node = self._find_node_by_name(graph, "MyFirstName")
        texts = [text for _style, text in self._node_label_texts(node)]
        illness_text = next(text for text in texts if text.startswith("- My"))
        self.assertLess(illness_text.index("MyFirstIllness"), illness_text.index("MySecondIllness"))

    def test_cause_of_death_is_right_aligned_under_the_death_date(self):
        graph = self._export_and_parse()
        node = self._find_node_by_name(graph, "MomsFathersFathersFirstName")
        cause_label = next(label for label in node.findall(".//y:NodeLabel", _GRAPHML_NS) if label.text == "(Cancer)")
        self.assertEqual(cause_label.get("alignment"), "right")

    def test_cause_of_death_sits_directly_under_the_death_date(self):
        # "Directly under" = the same tight gap used between consecutive illness lines (0 extra
        # pixels beyond the death date's own row height), not the larger gap used elsewhere.
        graph = self._export_and_parse()
        node = self._find_node_by_name(graph, "MomsFathersFathersFirstName")
        death_label = next(
            label for label in node.findall(".//y:NodeLabel", _GRAPHML_NS) if (label.text or "").startswith("✝")
        )
        cause_label = next(label for label in node.findall(".//y:NodeLabel", _GRAPHML_NS) if label.text == "(Cancer)")
        death_y = float(death_label.get("y"))
        death_height = float(death_label.get("height"))
        cause_y = float(cause_label.get("y"))
        self.assertEqual(cause_y, death_y + death_height)

    def test_every_box_uses_the_same_width(self):
        graph = self._export_and_parse()
        widths = {
            node.find(".//y:Geometry", _GRAPHML_NS).get("width")
            for node in graph.findall("g:node", _GRAPHML_NS)
            if node.find(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS) is not None
        }
        self.assertEqual(len(widths), 1)

    def test_names_are_on_a_single_line(self):
        graph = self._export_and_parse()
        for node in graph.findall("g:node", _GRAPHML_NS):
            label = node.find(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS)
            if label is not None:
                self.assertNotIn("\n", label.text or "")

    def _find_node_by_name(self, graph, first_name):
        for node in graph.findall("g:node", _GRAPHML_NS):
            label = node.find(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS)
            if label is not None and (label.text or "").startswith(first_name):
                return node
        raise LookupError(f"no node found for {first_name!r}")


class TestPersonNameText(unittest.TestCase):
    db: Any

    @classmethod
    def setUpClass(cls):
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_returns_real_name_on_one_line_when_no_home_person_given(self):
        mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
        self.assertEqual(ig._person_name_text(self.db, mother, None, None), "MyMothersFirstName MyMothersLastName")

    def test_returns_relationship_to_home_person_when_enabled(self):
        # Compares against the relationship calculator's own output rather than a hardcoded
        # literal like "Mutter": that term is locale-dependent, same as Gramps' date/name display.
        me = self.db.get_person_from_handle(self.role_to_handle["Me"])
        mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
        calculator = get_relationship_calculator()
        expected = calculator.get_one_relationship(self.db, me, mother)
        self.assertEqual(ig._person_name_text(self.db, mother, me, calculator), expected)

    def test_home_person_itself_is_labelled_me(self):
        me = self.db.get_person_from_handle(self.role_to_handle["Me"])
        calculator = get_relationship_calculator()
        self.assertEqual(ig._person_name_text(self.db, me, me, calculator), ig._("Me"))


class _FakeDbState:
    """Minimal stand-in for gramps.gen.dbstate.DbState, enough for GraphMLWriterOptionBox."""

    def __init__(self, db):
        self.db = db


class TestGraphMLWriterOptionBox(unittest.TestCase):
    db: Any

    @classmethod
    def setUpClass(cls):
        reload_custom_filters()
        cls.db = load_test_tree()
        cls.role_to_handle = build_role_to_handle(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _make_box(self):
        me = self.db.get_person_from_handle(self.role_to_handle["Me"])
        return ig.GraphMLWriterOptionBox(me, _FakeDbState(self.db), None)

    def test_relationship_labels_default_to_off(self):
        self.assertFalse(self._make_box().use_relationship_labels)

    def test_checkbox_toggles_use_relationship_labels(self):
        box = self._make_box()
        box.get_option_box()
        box._relationship_labels_check.set_active(True)
        box.parse_options()
        self.assertTrue(box.use_relationship_labels)

    def test_export_data_uses_relationship_labels_from_a_parsed_option_box(self):
        me_id = self.db.get_person_from_handle(self.role_to_handle["Me"]).get_gramps_id()
        rule = IsMedicallyRelevantTo([me_id, "", ""])
        person_filter = GenericFilter()
        person_filter.add_rule(rule)
        filtered_db = FilterProxyDb(self.db, person_filter)

        fake_option_box = _FakeRelationshipOptionBox(filtered_db)
        path = os.path.join(_TEST_DIR, "_tmp_test_export_relationship.graphml")
        # _name_lines() needs a Home Person to compute relationship terms against.
        self.db.set_default_person_handle(self.role_to_handle["Me"])
        try:
            ig.export_data(self.db, path, user=None, option_box=fake_option_box)
            tree = ET.parse(path)
            graph = tree.getroot().find("g:graph", _GRAPHML_NS)
            bold_texts = {
                label.text
                for node in graph.findall("g:node", _GRAPHML_NS)
                for label in node.findall(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS)
            }
            # Compared against the calculator's/translator's own output, not a hardcoded
            # literal like "Mutter": both are locale-dependent.
            me = self.db.get_person_from_handle(self.role_to_handle["Me"])
            mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
            calculator = get_relationship_calculator()
            self.assertIn(calculator.get_one_relationship(self.db, me, mother), bold_texts)
            self.assertIn(ig._("Me"), bold_texts)
        finally:
            self.db.set_default_person_handle(None)
            if os.path.exists(path):
                os.remove(path)


class _FakeRelationshipOptionBox:
    """Duck-types just enough of the option_box interface export_data() relies on."""

    use_relationship_labels = True

    def __init__(self, filtered_db):
        self._filtered_db = filtered_db

    def parse_options(self):
        pass

    def get_filtered_database(self, _database, progress=None, preview=False):
        return self._filtered_db


class TestDateText(unittest.TestCase):
    def test_returns_none_for_empty_date(self):
        self.assertIsNone(ig._date_text(Date()))

    def test_formats_a_date_the_same_way_gramps_itself_currently_does(self):
        # Deliberately not asserting a specific string: the exact rendering
        # depends on Gramps' currently configured date format, which is
        # locale-specific (see _date_text's docstring) - just confirm this
        # doesn't add/change anything on top of Gramps' own date displayer.
        date = Date()
        date.set_yr_mon_day(1900, 4, 4)
        self.assertEqual(ig._date_text(date), date_displayer.display(date))


class TestEventSortKey(unittest.TestCase):
    def test_dated_events_sort_oldest_first(self):
        early, late = _FakeEvent("1990-01-01", "B"), _FakeEvent("2000-01-01", "A")
        self.assertEqual(sorted([late, early], key=ig._event_sort_key), [early, late])

    def test_undated_events_sort_alphabetically_by_description(self):
        zebra, apple = _FakeEvent(None, "Zebra"), _FakeEvent(None, "Apple")
        self.assertEqual(sorted([zebra, apple], key=ig._event_sort_key), [apple, zebra])

    def test_dated_events_always_sort_before_undated_ones(self):
        dated, undated = _FakeEvent("1990-01-01", "Zebra"), _FakeEvent(None, "Apple")
        self.assertEqual(sorted([undated, dated], key=ig._event_sort_key), [dated, undated])


class _FakeEvent:
    def __init__(self, yyyy_mm_dd, description):
        date = Date()
        if yyyy_mm_dd:
            year, month, day = (int(part) for part in yyyy_mm_dd.split("-"))
            date.set_yr_mon_day(year, month, day)
        self._date = date
        self._description = description

    def get_date_object(self):
        return self._date

    def get_description(self):
        return self._description

    def __repr__(self):
        return f"_FakeEvent({self._description!r})"


class TestComputeGenerations(unittest.TestCase):
    def test_normalizes_oldest_generation_to_zero(self):
        # grandparent -> parent -> child, built as minimal fake objects exposing just .handle
        grandparent, parent, child = _FakePerson("gp"), _FakePerson("p"), _FakePerson("c")
        links = [
            {"family_handle": "f1", "parents": ["gp"], "children": ["p"]},
            {"family_handle": "f2", "parents": ["p"], "children": ["c"]},
        ]
        generations = ig._compute_generations([grandparent, parent, child], links)
        self.assertEqual(generations, {"gp": 0, "p": 1, "c": 2})

    def test_isolated_person_defaults_to_generation_zero(self):
        lone = _FakePerson("lone")
        self.assertEqual(ig._compute_generations([lone], []), {"lone": 0})


class _FakePerson:
    def __init__(self, handle):
        self.handle = handle


if __name__ == "__main__":
    unittest.main()
