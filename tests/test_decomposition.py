import pytest
from hypothesis import example
from hypothesis import given
from hypothesis import note
from hypothesis import reject
from hypothesis import settings
from hypothesis import strategies as st

from satreduce.booleanequivalence import Inconsistency
from satreduce.decomposition import ReducedSatProblem
from satreduce.minisat import find_solution
from tests.sat_strategies import sat_clauses
from tests.sat_strategies import sat_with_satisfaction
from tests.sat_strategies import unsatisfiable_clauses


@example(([(-1, -2), [-1, 2], [-2, 1]], {1: False, 2: False}))
@example(([(-1,), [-2, 3], [-3, 2]], {1: False, 2: False, 3: False}))
@example(([(-1, -2), [-1, 2], [-2, 1]], {1: False, 2: False}))
@given(sat_with_satisfaction())
def test_should_give_consistent_results(problem):
    clauses, assignment = problem

    reduced = ReducedSatProblem.from_sat(clauses)

    note(repr(reduced))

    for k, v in reduced.forced.items():
        assert assignment[k] == v

    for k, v in assignment.items():
        k2 = reduced.merge_table.find(k)
        v2 = assignment[abs(k2)] ^ (k2 < 0)
        assert v2 == v

    for clause in reduced.core:
        for literal in clause:
            assert reduced.merge_table.find(literal) == literal

    solution = find_solution(reduced.core)

    assignment = {abs(l): l > 0 for l in solution}

    for k, v in reduced.forced.items():
        assert abs(reduced.merge_table.find(k)) in reduced.forced
        assignment[k] = v

    variables = {abs(l) for clause in clauses for l in clause}
    new_assignment = dict(assignment)

    for v in variables:
        v2 = reduced.merge_table.find(v)
        if abs(v2) in assignment:
            if v2 < 0:
                new_assignment[v] = not assignment[abs(v2)]
            else:
                new_assignment[v] = assignment[v2]

    assignment = new_assignment

    note(repr(assignment))

    assigned_literals = {k if v else -k for k, v in assignment.items()}

    for c in clauses:
        merged = set(map(reduced.merge_table.find, c))
        if len(set(map(abs, merged))) < len(merged):
            continue
        assert set(c) & assigned_literals


@example(([(-1, -2), [-1, 2], [-2, 1]], {1: False, 2: False}))
@given(sat_with_satisfaction())
def test_incrementally_reduce_to_empty(problem):
    clauses, assignment = problem

    reduced = ReducedSatProblem.from_sat(clauses)

    for variable, value in assignment.items():
        reduced = reduced.with_extra_clauses([[variable if value else -variable]])
        note(f"{variable}={value} -> {reduced}")
        assert reduced.forced_value(variable) == value
    assert not reduced.core


@pytest.mark.parametrize(
    "eg",
    [
        [[1], [-1]],
        [[1, -2], [-1, 2], [1, 2], [-2]],
        [[-1, -2], [1, 2], [1], [2]],
        [[1, -2], [-1, 2], [1], [-2]],
    ],
)
def test_raises_inconsistency(eg):
    with pytest.raises(Inconsistency):
        ReducedSatProblem.from_sat(eg)


@example(
    [
        [1, -2, 5],
        [-1, 5, 4, 2],
        [1, 3],
        [1, -5, -4],
        [-1, 5],
        [1, -5, 4],
        [2, -3],
        [3, -5],
        [-1],
    ],
)
@settings(max_examples=100)
@given(unsatisfiable_clauses())
def test_eventually_inconsistent(clauses):
    with pytest.raises(Inconsistency):
        problem = ReducedSatProblem.from_sat(clauses)

        while problem.core:  # pragma: no branch
            problem = problem.with_extra_clauses([[problem.core[0][0]]])


def test_children_are_independent():
    p1 = ReducedSatProblem.from_sat([[1, 2, 3, 4]])

    p2 = p1.with_extra_clauses([[1, 2], [-1, -2]])

    assert p2.merge_table.find(2) == -1

    assert p1.merge_table.find(1) == 1
    assert p1.merge_table.find(2) == 2


@example(
    [
        [1, -2, 5],
        [-1, 5, 4, 2],
        [1, 3],
        [1, -5, -4],
        [-1, 5],
        [1, -5, 4],
        [2, -3],
        [3, -5],
        [-1],
    ]
)
@example([[-1]])
@given(sat_clauses())
def test_merged_clauses_are_always_populated(clauses):
    try:
        problem = ReducedSatProblem.from_sat(clauses)
    except Inconsistency:
        reject()

    for k, v in problem.forced.items():
        k2 = problem.merge_table.find(k)
        s = k2 < 0
        k2 = abs(k2)
        assert problem.forced[k2] == s ^ v


def test_forced_value_of_unforced_literal_is_none():
    problem = ReducedSatProblem.from_sat([[1, 2]])

    assert problem.forced_value(1) is None
    assert problem.forced_value(-2) is None
