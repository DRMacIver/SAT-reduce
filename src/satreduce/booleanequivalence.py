from collections import defaultdict


class NegatingTable:
    def __init__(self, table=()):
        self.__table = dict(table)

    def __getitem__(self, key):
        if key == 0:
            raise ValueError("Accessed 0 key")
        if key < 0:
            return -self.__table[-key]
        else:
            return self.__table[key]

    def __setitem__(self, key, value):
        if key == 0:
            raise ValueError("Accessed 0 key")
        if key < 0:
            self.__table[-key] = -value
        else:
            self.__table[key] = value

    def __iter__(self):
        for k in self.__table:
            yield k
            yield -k

    def __copy__(self):
        result = NegatingTable()
        result.__table = dict(self.__table)
        return result


class BooleanEquivalence(object):
    """Implements a data structure for maintaining a
    partition into joint sets using the union find
    algorithm. Initially everything is assumed to be
    in a singleton set, and calls to merge will
    link two sets so they are in the same partition."""

    def __init__(self, partitions=()):
        self.table = NegatingTable()
        for cls in partitions:
            self.merge_all(cls)

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
        assert abs(value) < abs(trail[0])
        return value

    def merge(self, left, right):
        left = self.find(left)
        right = self.find(right)
        if left == -right:
            raise Inconsistency(f"Attempted to merge {left} with {right}")
        if abs(left) > abs(right):
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
        return f"BooleanEquivalence({list(self.partitions())})"

    def __copy__(self):
        result = BooleanEquivalence()
        result.table = self.table.__copy__()
        return result

    def __deepcopy__(self, *args, **kwargs):
        return self.__copy__()


class Inconsistency(Exception):
    pass
