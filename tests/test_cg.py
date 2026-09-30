"""What element a coarse-grained bead stands for (pizard/cg.py)."""
import pytest

import cg


@pytest.mark.parametrize("name,elem", [
    ("BB", "C"),              # Martini backbone
    ("SC1", "C"), ("SC4", "C"),
    ("GC", "C"), ("GN", "N"), ("GO", "O"),          # SIRAH backbone
    ("BCB", "C"), ("BOG", "O"), ("BSG", "S"), ("BNN", "N"),   # SIRAH side chains
    ("W", "O"), ("WF", "O"), ("WT4", "O"),          # water beads
    ("PO4", "P"), ("NC3", "N"), ("GL1", "C"), ("GL2", "C"),
    ("C1A", "C"), ("C4B", "C"), ("D2A", "C"),       # lipid tails
    ("NA", "Na"), ("SOD", "Na"), ("CLA", "Cl"), ("CL", "Cl"),
])
def test_bead_elements(name, elem):
    assert cg.element(name) == elem


def test_the_names_a_viewer_gets_most_wrong():
    # PyMOL read these as tungsten, sulfur and an element "G"
    assert cg.element("W") == "O"
    assert cg.element("SOD") == "Na"
    assert cg.element("GL1") == "C"


def test_an_unknown_name_is_left_alone():
    assert cg.element("QQQ") is None
    assert cg.element("") is None
    assert cg.element("  ") is None


def test_case_and_padding_do_not_matter():
    assert cg.element(" bb ") == "C"
    assert cg.element("gc") == "C"


def test_coarse_grained_is_recognised_by_its_beads():
    assert cg.looks_coarse_grained(["BB", "SC1", "W"])
    assert cg.looks_coarse_grained(["GN", "GC", "GO"])
    assert not cg.looks_coarse_grained(["CA", "CB", "N", "O", "OW"])


def test_elements_maps_only_what_it_knows():
    got = cg.elements(["BB", "SC1", "QQQ", "W"])
    assert got == {"BB": "C", "SC1": "C", "W": "O"}


def _tcl_table(name):
    """Pull one of cg.tcl's tables, to check it against cg.py's."""
    import os
    import re
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "vizard", "cg.tcl")
    text = open(path).read()
    m = re.search(r"^(?:array set ::CG::%s|set ::CG::%s) \{(.*?)\}$" % (name, name),
                  text, re.M | re.S)
    assert m, "no ::CG::%s in cg.tcl" % name
    return m.group(1).split()


def test_tcl_and_python_tables_agree():
    """vizard/cg.tcl repeats cg.py's tables; they have to say the same thing."""
    ions = _tcl_table("IONS")
    assert dict(zip(ions[::2], ions[1::2])) == cg.IONS
    exact = _tcl_table("EXACT")
    assert dict(zip(exact[::2], exact[1::2])) == cg.EXACT
    prefix = _tcl_table("PREFIX")
    assert tuple(zip(prefix[::2], prefix[1::2])) == cg.PREFIX
    assert _tcl_table("MARKERS") == list(cg.MARKERS)


def test_water_and_ion_beads_are_told_apart():
    assert cg.is_water("W") and cg.is_water("WF") and cg.is_water("WT4")
    assert not cg.is_water("BB")
    assert cg.is_ion("SOD") and cg.is_ion("CLA") and cg.is_ion("NA")
    assert not cg.is_ion("SC1")


def test_solute_beads_leave_out_water_and_ions():
    names = ["BB", "SC1", "SC2", "W", "SOD", "CLA", "QQQ"]
    assert cg.solute_beads(names) == ["BB", "SC1", "SC2"]
    assert cg.solute_selection(names) == "name BB+SC1+SC2"
    assert cg.solute_selection(names, pymol=False) == "name BB SC1 SC2"


def test_solute_selection_of_nothing_is_empty():
    assert cg.solute_selection(["W", "SOD"]) == ""
    assert cg.solute_selection([]) == ""
