import pytest

from satreduce.booleanequivalence import BooleanEquivalence
from satreduce.booleanequivalence import NegatingTable


def test_no_zero_key_get():
    table = NegatingTable()
    with pytest.raises(ValueError):
        table[0]


def test_no_zero_key_set():
    table = NegatingTable()
    with pytest.raises(ValueError):
        table[0] = -1
