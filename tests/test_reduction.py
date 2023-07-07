import operator
from hypothesis import assume, given, strategies as st, example
from satreduce.reducer import shrink_sat
import pytest
import satreduce.minisat as ms


@st.composite
def sat_clauses(draw):
    n_variables = draw(st.integers(1, 10))
    variables = range(1, n_variables + 1)

    literal = st.builds(operator.mul, st.sampled_from(variables), st.sampled_from((-1, 1)))

    return draw(st.lists(
        st.lists(literal, unique=True, min_size=1)
    , min_size=1))


@example([[1]])
@given(sat_clauses())
def test_shrink_to_one_single_literal_clause(clauses):
    result = shrink_sat(clauses, any)
    assert result == ((1,),)


@pytest.mark.parametrize('n', range(2, 11))
def test_can_shrink_chain_to_two(n):
    chain = [
        [-i, i + 1] for i in range(1, n + 1)
    ]
    def test(clauses):
        clauses = list(clauses)
        return ms.is_satisfiable(clauses) and ms.is_satisfiable(clauses + [[1], [n]]) and ms.is_satisfiable(clauses + [[-1], [-n]]) and not ms.is_satisfiable(clauses + [[1], [-n]])
    
    assert test(chain)

    shrunk = shrink_sat(chain, test)

    assert shrunk == ((-1, n),)


@st.composite
def unsatisfiable_clauses(draw):
    clauses = draw(sat_clauses())
    assume(clauses)

    while True:
        sol = ms.find_solution(clauses)
        if sol is None:
            return clauses

        subset = draw(st.lists(st.sampled_from(sol), min_size=1, unique=True))
        clauses.append([-n for n in subset])


@given(unsatisfiable_clauses())
def test_reduces_unsatisfiable_to_trivial(unsat):
    def test(clauses):
        return clauses and all(clauses) and not ms.is_satisfiable(clauses)
    
    shrunk = shrink_sat(unsat, test)

    assert shrunk == ((-1,), (1,))


@st.composite
def has_unique_solution(draw):
    clauses = draw(sat_clauses())
    sol = ms.find_solution(clauses)
    assume(sol is not None)

    while True:
        other_sol = ms.find_solution(clauses + [[-l for l in sol]])
        if other_sol is None:
            assert ms.is_satisfiable(clauses)
            return clauses
        
        to_rule_out = sorted(set(other_sol) - set(sol))
        assert to_rule_out
        subset = draw(st.lists(st.sampled_from(to_rule_out), min_size=1, unique=True))
        clauses.append([-n for n in subset])


@given(has_unique_solution())
def test_reduces_unique_satisfiable_to_trivial(unique_sat):
    def test(clauses):
        if not clauses:
            return False
        sol = ms.find_solution(clauses)
        if sol is None:
            return False
        return not ms.is_satisfiable(list(clauses) + [[-l for l in sol]])
    
    shrunk = shrink_sat(unique_sat, test)
    assert test(shrunk)

    assert shrunk == ((1,),)
