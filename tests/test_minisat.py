from satreduce.minisat import is_satisfiable


def test_empty_clause_check():
    assert not is_satisfiable([[]])
