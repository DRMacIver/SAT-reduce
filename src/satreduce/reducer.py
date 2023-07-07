import hashlib
from collections import defaultdict
from functools import wraps

from satreduce.booleanequivalence import Inconsistency
from satreduce.decomposition import ReducedSatProblem


def shrink_sat(clauses, test_function):
    shrinker = SATShrinker(clauses, test_function)
    shrinker.reduce()
    return shrinker.current


def reduction_pass(fn):
    @wraps(fn)
    def accept(self):
        self.debug(fn.__name__)
        prev = self.current
        fn(self)
        if prev is not self.current:
            self.house_keeping_shrinks()

    return accept


class SATShrinker:
    def __init__(self, starting_point, test_function, debug=False):
        self.current = self.canonicalise(starting_point)
        self.__test_function = test_function
        self.__cache = {}
        self.__debug = debug

        if not self.test_function(self.current):
            raise ValueError("Initial argument does not satisfy test.")

    def debug(self, *args, **kwargs):
        if self.__debug:
            print(*args, **kwargs)

    def reduce(self):
        prev = None
        while prev is not self.current:
            prev = self.current
            self.house_keeping_shrinks()
            self.delete_variables()
            self.delete_clauses()
            self.merge_variables()
            self.delete_literals_from_clauses()

    def house_keeping_shrinks(self):
        self.replace_with_core()
        self.move_to_components()
        self.renumber_variables()

    def replace_with_core(self):
        try:
            self.test_function(ReducedSatProblem.from_sat(self.current).core)
        except Inconsistency:
            pass

    def move_to_components(self):
        merges = UnionFind()

        for clause in self.current:
            merges.merge_all(map(abs, clause))

        components = list(merges.partitions())
        if len(components) <= 1:
            return

        components.sort(key=len)

        for component in components:
            component = set(component)
            attempt = [c for c in self.current if any(abs(l) in component for l in c)]
            if self.test_function(attempt):
                return

    @reduction_pass
    def delete_variables(self):
        i = 0
        while True:
            variables = sorted({abs(l) for c in self.current for l in c})
            if i >= len(variables):
                return

            target = variables[i]
            self.debug("Deleting", target)

            new_clauses = []
            for c in self.current:
                c = set(c)
                c.discard(target)
                c.discard(-target)
                if c:
                    new_clauses.append(c)
            if self.test_function(new_clauses):
                self.replace_with_core()
            else:
                i += 1

    @reduction_pass
    def delete_clauses(self):
        i = 0
        while i < len(self.current):
            initial = self.current
            find_integer(
                lambda k: i + k <= len(initial)
                and self.test_function(initial[:i] + initial[i + k :])
            )
            i += 1

    @reduction_pass
    def merge_variables(self):
        i = 0
        j = 1
        while True:
            variables = sorted({abs(l) for c in self.current for l in c})
            if j >= len(variables):
                i += 1
                j = i + 1
            if j >= len(variables):
                return

            target = variables[i]
            to_replace = variables[j]

            new_clauses = []
            for c in self.current:
                c = set(c)
                if to_replace in c:
                    c.discard(to_replace)
                    c.add(target)
                if -to_replace in c:
                    c.discard(-to_replace)
                    c.add(-target)
                new_clauses.append(c)
            if not self.test_function(new_clauses):
                j += 1

    @reduction_pass
    def delete_literals_from_clauses(self):
        i = 0
        j = 0
        while i < len(self.current):
            clause = self.current[i]
            if j >= len(clause):
                j = 0
                i += 1
                continue
            attempt = list(self.current)
            attempt[i] = list(attempt[i])
            del attempt[i][j]
            if not self.test_function(attempt):
                j += 1

    def test_function(self, clauses):
        keys = [cache_key(clauses)]
        try:
            return self.__cache[keys[0]]
        except KeyError:
            pass

        clauses = self.canonicalise(clauses)
        keys.append(cache_key(clauses))
        try:
            result = self.__cache[keys[-1]]
        except KeyError:
            result = self.__test_function(clauses)
            if result and sort_key(clauses) < sort_key(self.current):
                self.debug(
                    f"Shrunk to {len(clauses)} clauses over {len(calc_variables(clauses))} variables"
                )
                self.current = clauses
        for key in keys:
            self.__cache[key] = result
        return result

    def renumber_variables(self):
        renumbering = {}

        def renumber(l):
            try:
                return renumbering[l]
            except KeyError:
                pass
            try:
                return -renumbering[-l]
            except KeyError:
                pass

            result = len(renumbering) + 1
            renumbering[l] = result
            return result

        renumbered = [[renumber(l) for l in c] for c in self.current]

        self.test_function(renumbered)

    def canonicalise(self, clauses):
        return tuple(
            sorted(
                {tuple(sorted(set(clause))) for clause in clauses},
                key=lambda s: (len(s), s),
            )
        )


def calc_variables(clauses):
    return {abs(l) for c in clauses for l in c}


def sort_key(clauses):
    n_variables = len(calc_variables(clauses))
    n_clauses = len(clauses)
    average_clause_length = (
        (sum([len(c) for c in clauses]) / n_clauses) if n_clauses > 0 else 0.0
    )

    shrink_clauses = [tuple((abs(l), l < 0) for l in c) for c in clauses]

    return (n_variables, n_clauses, average_clause_length, shrink_clauses)


def cache_key(clauses):
    n = len(clauses)
    r = repr(clauses)
    hex = hashlib.sha1(r.encode("utf-8")).hexdigest()[:8]
    return f"{n}:{len(r)}:{hex}"


def find_integer(f):
    """Finds a (hopefully large) integer n such that f(n) is True and f(n + 1)
    is False. Runs in O(log(n)).

    f(0) is assumed to be True and will not be checked. May not terminate unless
    f(n) is False for all sufficiently large n.
    """
    # We first do a linear scan over the small numbers and only start to do
    # anything intelligent if f(4) is true. This is because it's very hard to
    # win big when the result is small. If the result is 0 and we try 2 first
    # then we've done twice as much work as we needed to!
    for i in range(1, 5):
        if not f(i):
            return i - 1

    # We now know that f(4) is true. We want to find some number for which
    # f(n) is *not* true.
    # lo is the largest number for which we know that f(lo) is true.
    lo = 4

    # Exponential probe upwards until we find some value hi such that f(hi)
    # is not true. Subsequently we maintain the invariant that hi is the
    # smallest number for which we know that f(hi) is not true.
    hi = 5
    while f(hi):
        lo = hi
        hi *= 2

    # Now binary search until lo + 1 = hi. At that point we have f(lo) and not
    # f(lo + 1), as desired..
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if f(mid):
            lo = mid
        else:
            hi = mid
    return lo


class UnionFind:
    def __init__(self):
        self.table = {}

    def find(self, value):
        """Find a canonical representative for ``value``
        according to the current merges."""
        try:
            if self.table[value] == value:
                return value
        except KeyError:
            self.table[value] = value
            return value

        trail = []
        while value != self.table[value]:
            trail.append(value)
            value = self.table[value]
        for t in trail:
            self.table[t] = value
        return value

    def merge(self, left, right):
        left = self.find(left)
        right = self.find(right)
        if left > right:
            right, left = left, right
        self.table[right] = left

    def merge_all(self, values):
        value = None
        for i, v in enumerate(values):
            if i == 0:
                value = v
            else:
                self.merge(v, value)

    def partitions(self):
        results = defaultdict(set)
        for k in self.table:
            results[self.find(k)].add(k)
        yield from results.values()

    def __repr__(self):
        return f"UnionFind({list(self.partitions())})"
