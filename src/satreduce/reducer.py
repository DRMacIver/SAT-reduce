import hashlib
from collections import Counter
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import wraps
from itertools import islice
from threading import Lock

from satreduce.booleanequivalence import Inconsistency
from satreduce.decomposition import ReducedSatProblem


def shrink_sat(clauses, test_function, **kwargs):
    shrinker = SATShrinker(clauses, test_function, **kwargs)
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
    def __init__(self, starting_point, test_function, debug=False, parallelism=1):
        self.current = canonicalise(starting_point)
        self.__test_function = test_function
        self.__cache = {}
        self.__debug = debug
        self.__on_reduce_callbacks = []
        self.__parallelism = parallelism

        if parallelism > 1:
            self.__executor = ThreadPoolExecutor(max_workers=parallelism)
            self.__lock = Lock()

        if not self.test_function(self.current):
            raise ValueError("Initial argument does not satisfy test.")

    def on_reduce(self, fn):
        self.__on_reduce_callbacks.append(fn)

    def debug(self, *args, **kwargs):
        if self.__debug:
            print(*args, **kwargs)

    def reduce(self):
        prev = None
        while prev is not self.current:
            prev = self.current
            self.house_keeping_shrinks()
            self.delete_clauses()
            self.delete_literals()
            self.force_literals()
            self.delete_literals_from_clauses()
            self.merge_variables()

    def house_keeping_shrinks(self):
        self.replace_with_core()
        self.move_to_components()
        self.renumber_variables()

    def delete_literals(self):
        counts = Counter()
        for clause in self.current:
            for l in clause:
                counts[l] += 1
        literals = sorted(counts, key=counts.__getitem__, reverse=True)

        i = 0
        while i < len(literals):
            current = self.current

            def can_delete(i):
                l = literals[i]
                attempt = canonicalise([set(c) - {l} for c in current])
                return attempt != current and self.test_function(attempt)

            try:
                i = self.find_first(range(i, len(literals)), can_delete) + 1
            except NotFound:
                return

    @reduction_pass
    def force_literals(self):
        counts = Counter()
        for clause in self.current:
            for l in clause:
                counts[l] += 1
        literals = sorted(counts, key=counts.__getitem__, reverse=True)

        prev = None
        problem = None

        for l in literals:
            if prev != self.current:
                prev = self.current
                try:
                    problem = ReducedSatProblem.from_sat(self.current)
                except Inconsistency:
                    return
            try:
                forced_l = problem.with_extra_clauses([[l]])
            except Inconsistency:
                continue

            self.try_reduced_problem(forced_l)

    def replace_with_core(self):
        try:
            self.try_reduced_problem(ReducedSatProblem.from_sat(self.current))
        except Inconsistency:
            pass

    def try_reduced_problem(self, problem):
        if self.test_function(problem.core):
            return
        variables = {abs(l) for c in self.current for l in c}
        filled = list(problem.core)
        for k, v in problem.forced.items():
            if not v:
                k = -k
            filled.append([k])
        if self.test_function(filled):
            return
        for k in variables:
            k2 = problem.merge_table.find(k)
            if k2 == k:
                continue
            filled.extend(
                [
                    [-k, k2],
                    [-k2, k],
                ]
            )
        self.test_function(filled)

    @contextmanager
    def locked(self):
        if self.__parallelism <= 1:
            yield
        else:
            try:
                self.__lock.acquire()
                yield
            finally:
                self.__lock.release()

    def find_first(self, ls, f):
        if not ls:
            raise NotFound()
        if self.__parallelism <= 1:
            for x in ls:
                if f(x):
                    return x
            raise NotFound()
        else:
            it = iter(ls)
            chunk_size = 1
            while True:
                chunk = list(islice(it, chunk_size))
                if not chunk:
                    raise NotFound()
                for x, b in zip(chunk, self.__executor.map(f, chunk)):
                    if b:
                        return x
                chunk_size *= 2

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
    def delete_clauses(self):
        i = 0
        while i < len(self.current):
            initial = list(reversed(self.current))

            def can_delete(j, k):
                if j + k > len(initial):
                    return False
                return self.test_function(initial[:j] + initial[j + k :])

            try:
                i = self.find_first(range(i, len(initial)), lambda j: can_delete(j, 1))
            except NotFound:
                break

            find_integer(lambda k: can_delete(i, k))
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
        while True:
            current = self.current

            def can_delete_any(i):
                clause = current[i]
                if len(clause) <= 1:
                    return False
                j = 0
                changed = False
                while j < len(clause):
                    attempt = list(current)
                    attempt[i] = list(clause)
                    del attempt[i][j]
                    if self.test_function(attempt):
                        clause = attempt[i]
                        changed = True
                    else:
                        j += 1
                return changed

            try:
                i = self.find_first(range(i, len(current)), can_delete_any)
            except NotFound:
                break
            i += 1

    def test_function(self, clauses):
        keys = [cache_key(clauses)]
        try:
            return self.__cache[keys[0]]
        except KeyError:
            pass

        clauses = canonicalise(clauses)
        keys.append(cache_key(clauses))
        try:
            result = self.__cache[keys[-1]]
        except KeyError:
            result = self.__test_function(clauses)
            if result:
                with self.locked():
                    if sort_key(clauses) < sort_key(self.current):
                        self.debug(
                            f"Shrunk to {len(clauses)} clauses over {len(calc_variables(clauses))} variables"
                        )
                        self.current = clauses
                        for f in self.__on_reduce_callbacks:
                            f(clauses)
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


class NotFound(Exception):
    pass


def canonicalise(clauses):
    return tuple(
        sorted(
            {tuple(sorted(set(clause))) for clause in clauses},
            key=lambda s: (len(s), s),
        )
    )
