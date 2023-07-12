# SAT-reduce

SAT-reduce is a domain-specific test-case reducer for SAT problems. That is, given a file in CNF format, and some script that defines a condition that file should satisfy, it will produce a smaller version of that file.

## Installation

You can install this from git with:

```bash
pip install git+https://github.com/DRMacIver/SAT-reduce.git
```

It is unlikely to get a proper pypi release.

## Usage

In order to use SAT-reduce, write a small script (say `test.sh`) which takes a DIMACS CNF input file as an argument, and some DIMACS CNF file (say `target.cnf`) and invoke it as follows:

```bash
satreduce test.sh target.cnf
```

This will run for a while, replacing `target.cnf` with progressively smaller versions that cause the test to pass (i.e. return an exit code of 0).

By default it will not tell you much about progress. If you want to see (fairly chatty) output information, you can run this as:

```bash
satreduce test.sh target.cnf --debug
```

There are also a variety of other command line options that you can learn more about from `satreduce --help`.

## Should I use this?

If you have the problem this solves, you should use this, because it is vanishingly unlikely that anyone else will ever write a better tool for this problem, because I'm one of only a tiny handful of people who writes sophisticated test-case reducers, and as far as I know none of the others have gone down a sufficiently pointless rabbithole of working on SAT problems to have need of a SAT specific test-case reducers.

That being said, it's mostly alpha-quality software written for my own purposes. It's well tested and I expect it to work pretty well, but support level is "best effort and subject to current levels of interest" - please do file any issues you find. I will probably fix them, but I make no guarantees.

Still, it's worth a go and is easy to use. If it works well, great. If it doesn't, you're no worse off than you started.