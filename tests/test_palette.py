"""The color palette is written down in three places; keep them in step.

docs/make_swatches.py draws it, vizard/align.tcl defines it for VMD, and
pizard/pizard.py defines it for PyMOL. A change to one and not the others is
exactly the kind of drift nobody notices until a figure looks wrong.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _docs_palette():
    ns = {}
    with open(os.path.join(ROOT, "docs", "make_swatches.py")) as fh:
        src = fh.read()
    m = re.search(r"PALETTE = \[(.*?)\n\]", src, re.S)
    exec("PALETTE = [" + m.group(1) + "\n]", ns)
    return ns["PALETTE"]


def _tcl_palette():
    with open(os.path.join(ROOT, "vizard", "align.tcl")) as fh:
        src = fh.read()
    body = re.search(r"foreach \{id r g b\} \{(.*?)\n    \} \{", src, re.S).group(1)
    nums = body.split()
    out = {}
    for i in range(0, len(nums), 4):
        out[int(nums[i])] = tuple(round(float(v) * 255) for v in nums[i + 1:i + 4])
    return out


def _pizard_pocket():
    with open(os.path.join(ROOT, "pizard", "pizard.py")) as fh:
        src = fh.read()
    block = re.search(r"schemes = \[\(\"forest\".*?\]\n", src, re.S).group(0)
    return [tuple(round(float(v) * 255) for v in m)
            for m in re.findall(r"\(([\d.]+),([\d.]+),([\d.]+)\)", block)]


def test_eight_schemes():
    assert len(_docs_palette()) == 8


@pytest.mark.parametrize("i", range(8))
def test_vmd_matches_the_documented_palette(i):
    docs = _docs_palette()
    tcl = _tcl_palette()
    _, cartoon, _pocket, ligand = docs[i]
    # allow +-1 : the Tcl file stores 0-1 floats rounded to 3 places
    for got, want, what in ((tcl[17 + 2 * i], cartoon, "cartoon"),
                            (tcl[18 + 2 * i], ligand, "ligand")):
        for a, b in zip(got, want):
            assert abs(a - b) <= 1, "%s color drifted for scheme %d" % (what, i)


def test_pymol_pocket_matches_the_documented_palette():
    docs = _docs_palette()
    got = _pizard_pocket()
    assert len(got) == 8
    for i, (_, _c, pocket, _l) in enumerate(docs):
        for a, b in zip(got[i], pocket):
            assert abs(a - b) <= 1, "pocket color drifted for scheme %d" % i


def test_schemes_are_distinguishable():
    """Molecules loaded together must not look alike.

    Guards the specific failure this palette was built to fix: two schemes so
    close in RGB that two overlaid structures read as one.
    """
    docs = _docs_palette()
    def dist(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 / 255.0

    for i in range(len(docs) - 1):
        d = dist(docs[i][1], docs[i + 1][1])
        assert d > 0.40, "schemes %d and %d are too close (%.2f)" % (i, i + 1, d)
    worst = min(dist(a[1], b[1])
                for i, a in enumerate(docs) for b in docs[i + 1:])
    assert worst > 0.18
