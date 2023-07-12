import operator

import pytest
from hypothesis import assume
from hypothesis import example
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

import satreduce.minisat as ms
from satreduce.reducer import NotFound
from satreduce.reducer import SATShrinker
from satreduce.reducer import canonicalise
from satreduce.reducer import shrink_sat
from tests.sat_strategies import has_unique_solution
from tests.sat_strategies import sat_clauses
from tests.sat_strategies import unsatisfiable_clauses


@example([[1]])
@given(sat_clauses())
def test_shrink_to_one_single_literal_clause(clauses):
    result = shrink_sat(clauses, any)
    assert result == ((1,),)


@pytest.mark.parametrize("n", range(2, 11))
def test_can_shrink_chain_to_two(n):
    chain = [[-i, i + 1] for i in range(1, n + 1)]

    def test(clauses):
        clauses = list(clauses)
        return (
            ms.is_satisfiable(clauses)
            and ms.is_satisfiable(clauses + [[1], [n]])
            and ms.is_satisfiable(clauses + [[-1], [-n]])
            and not ms.is_satisfiable(clauses + [[1], [-n]])
        )

    assert test(chain)

    shrunk = shrink_sat(chain, test)

    assert shrunk == ((-1, n),)


@given(unsatisfiable_clauses())
def test_reduces_unsatisfiable_to_trivial(unsat):
    def test(clauses):
        return clauses and all(clauses) and not ms.is_satisfiable(clauses)

    shrunk = shrink_sat(unsat, test)

    assert shrunk == ((-1,), (1,))


@example([[-1], [-2], [-3], [-4, -5], [4, 5], [-6], [4, -5]])
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


def test_does_not_print_if_debug_disabled(capsys):
    reducer = SATShrinker([[1]], lambda x: True)

    reducer.debug("hi")

    captured = capsys.readouterr()

    assert captured.out == ""


def test_debug_prints_if_debug_enabled(capsys):
    reducer = SATShrinker([[1]], lambda x: True, debug=True)

    reducer.debug("hi")

    captured = capsys.readouterr()

    assert captured.out == "hi\n"


def test_can_reduce_to_a_component():
    reducer = SATShrinker([[1, 2], [3, 4, 5]], lambda x: len(x) >= 1)

    reducer.move_to_components()

    assert reducer.current == ((1, 2),)


def test_can_reduce_to_all_components():
    reducer = SATShrinker([[1, 2], [3, 4, 5]], lambda x: any(3 in y for y in x))

    reducer.move_to_components()

    assert reducer.current == ((3, 4, 5),)


def test_can_reduce_to_no_components():
    reducer = SATShrinker([[1, 2], [3, 4, 5]], lambda x: len(x) == 2)

    reducer.move_to_components()

    assert len(reducer.current) == 2


def test_raises_if_initial_invalid():
    with pytest.raises(ValueError):
        shrink_sat([[1]], lambda x: False)


def test_can_remove_a_single_literal():
    reducer = SATShrinker(
        [[1, 2, 3]], lambda x: len(x) >= 1 and 1 in x[0] and 3 in x[0]
    )

    reducer.delete_literals_from_clauses()

    assert reducer.current == ((1, 3),)


@pytest.mark.parametrize("parallel", (1, 2))
def test_find_first_finds_first(parallel):
    reducer = SATShrinker([[1, 2, 3, 4]], lambda x: True, parallelism=parallel)

    i = reducer.find_first(range(10), lambda x: x >= 5)

    assert i == 5


@pytest.mark.parametrize("parallel", (1, 2))
def test_find_first_finds_first_raises_on_missing(parallel):
    reducer = SATShrinker([[1, 2, 3, 4]], lambda x: True, parallelism=parallel)

    with pytest.raises(NotFound):
        reducer.find_first(range(10), lambda x: False)


@pytest.mark.parametrize("parallel", (1, 2))
def test_find_first_finds_first_raises_on_empty(parallel):
    reducer = SATShrinker([[1, 2, 3, 4]], lambda x: True, parallelism=parallel)

    with pytest.raises(NotFound):
        reducer.find_first([], ...)


def test_deleting_literals():
    reducer = SATShrinker(
        [
            [1, 2],
            [3, 4],
            [5, 6],
            [7, 8],
        ],
        lambda c: len(c) == 4 and all(c),
    )

    reducer.delete_literals()

    for c in reducer.current:
        assert len(c) == 1


@given(sat_clauses())
def test_shrink_to_original(sat):
    sat = canonicalise(sat)

    assert shrink_sat(sat, lambda t: t == sat) == sat


@given(sat_clauses())
def test_shrink_to_non_trivial(sat):
    assert shrink_sat(sat, lambda t: len(t) >= 1 and all(t)) == ((1,),)
