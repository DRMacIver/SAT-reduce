"""Test cases for the __main__ module."""
import pytest
from click.testing import CliRunner

from satreduce import __main__
from satreduce.dimacscnf import clauses_to_dimacs
from satreduce.dimacscnf import dimacs_to_clauses


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_main_fails_with_no_args(runner: CliRunner) -> None:
    """It exits with a status code of zero."""
    result = runner.invoke(__main__.main)
    assert result.exit_code != 0


def test_main_runs_to_empty(runner: CliRunner, tmpdir) -> None:
    """It exits with a status code of zero."""

    target = str(tmpdir / "test.cnf")
    with open(target, "w") as o:
        o.write(
            clauses_to_dimacs(
                [
                    [1, 2, 3],
                ]
            )
        )
    result = runner.invoke(__main__.main, ["true", target])
    assert result.exit_code == 0
    with open(target) as i:
        shrunk = dimacs_to_clauses(i.read())

    assert shrunk == [[1]]
