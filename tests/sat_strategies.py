import operator

import hypothesis.strategies as st
from hypothesis import assume

import satreduce.minisat as ms


@st.composite
def sat_clauses(draw, min_clause_size=1):
    n_variables = draw(st.integers(min_clause_size, min(10, min_clause_size * 2)))
    variables = range(1, n_variables + 1)

    literal = st.builds(
        operator.mul, st.sampled_from(variables), st.sampled_from((-1, 1))
    )

    return draw(
        st.lists(st.lists(literal, unique_by=abs, min_size=min_clause_size), min_size=1)
    )


@st.composite
def unsatisfiable_clauses(draw, min_clause_size=1):
    clauses = draw(sat_clauses(min_clause_size=min_clause_size))
    assume(clauses)

    while True:
        sol = ms.find_solution(clauses)
        if sol is None:
            return clauses
        assert len(sol) >= min_clause_size, (sol, clauses)
        subset = draw(
            st.lists(st.sampled_from(sol), min_size=min_clause_size, unique=True)
        )
        clauses.append([-n for n in subset])


@st.composite
def has_unique_solution(draw):
    clauses = draw(sat_clauses(min_clause_size=2))
    sol = ms.find_solution(clauses)
    assume(sol is not None)

    while True:
        other_sol = ms.find_solution(clauses + [[-l for l in sol]])
        if other_sol is None:
            assert ms.is_satisfiable(clauses)
            return clauses

        to_rule_out = sorted(set(other_sol) - set(sol))
        assert to_rule_out
        subset = draw(
            st.lists(
                st.sampled_from(to_rule_out),
                min_size=min(2, len(to_rule_out)),
                unique=True,
            )
        )
        clauses.append([-n for n in subset])


@st.composite
def sat_with_satisfaction(draw):
    n = draw(st.integers(1, 20))

    variables = range(1, n + 1)
    assignments = draw(st.lists(st.booleans(), min_size=n, max_size=n))

    vector = [i if b else -i for i, b in zip(variables, assignments, strict=True)]

    clauses = draw(
        st.lists(
            st.lists(st.sampled_from(vector), unique=True, max_size=4, min_size=1).map(
                tuple
            ),
            min_size=1,
            unique=True,
        )
    )

    if len(variables) > 1:
        merges = draw(
            st.lists(
                st.lists(
                    st.sampled_from(variables), unique=True, min_size=2, max_size=2
                )
            )
        )

        for a, b in merges:
            if assignments[a - 1] != assignments[b - 1]:
                b = -b
            clauses.extend([[-a, b], [-b, a]])

    used_variables = set()
    for c in clauses:
        used_variables.update(map(abs, c))

    assume(len(used_variables) == n)

    return (clauses, dict(zip(variables, assignments)))
