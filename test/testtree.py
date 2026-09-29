"""
Shared TestTree fixture helpers, used by both test_filter.py and
test_graph_generation.py. See README.md in this directory for the full
cast of people in testdata/TestTree.gramps and why each one is
included/excluded by the filter.
"""

import os

from gramps.cli.user import User
from gramps.gen.db.utils import import_as_dict

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


def load_test_tree():
    return import_as_dict(TEST_TREE_PATH, User(quiet=True))


def find_handle_by_first_name(database, first_name):
    for person in database.iter_people():
        if person.get_primary_name().get_first_name() == first_name:
            return person.get_handle()
    raise LookupError(f"No person with first name {first_name!r} in TestTree")


def build_role_to_handle(database):
    return {role: find_handle_by_first_name(database, first_name) for role, first_name in ROLE_TO_FIRST_NAME.items()}
