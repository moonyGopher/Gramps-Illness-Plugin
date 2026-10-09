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

    def test_full_name_mode_returns_given_and_surname_on_one_line(self):
        mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
        text = ig._person_name_text(self.db, mother, ig._LABEL_MODE_FULL_NAME, None, None)
        self.assertEqual(text, "MyMothersFirstName MyMothersLastName")

    def test_first_name_mode_returns_just_the_given_name(self):
        mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
        text = ig._person_name_text(self.db, mother, ig._LABEL_MODE_FIRST_NAME, None, None)
        self.assertEqual(text, "MyMothersFirstName")

    def test_relationship_mode_returns_the_relationship_to_the_home_person(self):
        # Compares against the relationship calculator's own output rather than a hardcoded
        # literal like "Mutter": that term is locale-dependent, same as Gramps' date/name display.
        me = self.db.get_person_from_handle(self.role_to_handle["Me"])
        mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
        calculator = get_relationship_calculator()
        expected = calculator.get_one_relationship(self.db, me, mother)
        text = ig._person_name_text(self.db, mother, ig._LABEL_MODE_RELATIONSHIP, me, calculator)
        self.assertEqual(text, expected)

    def test_relationship_mode_falls_back_to_full_name_without_a_home_person(self):
        mother = self.db.get_person_from_handle(self.role_to_handle["MyMother"])
        text = ig._person_name_text(self.db, mother, ig._LABEL_MODE_RELATIONSHIP, None, None)
        self.assertEqual(text, "MyMothersFirstName MyMothersLastName")

    def test_home_person_itself_is_labelled_me_in_relationship_mode(self):
        me = self.db.get_person_from_handle(self.role_to_handle["Me"])
        calculator = get_relationship_calculator()
        text = ig._person_name_text(self.db, me, ig._LABEL_MODE_RELATIONSHIP, me, calculator)
        self.assertEqual(text, ig._("Me"))


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

    def test_label_mode_defaults_to_full_name(self):
        self.assertEqual(self._make_box().label_mode, ig._LABEL_MODE_FULL_NAME)

    def test_selecting_a_radio_button_updates_label_mode(self):
        box = self._make_box()
        # Keep the returned container alive: GTK's radio-group exclusivity depends on the
        # buttons staying parented, same as they would in the real export dialog (which keeps
        # this box around for as long as the dialog is open) - an orphaned button is never
        # excluded from its group's sibling buttons, so a discarded box would defeat this test.
        container = box.get_option_box()  # noqa: F841 - keep alive, see comment above
        box._label_mode_buttons[ig._LABEL_MODE_FIRST_NAME].set_active(True)
        box.parse_options()
        self.assertEqual(box.label_mode, ig._LABEL_MODE_FIRST_NAME)

    def test_export_data_uses_the_label_mode_from_a_parsed_option_box(self):
        me_id = self.db.get_person_from_handle(self.role_to_handle["Me"]).get_gramps_id()
        rule = IsMedicallyRelevantTo([me_id, "", ""])
        person_filter = GenericFilter()
        person_filter.add_rule(rule)
        filtered_db = FilterProxyDb(self.db, person_filter)

        fake_option_box = _FakeLabelModeOptionBox(filtered_db, ig._LABEL_MODE_RELATIONSHIP)
        path = os.path.join(_TEST_DIR, "_tmp_test_export_relationship.graphml")
        # _person_name_text() needs a Home Person to compute relationship terms against.
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


class _FakeLabelModeOptionBox:
    """Duck-types just enough of the option_box interface export_data() relies on."""

    def __init__(self, filtered_db, label_mode):
        self._filtered_db = filtered_db
        self.label_mode = label_mode

    def parse_options(self):
        pass

    def get_filtered_database(self, _database, progress=None, preview=False):
        return self._filtered_db


class TestDateText(unittest.TestCase):
    def test_returns_none_for_empty_date(self):
        self.assertIsNone(ig._date_text(Date()))

    def test_formats_using_the_locale_preferred_numeric_format(self):
        # Deliberately not asserting a specific string: the exact rendering is locale-specific
        # (e.g. "4.4.1900" for German, "4/4/1900" for English) - just confirm this matches
        # Gramps' own format index 1 (its "locale-preferred numerical format", guaranteed to
        # exist for every language unlike most other format indices - see _date_text's
        # docstring), regardless of whatever format happens to be globally configured.
        date = Date()
        date.set_yr_mon_day(1900, 4, 4)
        original_format = date_displayer.format
        date_displayer.set_format(1)
        try:
            expected = date_displayer.display(date)
        finally:
            date_displayer.set_format(original_format)
        self.assertEqual(ig._date_text(date), expected)

    def test_does_not_permanently_change_the_configured_format(self):
        date = Date()
        date.set_yr_mon_day(1900, 4, 4)
        original_format = date_displayer.format
        ig._date_text(date)
        self.assertEqual(date_displayer.format, original_format)


class TestWrapLine(unittest.TestCase):
    def test_short_text_is_not_wrapped(self):
        self.assertEqual(ig._wrap_line("- Flu (2020)", 1000), ["- Flu (2020)"])

    def test_long_text_wraps_onto_multiple_lines_within_the_width(self):
        text = "- " + " ".join(["Word"] * 20)
        max_width = 150.0
        lines = ig._wrap_line(text, max_width)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(ig._text_width(line), max_width)

    def test_reassembled_wrapped_text_contains_the_same_words(self):
        text = "- " + " ".join(["Word"] * 20)
        lines = ig._wrap_line(text, 150.0)
        self.assertEqual(" ".join(lines).split(), text.split())

    def test_continuation_lines_get_the_hanging_indent_not_the_first_line(self):
        text = "- " + " ".join(["Word"] * 20)
        lines = ig._wrap_line(text, 150.0, hanging_indent="  ")
        self.assertGreater(len(lines), 1)
        self.assertFalse(lines[0].startswith("  "))
        for line in lines[1:]:
            self.assertTrue(line.startswith("  "))


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


class TestComputeBoxWidth(unittest.TestCase):
    def test_uses_the_name_when_it_is_wider_than_any_date_row(self):
        long_name = "A" * 50
        rows = [ig._Row([("* 2000", "left"), ("✝ 2080", "right")], is_date_row=True)]
        width = ig._compute_box_width([long_name], [rows])
        self.assertAlmostEqual(width, ig._text_width(long_name) + ig._LEFT_MARGIN + ig._SIDE_MARGIN)

    def test_uses_the_date_row_when_it_is_wider_than_any_name(self):
        short_name = "Jo"
        long_birth, long_death = "* " + "1" * 40, "✝ " + "2" * 40
        rows = [ig._Row([(long_birth, "left"), (long_death, "right")], is_date_row=True)]
        width = ig._compute_box_width([short_name], [rows])
        self.assertAlmostEqual(width, ig._date_row_width([(long_birth, "left"), (long_death, "right")]))

    def test_never_narrower_than_the_minimum(self):
        width = ig._compute_box_width(["Jo"], [[]])
        self.assertEqual(width, ig._BOX_MIN_WIDTH)


class TestDateRowWidth(unittest.TestCase):
    def test_single_cell_uses_its_own_width_plus_margins_on_both_sides(self):
        width = ig._date_row_width([("* 2000", "left")])
        self.assertAlmostEqual(width, ig._text_width("* 2000") + 2 * ig._LEFT_MARGIN)

    def test_two_cells_add_up_with_a_gap_between_them(self):
        width = ig._date_row_width([("* 2000", "left"), ("✝ 2080", "right")])
        expected = ig._text_width("* 2000") + ig._DATE_GAP + ig._text_width("✝ 2080") + 2 * ig._LEFT_MARGIN
        self.assertAlmostEqual(width, expected)


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
