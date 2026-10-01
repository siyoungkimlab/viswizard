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
    assert sorted(_tcl_table("RESIDUES")) == sorted(cg.RESIDUES)


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


def test_the_backbone_bead_is_renamed_for_pymol():
    # PyMOL only treats a model as a protein if it says so while reading the
    # file, and one bead per residue called BB is not a protein to it
    assert cg.pymol_atom("BB", "ALA") == ("CA", "C", 0)
    assert cg.pymol_atom("GC", "LEU") == ("CA", "C", 0)
    # the side chains of that residue are protein too, under their own names
    assert cg.pymol_atom("SC1", "ALA") == ("SC1", "C", 0)
    assert cg.pymol_atom("BCB", "CYS") == ("BCB", "C", 0)


def test_water_lipid_and_ion_beads_are_not_renamed_or_made_polymer():
    assert cg.pymol_atom("W", "W") == ("W", "O", 1)
    assert cg.pymol_atom("SOD", "ION") == ("SOD", "Na", 1)
    assert cg.pymol_atom("PO4", "POPC") == ("PO4", "P", 1)
    # a backbone bead outside an amino acid is a bead, not a CA
    assert cg.pymol_atom("BB", "POPC") == ("BB", "C", 1)


def test_a_bead_whose_name_says_nothing_is_left_to_the_file():
    assert cg.pymol_atom("QQQ", "ALA") is None
    assert cg.pymol_atom("", "ALA") is None


def test_a_bead_called_ca_keeps_whatever_it_already_has():
    # either a calcium ion, which a viewer reads as calcium anyway, or a
    # backbone bead that came in through pymol_atom carrying its carbon
    assert "CA" not in cg.elements(["BB", "CA", "SC1"])
    assert cg.elements(["BB", "CA", "SC1"]) == {"BB": "C", "SC1": "C"}


def test_the_glue_names_the_backbone_as_pymol_has_it():
    names = ["BB", "SC1", "W", "SOD"]
    # both names: only the beads of a residue the reader knew were renamed, and
    # a box can hold both -- a protein and the dipeptide probes of a pocket
    # search, whose residue names no reader knows, each carrying its own BB
    assert cg.solute_beads(names, rename=True) == ["BB", "CA", "SC1"]
    assert cg.solute_selection(names, rename=True) == "name BB+CA+SC1"
    # VMD reads the beads under their own names, so nothing is renamed there
    assert cg.solute_selection(names, pymol=False) == "name BB SC1"
