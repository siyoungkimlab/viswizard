"""
cg.py -- what element a coarse-grained bead stands for.

A Martini or SIRAH file names beads, not atoms, and says nothing about
elements, so a viewer guesses from the name and gets it wrong: PyMOL reads
Martini water "W" as tungsten, the sodium bead "SOD" as sulfur, and the
glycerol beads "GL1"/"GL2" as an element "G" that does not exist; VMD gives
every bead element X, atomic number 0, and a radius picked off the first
letter -- 1.9 A for "SC1", which is sulfur's.

Wrong elements mean wrong colours, wrong radii and a wrong element category,
so a bead is coloured as whatever it was mistaken for.  The rules below give
each bead the element it stands for, which is what a viewer needs; a bead is
still a bead, several atoms' worth of one.

Nothing here imports pymol, so it can be tested on its own.
"""

# An ion bead is one ion, and these names would otherwise be read as the
# element their first letter happens to be: SOD as sulfur, CLA as carbon.
IONS = {
    "NA": "Na", "SOD": "Na", "CL": "Cl", "CLA": "Cl", "K": "K", "POT": "K",
    "CA": "Ca", "CAL": "Ca", "MG": "Mg", "ZN": "Zn", "CES": "Cs", "CS": "Cs",
}

# Martini beads whose name says nothing about the element.
EXACT = {
    "BB": "C",       # protein backbone: one per residue
    "PO4": "P",      # lipid phosphate
    "NC3": "N",      # choline nitrogen
    "CNO": "N",      # ethanolamine head
}

# Read as (prefix, element), first match winning.  SC1..SC5 are Martini side
# chain beads -- mostly apolar or aromatic, so carbon is the sensible stand-in
# whatever the residue -- GL1/GL2 the glycerol backbone, C.. and D.. the tail
# beads (D for a bead with a double bond), and W.. the water beads: Martini's
# W and WF, SIRAH's WT4, all standing for water, so oxygen.
PREFIX = (("SC", "C"), ("GL", "C"), ("W", "O"), ("C", "C"), ("D", "C"))

# SIRAH names a bead for the atom it is centred on: the second letter is the
# element.  GN, GC and GO are the backbone; BCB, BOG, BSG, BNN and the rest
# are side chains.
SIRAH_FIRST = "BG"
SIRAH_ELEMENTS = "CNOSP"

# Any of these means the model is coarse-grained rather than all-atom.
MARKERS = ("BB", "GC", "GN", "SC1")

# The one bead per residue that stands in for the backbone: Martini's BB,
# SIRAH's GC.  It is what the fit, the sequence superposition and the cartoon
# all work from.
BACKBONE = ("BB", "GC")

# What a backbone bead is called once PyMOL has it.  PyMOL decides what is
# protein while it reads a file, and a bead named BB carrying whatever element
# its name suggests is not it, so nothing in the model is a protein: no guide
# atoms, and cealign, super, the cartoon and the GUI's "action -> align -> to
# molecule" all have nothing to work from.  Giving the beads their element and
# renaming the backbone bead CA is enough -- PyMOL then classifies the model on
# the next sort, and everything above works.  Only PyMOL needs this; VMD reads
# the beads under their own names.
CA = "CA"

# The residues whose beads are protein.  PyMOL decides for itself what is
# polymer while it reads a file, but it wants a full N/CA/C/O backbone to do
# it, and a coarse-grained model has one bead per residue -- so the beads are
# marked as polymer here instead.  Without it "polymer" matches nothing in the
# model, and neither does anything built on it.
RESIDUES = set(
    "ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP "
    "TYR VAL HID HIE HIP HISD HISE HISH CYX CYM ACE NME NMA".split())


# The residue names coarse-grained solvent and ions come under.  Neither VMD's
# "water" nor PyMOL's "solvent" matches a Martini water bead -- the residue is
# called W -- so without this list a 7266-bead box strips 8 atoms and keeps
# 5665 waters.  SIRAH's water is WT4 and its ions NaW/ClW; an ion bead often
# arrives under a residue called ION, or under its own name.
SOLVENT = ("W", "WF", "WN", "WT4", "ION", "NA", "CL", "SOD", "CLA", "POT",
           "CAL", "MG", "ZN", "NAW", "CLW")


def solvent_selection(pymol=True):
    """A selection for coarse-grained water and ions, to strip."""
    return ("resn " if pymol else "resname ") + \
           ("+" if pymol else " ").join(SOLVENT)


def pymol_atom(name, resname=""):
    """What PyMOL should be told about a bead: (name, element, hetatm).

    None when the bead name says nothing, in which case the file's own values
    stand.  This has to be applied while the file is being read: PyMOL works
    out what each residue is as it reads it, and a bead with a bogus element is
    not a protein, so the model arrives as nothing at all -- no guide atoms,
    and align, super and the GUI's "action -> align -> to molecule" have
    nothing to work from.  Correcting the elements afterwards does not undo it;
    a sort brings back the guide atoms and cealign, but align and super stay
    broken, so the model has to be born right.
    """
    elem = element(name)
    if not elem:
        return None
    protein = str(resname).strip().upper() in RESIDUES
    n = str(name).strip().upper()
    return (CA if protein and n in BACKBONE else name, elem, 0 if protein else 1)


def is_water(name):
    """A water bead: Martini's W and WF, SIRAH's WT4."""
    return str(name).strip().upper().startswith("W")


def is_ion(name):
    """An ion bead, which is one ion."""
    return str(name).strip().upper() in IONS


def solute_beads(names, rename=False):
    """The bead names worth gluing and drawing: not water, not ions.

    PyMOL's polymer/organic/inorganic flags are set when a file is read and do
    not follow the element afterwards, so a model PyMOL read itself is
    "inorganic" whatever its beads are -- "polymer" matches none of it.  The
    beads themselves are what is left to name.

    With rename, a backbone bead is listed under both names: CA, which is what
    PyMOL calls it once the model is loaded, and the file's own name, because
    only the beads of a residue the reader recognised were renamed.  A system
    can hold both -- a protein and, say, the dipeptide probes of a pocket
    search, whose residue names (WW, FY, EE) no reader knows.  A bead already
    called CA is a calcium ion, which is not solute either way.
    """
    out = set()
    for n in set(names):
        if str(n).strip().upper() in BACKBONE:
            out.add(n)
            if rename:
                out.add(CA)
        elif element(n) and not is_water(n) and not is_ion(n):
            out.add(n)
    return sorted(out)


def solute_selection(names, pymol=True, rename=False):
    """A selection for those beads, or "" when there are none."""
    beads = solute_beads(names, rename)
    if not beads:
        return ""
    return "name " + ("+" if pymol else " ").join(beads)


def backbone_selection(pymol=True):
    """"name BB+GC" for PyMOL, "name BB GC" for VMD."""
    return "name " + ("+" if pymol else " ").join(BACKBONE)


def element(name):
    """The element a bead stands for, or None when the name says nothing."""
    n = str(name).strip().upper()
    if not n:
        return None
    if n in IONS:
        return IONS[n]
    if n in EXACT:
        return EXACT[n]
    if len(n) >= 2 and n[0] in SIRAH_FIRST and n[1] in SIRAH_ELEMENTS:
        return n[1]
    for prefix, elem in PREFIX:
        if n.startswith(prefix):
            return elem
    return None


def looks_coarse_grained(names):
    """Is this a coarse-grained model?  A backbone or side chain bead says so."""
    upper = {str(n).strip().upper() for n in names}
    return bool(upper.intersection(MARKERS))


def elements(names):
    """{name: element} for the names worth overwriting, in one pass.

    A bead called CA is left out.  Either it is a calcium ion, which a viewer
    reads as calcium already, or it is a backbone bead that came in through
    pymol_atom and carries its carbon -- and nothing here can tell the two
    apart.  Both are right as they stand.
    """
    out = {}
    for n in set(names):
        if str(n).strip().upper() == CA:
            continue
        e = element(n)
        if e:
            out[n] = e
    return out
