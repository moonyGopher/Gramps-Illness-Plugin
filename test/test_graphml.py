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

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_TEST_DIR))  # repo root, for illness_graphml
sys.path.insert(0, _TEST_DIR)  # this directory, for testtree

from gramps.gen.filters import GenericFilter
from gramps.gen.lib import Date
from gramps.gen.proxy import FilterProxyDb

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
            label.text.split(" \n")[0]
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

    def _find_node_by_name(self, graph, first_name):
        for node in graph.findall("g:node", _GRAPHML_NS):
            label = node.find(".//y:NodeLabel[@fontStyle='bold']", _GRAPHML_NS)
            if label is not None and (label.text or "").startswith(first_name):
                return node
        raise LookupError(f"no node found for {first_name!r}")


class TestDateText(unittest.TestCase):
    def test_returns_none_for_empty_date(self):
        self.assertIsNone(ig._date_text(Date()))

    def test_formats_full_date_numerically(self):
        date = Date()
        date.set_yr_mon_day(1900, 4, 4)
        self.assertEqual(ig._date_text(date), "04.04.1900")


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
