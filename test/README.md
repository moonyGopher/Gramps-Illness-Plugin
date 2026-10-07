# Tests

- `test_filter.py` tests `illness_filter.filter_relevant_people()` against
  the TestTree fixture below.
- `test_filter_rule.py` tests `illness_filter_rule.IsMedicallyRelevantTo`
  (the Gramps Person filter rule wrapping that same filter) against the same
  fixture.
- `test_graphml.py` tests `illness_graphml.export_data()` (the GraphML (yEd)
  export) against the same fixture, filtered the same way.
- `testtree.py` holds the shared fixture-loading helpers used by all three.

Run all of them with:

```sh
python3 -m unittest discover -s test -p "test_*.py" -v
```

(from the repository root, so that `illness_filter`, `illness_filter_rule`
and `illness_graphml` are importable)

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