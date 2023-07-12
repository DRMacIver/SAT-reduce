import os
import subprocess
import tempfile

from satreduce.dimacscnf import clauses_to_dimacs


def is_satisfiable(clauses):
    if not clauses:
        return True
    if not all(clauses):
        return False

    f, sat_file = tempfile.mkstemp()
    os.close(f)

    with open(sat_file, "w") as o:
        o.write(clauses_to_dimacs(clauses))
    try:
        result = subprocess.run(
            ["minisat", sat_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        assert result in (10, 20)
        return result == 10
    finally:
        os.unlink(sat_file)


def find_solution(clauses):
    if not clauses:
        return []
    if not all(clauses):
        return None

    f, sat_file = tempfile.mkstemp()
    os.close(f)

    f, out_file = tempfile.mkstemp()
    os.close(f)

    with open(sat_file, "w") as o:
        o.write(clauses_to_dimacs(clauses))
    try:
        result = subprocess.run(
            ["minisat", sat_file, out_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        assert result in (10, 20)
        if result == 20:
            return None
        with open(out_file) as i:
            satline, resultline = i
        assert satline == "SAT\n"
        result = list(map(int, resultline.strip().split()))
        assert result[-1] == 0
        result.pop()
        return result
    finally:
        os.unlink(sat_file)
        os.unlink(out_file)
