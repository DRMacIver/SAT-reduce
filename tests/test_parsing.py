from hypothesis import given

from satreduce.dimacscnf import clauses_to_dimacs
from satreduce.dimacscnf import dimacs_to_clauses
from tests.sat_strategies import sat_clauses


@given(sat_clauses())
def test_parsing_round_trips(clauses):
    assert dimacs_to_clauses(clauses_to_dimacs(clauses)) == clauses


def test_skips_lines_with_comments():
    assert dimacs_to_clauses(clauses_to_dimacs([[1]]) + "\nc foo") == [[1]]
