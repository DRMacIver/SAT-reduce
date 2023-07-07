import attrs
from satreduce.booleanequivalence import BooleanEquivalence, Inconsistency
from networkx import DiGraph, strongly_connected_components
from typing import Sequence
from copy import deepcopy
from satreduce.minisat import find_solution

@attrs.define
class ReducedSatProblem:
    merge_table: BooleanEquivalence
    forced: dict[int, bool]
    free: set[int]
    core: tuple[tuple[int, ...], ...]
    implications: DiGraph

    @classmethod
    def from_sat(cls, problem: Sequence[Sequence[int]]):
        problem = tuple(map(tuple, problem))
        result = ReducedSatProblem(
            merge_table=BooleanEquivalence(),
            forced={},
            free={abs(l) for clause in problem for l in clause},
            core=problem,
            implications=DiGraph(),
        )
        result.__reduce()
        return result
    
    def with_extra_clauses(self, clauses):
        result = deepcopy(self)
        result.core = result.core + tuple(map(tuple, clauses))
        result.__reduce()
        return result
    
    def __reduce(self):
        prev = None
        changed = True
        while prev != self.core or changed:
            changed = False
            prev = self.core

            new_core = set()

            self.implications = DiGraph()

            for clause in self.core:
                clause = tuple(sorted(set(map(self.merge_table.find, clause))))

                new_clause = []
                redundant = False
                for literal in clause:
                    variable = abs(literal)
                    value = literal > 0
                    if variable in self.forced:
                        if self.forced[variable] == value:
                            redundant = True
                            break
                    else:
                        new_clause.append(literal)
                if redundant:
                    continue
                    
                clause = tuple(sorted(set(map(self.merge_table.find, new_clause))))
                if len(set(map(abs, clause))) < len(clause):
                    continue
                if len(clause) == 1:
                    literal, = clause
                    variable = abs(literal)
                    value = literal > 0
                    if variable not in self.forced:
                        self.forced[variable] = value
                    elif value != self.forced[variable]:
                        raise Inconsistency(f"Forced {variable} = {value} but previously forced to {self.forced[variable]}")
                    continue

                if len(clause) == 2:
                    a, b = clause
                    self.implications.add_edge(-a, b)
                    self.implications.add_edge(-b, a)
                new_core.add(clause)

            self.core = tuple(sorted(new_core, key=lambda s: (len(s), s)))
            for component in strongly_connected_components(self.implications):
                if len(component) > 1:
                    self.merge_table.merge_all(component)
                    changed = True

        self.free = {c for c in self.free if self.merge_table.find(c) == c and c not in self.forced}
        for f in self.free:
            self.implications.add_node(f)
            self.implications.add_node(-f)