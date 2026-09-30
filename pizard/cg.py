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
    """{name: element} for the names worth overwriting, in one pass."""
    out = {}
    for n in set(names):
        e = element(n)
        if e:
            out[n] = e
    return out
