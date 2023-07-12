"""Test cases for the __main__ module."""
import os
import signal
import subprocess
import time

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


def test_can_disable_timeout(runner: CliRunner, tmpdir) -> None:
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
    result = runner.invoke(__main__.main, ["true", target, "--timeout=0"])
    assert result.exit_code == 0
    with open(target) as i:
        shrunk = dimacs_to_clauses(i.read())

    assert shrunk == [[1]]


def test_can_run_compound_tests(runner: CliRunner, tmpdir) -> None:
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
    result = runner.invoke(__main__.main, ["echo hello world", target])
    assert result.exit_code == 0
    with open(target) as i:
        shrunk = dimacs_to_clauses(i.read())

    assert shrunk == [[1]]


def test_creates_backup_file(runner: CliRunner, tmpdir) -> None:
    """It exits with a status code of zero."""

    contents = clauses_to_dimacs(
        [
            [1, 2, 3],
        ]
    )
    target = str(tmpdir / "test.cnf")
    backup = str(tmpdir / "backup.cnf")
    with open(target, "w") as o:
        o.write(contents)
    result = runner.invoke(__main__.main, ["true", target, "--backup=" + backup])
    assert result.exit_code == 0
    with open(backup) as i:
        assert i.read() == contents


def test_runs_with_a_timeout(runner: CliRunner, tmpdir) -> None:
    """It exits with a status code of zero."""

    contents = clauses_to_dimacs(
        [
            [1, 2, 3],
        ]
    )
    target = str(tmpdir / "test.cnf")
    with open(target, "w") as o:
        o.write(contents)
    start = time.time()
    result = runner.invoke(
        __main__.main, ["sleep 10", target, "--timeout=1", "--input-type=basename"]
    )
    assert time.time() - start < 2
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "timeout" in result.exception.args[0]


STUPID_TIMEOUT_SCRIPT = """
#!/usr/bin/env python

import sys
import time

if __name__ == '__main__':
    lines = list(sys.stdin)
    if len(lines) < 3:
        time.sleep(10)
"""


def test_timing_out_is_false(runner: CliRunner, tmpdir) -> None:
    contents = clauses_to_dimacs(
        [
            [1, 2, 3],
            [1, 2],
            [1, 3],
        ]
    )
    script = str(tmpdir / "stupid.py")
    with open(script, "w") as o:
        o.write(STUPID_TIMEOUT_SCRIPT)
    target = str(tmpdir / "test.cnf")
    with open(target, "w") as o:
        o.write(contents)
    start = time.time()
    result = runner.invoke(
        __main__.main,
        [f"python {script}", target, "--timeout=0.1", "--input-type=stdin"],
    )
    assert time.time() - start < 2
    assert result.exit_code == 0

    with open(target) as i:
        clauses = dimacs_to_clauses(i.read())

    assert len(clauses) == 2


def test_prints_with_debug(runner: CliRunner, tmpdir, capfd) -> None:
    contents = clauses_to_dimacs(
        [
            [1, 2, 3],
            [1, 2],
            [1, 3],
        ]
    )
    target = str(tmpdir / "test.cnf")
    with open(target, "w") as o:
        o.write(contents)
    result = runner.invoke(
        __main__.main, [f"echo hello world", target, "--input-type=stdin", "--debug"]
    )
    assert result.exit_code == 0

    out, err = capfd.readouterr()

    assert "hello world" in out


AWFUL_PYTHON_SCRIPT = """
import time

if __name__ == '__main__':
    while True:
        try:
            time.sleep(1)
        except BaseException:
            pass
"""


def test_sigkills_stubborn_processes(tmpdir):
    target = tmpdir / "awful.py"

    with open(target, "w") as o:
        o.write(AWFUL_PYTHON_SCRIPT)

    sp = subprocess.Popen(["python", target], preexec_fn=os.setsid)
    try:
        sp.communicate("", timeout=0.1)
    except subprocess.TimeoutExpired:
        pass

    __main__.interrupt_wait_and_kill(sp)
    assert sp.returncode == -9


def test_errors_on_bad_command(runner: CliRunner, tmpdir) -> None:
    contents = clauses_to_dimacs(
        [
            [1, 2, 3],
        ]
    )
    target = str(tmpdir / "test.cnf")
    with open(target, "w") as o:
        o.write(contents)
    result = runner.invoke(
        __main__.main, [f"this_command_does_not_exist blah blah blah", target]
    )
    assert result.exit_code != 0
    assert "command not found" in result.output


def test_resolves_command_to_path(tmpdir, monkeypatch) -> None:
    monkeypatch.chdir(tmpdir)
    target = str(tmpdir / "test.sh")
    with open(target, "w") as o:
        o.write("")

    validated = __main__.validate_command(..., ..., "test.sh")
    assert validated[0] == target
