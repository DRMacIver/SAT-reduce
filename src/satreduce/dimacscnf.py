def dimacs_to_clauses(contents):
    clauses = []
    for l in contents.splitlines():
        l = l.strip()
        if l.startswith("c"):
            continue
        if l.startswith("p"):
            continue
        clause = list(map(int, l.strip().split()))
        assert clause[-1] == 0
        clause.pop()
        clauses.append(clause)
    return clauses


def clauses_to_dimacs(clauses):
    n_variables = max(abs(l) for c in clauses for l in c)

    parts = [f"p cnf {n_variables} {len(clauses)}"]

    for c in clauses:
        parts.append(" ".join(map(repr, list(c) + [0])))

    return "\n".join(parts)
