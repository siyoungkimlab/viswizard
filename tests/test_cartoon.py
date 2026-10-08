"""The coarse-grained cartoon trace, as far as a test without PyMOL can see.

PyMOL has to be running to draw anything, so what is checked here is the
source: that each setting the trace needs is asked for, and asked for on the
object rather than globally.  The drawing itself was checked by driving PyMOL
headless -- see CONTRIBUTING.md on verifying what CI cannot reach.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _source():
    with open(os.path.join(ROOT, "pizard", "pizard.py")) as fh:
        return fh.read()


def test_the_trace_settings_are_set_on_the_object():
    """As a global these would trace the cartoon of everything loaded after,
    so a structure fetched later would come out as a tube through all its
    atoms."""
    src = _source()
    for setting in ("cartoon_trace_atoms", "cartoon_tube_radius", "cartoon_gap_cutoff"):
        m = re.search(r'cmd\.set\("%s", ([^,]+), ([^)]+)\)' % setting, src)
        assert m, "pizard does not set %s" % setting
        assert m.group(2).strip() not in ("", "None"), "%s is set globally" % setting


def test_a_jump_in_the_numbering_does_not_break_the_trace():
    """PyMOL breaks a cartoon where the residue number jumps, and a number is
    not a distance: 1jbu's chain H is numbered as a chymotrypsin and jumps
    eight times -- 35 to 37, 129G to 134, 170I to 175 -- with the two beads
    2.9 to 3.7 A apart each time.  At PyMOL's default of 10 the trace came out
    in pieces, with stubs hanging off it.

    Raising it costs nothing: PyMOL draws a real break as dashes whatever this
    is set to, so no trace claims a chain is whole when it is not.
    """
    src = _source()
    cutoff = int(re.search(r"^GAP_CUTOFF = (\d+)", src, re.M).group(1))
    assert cutoff > 10          # PyMOL's own default, which is what broke it
    assert 'cmd.set("cartoon_gap_cutoff", GAP_CUTOFF' in src
