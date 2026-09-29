# Tests

- `test_filter.py` tests `illness_filter.filter_relevant_people()` against
  the TestTree fixture below.
- `test_graph_generation.py` tests `illness_graph.build_graph_data()` (node
  labels, edges, couples, generation ordering) against the same fixture.
- `testtree.py` holds the shared fixture-loading helpers used by both.

Run all of them with:

```sh
python3 -m unittest discover -s test -p "test_*.py" -v
```

(from the repository root, so that `illness_filter` and `illness_graph` are
importable)

## TestTree data for the test

With "Me" as the central person and the default depth of 3 generations,
the following persons in the TestTree should be included by the filter
(blood relatives - ancestors, their siblings and children, and Me's own
descendants):
- Me
- MyBrother (Me's own sibling)
- MyChild
- MyFather
- MyMother
- MomsFather
- MomsMom
- MomsSister (Mom's sibling)
- MomsBrother (Mom's sibling)
- MomsSistersChild (Mom's sister's child, i.e. Me's cousin)
- MomsFathersFather
- MomsFathersMother

The following persons are only connected to Me by marriage (in-laws) and
should be filtered out:
- HusbandsFather
- HusbandsMother
- MomsSistersHusband
- MyHusband