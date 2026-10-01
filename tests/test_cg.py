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
    assert sorted(_tcl_table("SIRAH_RESIDUES")) == sorted(cg.SIRAH_RESIDUES)
    assert _tcl_table("SOLVENT") == list(cg.SOLVENT)


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


def test_coarse_grained_water_and_ions_can_be_named_for_stripping():
    # "solvent" and "water" match none of these, which is why --strip needs the
    # list: a Martini water bead's residue is called W
    assert "resn W+WF" in cg.solvent_selection()
    assert cg.solvent_selection(pymol=False).startswith("resname W WF")
    for name in ("W", "WT4", "ION", "SOD"):
        assert name in cg.SOLVENT
    # and nothing that is part of a protein
    assert not set(cg.SOLVENT) & set(cg.RESIDUES)


def test_a_sirah_residue_is_protein_and_a_probe_is_not():
    """SIRAH names its residues for itself, so without its own list a SIRAH
    protein arrives as no protein at all: the backbone bead keeps its name, the
    model is hetatm, and there is nothing to draw a cartoon from.

    Their case is what tells them from the dipeptide probes a swim fills the box
    with: upper-cased, sS, sT, sW and sY are the probes SS, ST, SW and SY.
    """
    for residue in ("sL", "sK", "sHe", "sS", "sT", "sW", "sY"):
        name, elem, het = cg.pymol_atom("GC", residue)
        assert (name, elem, het) == (cg.CA, "C", 0)
        assert cg.pymol_atom("GN", residue)[2] == 0  # the whole residue is protein

    for probe in ("SS", "ST", "SW", "SY", "EK", "RR"):
        name, elem, het = cg.pymol_atom("GC", probe)
        assert (name, elem, het) == ("GC", "C", 1)  # its own name, and not polymer

    assert not {r.upper() for r in cg.SIRAH_RESIDUES} & set(cg.SOLVENT)
    assert not set(cg.SIRAH_RESIDUES) & cg.RESIDUES


def test_a_sirah_residue_is_told_from_a_probe_by_its_case():
    # the reason this is a Python test and not a selection: PyMOL ignores case
    # in resn, so "resn sS" matches the dipeptide probe SS as well, and a box of
    # probes would come out as protein.  VMD's resname keeps its case.
    assert cg.is_protein_residue("sS") and not cg.is_protein_residue("SS")
    assert cg.is_protein_residue("sT") and not cg.is_protein_residue("ST")
    assert cg.is_protein_residue("sW") and not cg.is_protein_residue("SW")
    assert cg.is_protein_residue("sY") and not cg.is_protein_residue("SY")
    # a standard residue is matched whatever its case; a probe never is
    assert cg.is_protein_residue("ALA") and cg.is_protein_residue("ala")
    for probe in ("WW", "FY", "RQ", "EE"):
        assert not cg.is_protein_residue(probe)
        assert cg.pymol_atom("GC", probe) == ("GC", "C", 1)


def test_sirah_water_and_ions_are_named_as_sirah_writes_them():
    # VMD matches a resname with its case, so the upper-cased spelling alone
    # left SIRAH's 175 ion beads in place
    for name in ("NaW", "ClW", "NAW", "CLW", "WT4"):
        assert name in cg.SOLVENT
    assert cg.element("NaW") == "Na" and cg.element("ClW") == "Cl"
    assert cg.is_ion("NaW") and cg.is_ion("ClW")
