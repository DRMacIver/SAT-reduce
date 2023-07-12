from satreduce.minisat import find_solution
from satreduce.minisat import is_satisfiable


def test_empty_clause_check():
    assert not is_satisfiable([[]])


def test_empty_clause_check_solution():
    assert find_solution([[]]) is None
