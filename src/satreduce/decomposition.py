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

    changed: bool = False

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
    
    def forced_value(self, literal):
        literal = self.merge_table.find(literal)
        if literal < 0:
            result = self.forced_value(-literal)
            if result is not None:
                return not result
        else:
            return self.forced[literal]


    
    def __force(self, literal):
        literal = self.merge_table.find(literal)
        variable = abs(literal)
        value = literal > 0
        if variable in self.forced:
            if self.forced[variable] != value:
                raise Inconsistency(f"Attempted to force {variable}={value} but it is already {self.forced[variable]}")
        else:
            self.changed = True
            self.forced[variable] = value

    def __merge(self, a, b):
        a = self.merge_table.find(a)
        b = self.merge_table.find(b)
        if a == b:
            return
        self.changed = True
        self.merge_table.merge(a, b)

        for c in a, b:
            c = abs(c)
            if c in self.forced:
                if self.forced[c]:
                    self.__force(c)
                else:
                    self.__force(-c)
    
    def __reduce(self):
        prev = None
        while prev != self.core or self.changed:
            self.changed = False
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
                if not new_clause:
                    raise Inconsistency(f"All literals in {clause} are unsatisfied")
                    
                clause = tuple(sorted(set(map(self.merge_table.find, new_clause))))
                if len(set(map(abs, clause))) < len(clause):
                    continue
                if len(clause) == 1:
                    self.__force(*clause)
                    continue

                if len(clause) == 2:
                    a, b = clause
                    self.implications.add_edge(-a, b)
                    self.implications.add_edge(-b, a)
                new_core.add(clause)

            self.core = tuple(sorted(new_core, key=lambda s: (len(s), s)))
            for component in strongly_connected_components(self.implications):
                if len(component) > 1:
                    forced_values = {self.forced.get(self.merge_table.find(c)) for c in component}
                    forced_values.discard(None)
                    if len(forced_values) > 1:
                        raise Inconsistency(f"Attempted to merge {component} with inconsistent assigned values")

                    target = None
                    for c in component:
                        if target is None:
                            target = c
                        else:
                            self.__merge(target, c)

        self.free = {c for c in self.free if self.merge_table.find(c) == c and c not in self.forced}
        for f in self.free:
            self.implications.add_node(f)
            self.implications.add_node(-f)