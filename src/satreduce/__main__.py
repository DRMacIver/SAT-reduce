import hashlib
import os
import random
import shlex
import signal
import subprocess
import sys
import time
import traceback
from shutil import which
from tempfile import TemporaryDirectory

import click

from satreduce.dimacscnf import clauses_to_dimacs
from satreduce.dimacscnf import dimacs_to_clauses
from satreduce.reducer import SATShrinker


def validate_command(ctx, param, value):
    if value is None:
        return None
    parts = shlex.split(value)
    command = parts[0]

    if os.path.exists(command):
        command = os.path.abspath(command)
    else:
        what = which(command)
        if what is None:
            raise click.BadParameter("%s: command not found" % (command,))
        command = os.path.abspath(what)
    return [command] + parts[1:]


def signal_group(sp, signal):
    gid = os.getpgid(sp.pid)
    assert gid != os.getgid()
    os.killpg(gid, signal)


def interrupt_wait_and_kill(sp):
    if sp.returncode is None:
        # In case the subprocess forked. Python might hang if you don't close
        # all pipes.
        for pipe in [sp.stdout, sp.stderr, sp.stdin]:
            if pipe:
                pipe.close()
        signal_group(sp, signal.SIGINT)
        for _ in range(10):
            if sp.poll() is not None:
                return
            time.sleep(0.1)
        signal_group(sp, signal.SIGKILL)


@click.command(
    help="""
satreduce takes a file in simplified DIMACS CNF format and a test command and
attempts to produce a minimal example of the file such that the test command
returns 0.
""".strip()
)
@click.version_option()
@click.option(
    "--debug/--no-debug",
    default=False,
    is_flag=True,
    help=("Emit (extremely verbose) debug output while shrinking"),
)
@click.option(
    "--backup",
    default="",
    help=(
        "Name of the backup file to create. Defaults to adding .bak to the "
        "name of the source file"
    ),
)
@click.option("--seed", default=None)
@click.option(
    "--timeout",
    default=1,
    type=click.FLOAT,
    help=(
        "Time out subprocesses after this many seconds. If set to <= 0 then "
        "no timeout will be used. Any commands that time out will be treated "
        "as failing the test"
    ),
)
@click.argument("test", callback=validate_command)
@click.argument(
    "filename",
    type=click.Path(exists=True, resolve_path=True, dir_okay=False, allow_dash=False),
)
def main(
    debug,
    backup,
    filename,
    test,
    timeout,
    seed,
):
    if debug:

        def dump_trace(signum, frame):
            traceback.print_stack()

        signal.signal(signal.SIGQUIT, dump_trace)

    if seed is not None:
        random.seed(seed)

    if not backup:
        backup = filename + os.extsep + "bak"

    try:
        os.remove(backup)
    except FileNotFoundError:
        pass

    def test_clauses(clauses):
        with TemporaryDirectory() as d:
            sp = subprocess.Popen(
                test,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                preexec_fn=os.setsid,
                cwd=d,
            )
            try:
                sp.communicate(clauses_to_dimacs(clauses), timeout=timeout)
            finally:
                interrupt_wait_and_kill(sp)
            return sp.returncode == 0

    if timeout <= 0:
        timeout = None

    with open(filename, "r") as o:
        initial = o.read()

    if not backup:
        backup = os.path.abspath(filename + ".bak")

    with open(backup, "w") as o:
        o.write(initial)

    shrinker = SATShrinker(
        dimacs_to_clauses(initial),
        test_clauses,
        debug=debug,
    )

    @shrinker.on_reduce
    def _(clauses):
        with open(filename, "w") as o:
            o.write(clauses_to_dimacs(clauses))

    shrinker.reduce()


if __name__ == "__main__":
    main(prog_name="sat-reduce")  # pragma: no cover
