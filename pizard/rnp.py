"""
rnp.py -- Runs N' Poses / PLINDER system ids as pizard input.

    pizard rnp 8g62__1__1.A__1.F_1.J_1.L        # the whole system
    pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F    # zoomed on that one ligand

A PLINDER system id names a protein-ligand complex:

    8g62 __ 1 __ 1.A __ 1.F_1.J_1.L
    ^      ^     ^       ^
    PDB    |     |       ligand chains, joined by "_"
    entry  |     receptor chains, joined by "_"
           biological assembly

Each chain is <instance>.<asym_id>, where asym_id is the mmCIF
``label_asym_id`` -- NOT the author chain.  In 8G62 every ligand is author
chain A; F, J and L are what tells them apart.  That is the whole reason this
module exists: there is no way to type "1.F" at PyMOL and mean anything, but
PyMOL does keep ``label_asym_id`` in the segment identifier, so

    segi F

is the ligand, exactly, with no residue numbers to look up.  A PLINDER
ground-truth ``system.cif`` is even simpler: its chains are already called
"1.A" and "1.F", so the id can be used verbatim.

Nothing here imports pymol, so it can be tested on its own.
"""
import atexit
import os
import re
import shutil
import tempfile
import urllib.request

RCSB_CIF = "https://files.rcsb.org/download/%s.cif"

# PDBe serves a ready-made map per X-ray entry, so there is nothing to phase
# here: <id>.ccp4 is the 2Fo-Fc map (what the model was built into) and
# <id>_diff.ccp4 the Fo-Fc difference map (what the model does not explain --
# positive where there is unmodelled density, negative where an atom sits in
# none).  Both are on the crystal cell, with the symmetry in their own header,
# which is how PyMOL places a mesh around a ligand outside the deposited box.
PDBE_MAPS = {
    "2fofc": "https://www.ebi.ac.uk/pdbe/entry-files/%s.ccp4",
    "fofc": "https://www.ebi.ac.uk/pdbe/entry-files/%s_diff.ccp4",
}
DENSITY_CHOICES = ("2fofc", "fofc", "both", "off")

# <instance>.<asym_id> -- "1.A", "2.BA".  The asym id is letters (mmCIF allows
# more, but every PDB entry uses A, B, ... AA, AB).
CHAIN = re.compile(r"^(\d+)\.([0-9A-Za-z]+)$")

# Where a downloaded ground_truth.tar.gz might have been unpacked.  The
# benchmark's own poses are better than anything fetched from RCSB -- they are
# what its numbers were computed against -- so they win when they are there.
GROUND_TRUTH_DIRS = [
    "$RNP_GROUND_TRUTH",
    "~/runs-n-poses/ground_truth",
    "~/runs-n-poses/examples/ground_truth",
    "~/data/paper_data/ground_truth",
    "./ground_truth",
]


class System(object):
    """A parsed PLINDER system id."""

    def __init__(self, system_id, pdb_id, assembly, receptor, ligands):
        self.system_id = system_id
        self.pdb_id = pdb_id
        self.assembly = assembly
        self.receptor = receptor      # ["1.A"]
        self.ligands = ligands        # ["1.F", "1.J", "1.L"]

    @property
    def chains(self):
        return self.receptor + self.ligands

    def __repr__(self):
        return "System(%s)" % self.system_id


def parse(system_id):
    """Split a system id into its four fields, or raise ValueError."""
    fields = system_id.split("__")
    if len(fields) != 4:
        raise ValueError(
            "'%s' is not a PLINDER system id: expected four __-separated "
            "fields, <pdb>__<assembly>__<receptor chains>__<ligand chains>, "
            "got %d" % (system_id, len(fields)))
    pdb_id, assembly, rec, lig = fields
    if not re.match(r"^[0-9][0-9A-Za-z]{3}$", pdb_id):
        raise ValueError("'%s': '%s' is not a 4-character PDB id"
                         % (system_id, pdb_id))
    receptor, ligands = rec.split("_"), lig.split("_")
    for c in receptor + ligands:
        if not CHAIN.match(c):
            raise ValueError("'%s': '%s' is not an <instance>.<chain> name"
                             % (system_id, c))
    return System(system_id, pdb_id.lower(), assembly, receptor, ligands)


def asym(chain):
    """"1.F" -> "F" -- the mmCIF label_asym_id."""
    return CHAIN.match(chain).group(2)


def instance(chain):
    """"2.A" -> 2 -- which copy of the chain the assembly makes."""
    return int(CHAIN.match(chain).group(1))


def resolve_ligand(system, wanted):
    """Match what the user typed against the system's ligand chains.

    "1.F" and "F" both work, and so does the wrong case, because the point of
    typing it is to save a trip to the RCSB page -- not to be graded on it.
    """
    if wanted is None:
        return None
    w = wanted.strip()
    for c in system.ligands:
        if w.lower() in (c.lower(), asym(c).lower()):
            return c
    raise ValueError(
        "'%s' is not a ligand chain of %s -- it has %s"
        % (wanted, system.system_id, ", ".join(system.ligands)))


def selection(chains, local):
    """A PyMOL selection for these PLINDER chains.

    ``local`` is a ground-truth system.cif, whose chains are already named
    "1.F"; otherwise the file came from RCSB and the name to match is the bare
    label_asym_id, which PyMOL parks in segi.
    """
    if not chains:
        return "none"
    names = chains if local else [asym(c) for c in chains]
    return "segi " + "+".join(names)


def ground_truth(system_id, dirs=None):
    """Path to a local ground-truth system.cif, or None."""
    for d in (GROUND_TRUTH_DIRS if dirs is None else dirs):
        d = os.path.expanduser(os.path.expandvars(d))
        if "$" in d:            # an unset environment variable
            continue
        p = os.path.join(d, system_id, "system.cif")
        if os.path.isfile(p):
            return p
    return None


def fetch(pdb_id, dest_dir):
    """Download an mmCIF from RCSB into dest_dir and return the path."""
    url = RCSB_CIF % pdb_id.lower()
    path = os.path.join(dest_dir, "%s.cif" % pdb_id.lower())
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(path, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        raise SystemExit("pizard rnp: could not download %s (%s)" % (url, e))
    return path


def density_kinds(spec):
    """--density value -> the maps to load, in the order to load them."""
    spec = str(spec).strip().lower()
    if spec in ("off", "none", "no", "0", ""):
        return []
    if spec == "both":
        return ["2fofc", "fofc"]
    if spec in PDBE_MAPS:
        return [spec]
    raise SystemExit("pizard: --density takes one of %s, not '%s'"
                     % (", ".join(DENSITY_CHOICES), spec))


def fetch_map(pdb_id, kind, dest_dir):
    """Download a PDBe map, or None when the entry has none.

    An NMR or cryo-EM entry has no X-ray map, and neither does an X-ray entry
    whose structure factors were never deposited; that is a fact about the
    entry, not an error, so it comes back as None for the caller to mention.
    """
    url = PDBE_MAPS[kind] % pdb_id.lower()
    path = os.path.join(dest_dir, "%s_%s.ccp4" % (pdb_id.lower(), kind))
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        return None
    return path


class Context(object):
    """What pizard needs to open one PLINDER system.

    ``argv`` is the ordinary pizard command line this turned into, so the
    normal code path does the loading, the reps and the zoom; the rest is the
    little that is specific to a PLINDER system.
    """

    def __init__(self, system, path, argv, others, local, temp=None, notes=()):
        self.system = system
        self.path = path
        self.argv = argv
        self.others = others      # the ligand chains NOT zoomed on
        self.local = local        # ground-truth naming ("1.F") vs RCSB ("F")
        self.temp = temp
        self.notes = list(notes)

    def tempdir(self):
        """A scratch directory for downloads, made on demand."""
        if not self.temp:
            self.temp = tempfile.mkdtemp(prefix="pizard-rnp-")
            atexit.register(shutil.rmtree, self.temp, True)
        return self.temp

    def cleanup(self):
        """Delete the downloaded CIF.  It is already in PyMOL's memory."""
        if self.temp and os.path.isdir(self.temp):
            shutil.rmtree(self.temp, ignore_errors=True)
            self.temp = None


def prepare(args, dirs=None, fetcher=fetch):
    """Turn ``rnp <system_id> [<ligand chain>] [flags]`` into a Context."""
    # A flag's value is positional too ("--pocket 8"), so only the tokens
    # before the first flag can be ours.
    head = []
    for a in args:
        if a.startswith("-"):
            break
        head.append(a)
    if not head:
        raise SystemExit(
            "pizard rnp: give a PLINDER system id, e.g.\n"
            "  pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F")
    if len(head) > 2:
        raise SystemExit("pizard rnp: expected a system id and at most one "
                         "ligand chain, got %s" % " ".join(head))
    try:
        system = parse(head[0])
        chain = resolve_ligand(system, head[1] if len(head) > 1 else None)
    except ValueError as e:
        raise SystemExit("pizard rnp: %s" % e)
    passthrough = args[len(head):]

    notes = []
    path = ground_truth(system.system_id, dirs)
    local = path is not None
    temp = None
    if local:
        notes.append("ground truth %s" % path)
    else:
        temp = tempfile.mkdtemp(prefix="pizard-rnp-")
        atexit.register(shutil.rmtree, temp, True)   # backstop; see cleanup()
        path = fetcher(system.pdb_id, temp)
        notes.append("fetched %s (deleted after loading)"
                     % os.path.basename(path))
        # The asymmetric unit is what RCSB serves.  Instance 1 of a chain is
        # in it; a second copy is made by the assembly operation, which is not
        # applied here, so say so rather than showing the wrong molecule
        # silently.
        if any(instance(c) != 1 for c in system.chains):
            notes.append("chains beyond instance 1 are assembly copies; "
                         "showing the deposited chains instead")
        elif system.assembly not in ("1",):
            notes.append("assembly %s: showing deposited coordinates"
                         % system.assembly)

    focus = [chain] if chain else list(system.ligands)
    others = [c for c in system.ligands if c not in focus]

    # --strip none, because a PLINDER ligand is sometimes exactly what --strip
    # throws away: 7p1e__1__1.A__1.C_1.G has a calcium as chain 1.G, and
    # "solvent or inorganic" would delete it.  --only has already reduced the
    # file to this system's chains, so there is nothing left to strip.
    argv = [path,
            "--object", system.pdb_id,
            "--ligand", selection(focus, local),
            "--only", selection(system.chains, local),
            "--strip", "none"] + list(passthrough)
    return Context(system, path, argv, others, local, temp, notes)


def describe(ctx):
    """The one-line summary printed when a system opens."""
    s = ctx.system
    return "pizard rnp: %s -- %s, assembly %s, receptor %s, ligand%s %s" % (
        s.system_id, s.pdb_id.upper(), s.assembly, "+".join(s.receptor),
        "" if len(s.ligands) == 1 else "s", "+".join(s.ligands))
