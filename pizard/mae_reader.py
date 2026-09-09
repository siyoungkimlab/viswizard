"""
mae_reader.py -- .mae / .maegz / .cms reader for open-source PyMOL.

The incentive build gets .mae from the proprietary `epymol.mae`; open-source
PyMOL has nothing.  This is a pure-Python replacement that registers itself
with PyMOL's loader, so `load foo.mae` just works:

    run mae_reader.py
    load system.mae

Bonds come from the file's m_bond block, so nothing is guessed by distance,
and the chorus box becomes the object's unit cell.

Handles: gzip (.maegz, .mae.gz), multiple f_m_ct blocks, quoted strings with
escapes, <> for absent values, and .cms files (the full_system ct wins).
"""
import gzip
import os
import re

__all__ = ["parse_mae", "load_mae"]

ELEMENTS = (
    "LP H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe "
    "Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn "
    "Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W "
    "Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf "
    "Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split()

# Order matters: ':::' before the bare-token rule, comments before everything.
# A '[' is only structural in the "m_atom[204] {" size specifier -- property
# names may legitimately contain brackets (see syntax.mae), so the bare-token
# rule swallows brackets except when they open a size specifier.
_TOKEN = re.compile(r'''
      [ \t\r\n]+                          # whitespace
    | \#[^\n]*                            # comment to end of line
    | "(?:[^"\\]|\\.)*"                   # quoted string, backslash escapes
    | :::                                 # section separator
    | \[\s*\d+\s*\](?=\s*\{)             # block size specifier
    | [{}]                                # structure
    | (?: [^\s{}\[\]"]                    # bare token, brackets allowed
        | \[(?!\s*\d+\s*\]\s*\{)
        | \] )+
''', re.VERBOSE)

_UNQUOTE = re.compile(r'\\(.)')


def _tokenize(text):
    out = []
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t[0] in ' \t\r\n#':
            continue
        if t[0] == '"':
            t = _UNQUOTE.sub(r'\1', t[1:-1])
        out.append(t)
    return out


def _size(cur):
    """Consume a '[N]' size specifier if present."""
    t = cur.peek()
    if t and t[0] == "[":
        return int(cur.next()[1:-1].strip())
    return None


class _Cursor(object):
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        v = self.t[self.i]
        self.i += 1
        return v


def _parse_block(cur, nrows):
    """Read `<names> ::: <values>` plus any nested blocks, up to the closing }."""
    names = []
    while cur.peek() != ":::":
        names.append(cur.next())
    cur.next()                                    # eat :::

    rows, sub = [], {}
    if nrows is None:                             # unindexed: one value per name
        rows.append([cur.next() for _ in names])
    else:
        for _ in range(nrows):
            cur.next()                            # leading row index, discarded
            rows.append([cur.next() for _ in names])
        if cur.peek() == ":::":
            cur.next()

    while cur.peek() != "}":                      # nested blocks (m_atom, m_bond)
        name = cur.next()
        n = _size(cur)
        cur.next()                                # {
        sub[name] = _parse_block(cur, n)
    cur.next()                                    # }
    return {"names": names, "rows": rows, "sub": sub}


def parse_mae(path):
    """Return a list of ct dicts: {props, atoms, bonds, cell}."""
    opener = gzip.open if path.endswith((".gz", ".maegz")) else open
    with opener(path, "rt", errors="replace") as fh:
        cur = _Cursor(_tokenize(fh.read()))

    cts = []
    while cur.peek() is not None:
        name = cur.next()
        n = _size(cur)
        if cur.peek() != "{":                     # stray token, skip
            continue
        cur.next()
        blk = _parse_block(cur, n)
        if not name.endswith("_m_ct"):            # the leading m2io version block
            continue
        cts.append(_build_ct(blk))

    full = [c for c in cts if c["props"].get("s_ffio_ct_type") == "full_system"]
    return full or cts                            # .cms: full_system wins


def _build_ct(blk):
    props = dict(zip(blk["names"], blk["rows"][0])) if blk["rows"] else {}

    atoms = []
    ab = blk["sub"].get("m_atom")
    if ab:
        col = {n: i for i, n in enumerate(ab["names"])}

        def get(row, key, default=""):
            i = col.get(key)
            if i is None:
                return default
            v = row[i]
            return default if v == "<>" else v

        for row in ab["rows"]:
            anum = int(float(get(row, "i_m_atomic_number", "0") or 0))
            atoms.append({
                "coord": (float(get(row, "r_m_x_coord", "0")),
                          float(get(row, "r_m_y_coord", "0")),
                          float(get(row, "r_m_z_coord", "0"))),
                "elem": ELEMENTS[anum] if 0 <= anum < len(ELEMENTS) else "",
                "name": get(row, "s_m_pdb_atom_name").strip(),
                "resn": get(row, "s_m_pdb_residue_name").strip(),
                "resi": get(row, "i_m_residue_number", "1").strip(),
                "chain": get(row, "s_m_chain_name").strip(),
                "segi": get(row, "s_m_pdb_segment_name").strip(),
                "b": float(get(row, "r_m_pdb_tfactor", "0") or 0),
                "q": float(get(row, "r_m_pdb_occupancy", "1") or 1),
                "formal_charge": int(float(get(row, "i_m_formal_charge", "0") or 0)),
                "pseudo": False,
            })

    # Virtual sites live in ffio_ff/ffio_pseudo, not m_atom.  They must be
    # included or the atom count will not match the matching trajectory.
    ff = blk["sub"].get("ffio_ff")
    pb = ff["sub"].get("ffio_pseudo") if ff else None
    if pb:
        col = {n: i for i, n in enumerate(pb["names"])}

        def pget(row, key, default=""):
            i = col.get(key)
            if i is None:
                return default
            v = row[i]
            return default if v == "<>" else v

        for row in pb["rows"]:
            atoms.append({
                "coord": (float(pget(row, "r_ffio_x_coord", "0")),
                          float(pget(row, "r_ffio_y_coord", "0")),
                          float(pget(row, "r_ffio_z_coord", "0"))),
                "elem": "", "pseudo": True,
                "name": pget(row, "s_ffio_atom_name").strip() or "Vrt",
                "resn": pget(row, "s_ffio_pdb_residue_name").strip(),
                "resi": pget(row, "i_ffio_residue_number", "1").strip(),
                "chain": pget(row, "s_ffio_chain_name").strip(),
                "segi": "", "b": 0.0, "q": 0.0, "formal_charge": 0,
            })

    bonds = []
    bb = blk["sub"].get("m_bond")
    if bb:
        col = {n: i for i, n in enumerate(bb["names"])}
        fi, ti = col.get("i_m_from"), col.get("i_m_to")
        oi = col.get("i_m_order")
        for row in bb["rows"]:
            a, b = int(row[fi]) - 1, int(row[ti]) - 1
            if a > b:
                continue                          # mae lists each bond twice
            order = int(float(row[oi])) if oi is not None else 1
            bonds.append((a, b, max(1, order)))

    # ffio_virtuals gives the parent only as a per-site template, whose
    # expansion needs the full force-field topology.  A virtual site always sits
    # within ~1 A of its parent, so bond it to the nearest real atom instead --
    # residue numbers are NOT usable here (ffio numbers from 1, m_atom from 0).
    # Without these bonds each site is its own component and wrapping scatters
    # them away from the molecule they belong to.
    if any(a.get("pseudo") for a in atoms):
        cs = 3.0
        grid = {}
        for i, a in enumerate(atoms):
            if not a.get("pseudo"):
                x, y, z = a["coord"]
                grid.setdefault((int(x // cs), int(y // cs), int(z // cs)), []).append(i)
        for i, a in enumerate(atoms):
            if not a.get("pseudo"):
                continue
            x, y, z = a["coord"]
            gx, gy, gz = int(x // cs), int(y // cs), int(z // cs)
            best, bd = None, 1e18
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for j in grid.get((gx + dx, gy + dy, gz + dz), ()):
                            p = atoms[j]["coord"]
                            d = (p[0] - x) ** 2 + (p[1] - y) ** 2 + (p[2] - z) ** 2
                            if d < bd:
                                best, bd = j, d
            if best is not None:
                bonds.append((min(i, best), max(i, best), 1))

    return {"props": props, "atoms": atoms, "bonds": bonds, "cell": _cell(props)}


def _cell(props):
    keys = ["r_chorus_box_%s%s" % (v, x) for v in "abc" for x in "xyz"]
    if not all(k in props for k in keys):
        return None
    import math
    v = [float(props[k]) for k in keys]
    va, vb, vc = v[0:3], v[3:6], v[6:9]

    def norm(u):
        return math.sqrt(sum(x * x for x in u))

    def ang(u, w):
        d = sum(x * y for x, y in zip(u, w)) / (norm(u) * norm(w))
        return math.degrees(math.acos(max(-1.0, min(1.0, d))))

    if min(norm(va), norm(vb), norm(vc)) < 1e-6:
        return None
    return [norm(va), norm(vb), norm(vc), ang(vb, vc), ang(va, vc), ang(va, vb)]


def load_mae(filename, object="", state=0, quiet=1, multiplex=-1, zoom=-1,
             _self=None):
    from chempy import Atom, Bond
    from chempy.models import Indexed
    if _self is None:
        from pymol import cmd as _self

    cts = parse_mae(filename)
    if not cts:
        raise Exception("no ct blocks in %s" % filename)

    base = object or re.sub(r"\.(mae|maegz|cms)(\.gz)?$", "",
                            os.path.basename(filename), flags=re.I)
    counts = set(len(c["atoms"]) for c in cts)
    as_states = (multiplex == 0) or (multiplex < 0 and len(counts) == 1)

    for k, ct in enumerate(cts):
        model = Indexed()
        for a in ct["atoms"]:
            at = Atom()
            at.coord = list(a["coord"])
            at.symbol = a["elem"]
            at.name = a["name"] or a["elem"]
            at.resn = a["resn"]
            at.resi = a["resi"]
            at.chain = a["chain"]
            at.segi = a["segi"]
            at.b, at.q = a["b"], a["q"]
            at.formal_charge = a["formal_charge"]
            at.hetatm = a["resn"] not in _POLYMER
            model.atom.append(at)
        for i, j, o in ct["bonds"]:
            bd = Bond()
            bd.index = [i, j]
            bd.order = o
            model.bond.append(bd)

        name = base if as_states else "%s_%d" % (base, k + 1)
        st = (state if state > 0 else k + 1) if as_states else 1
        _self.load_model(model, name, state=st, zoom=zoom)
        if ct["cell"]:
            _self.set_symmetry(name, *(ct["cell"] + ["P 1"]))
        if not quiet:
            print(" MAE: %s state %d: %d atoms, %d bonds%s"
                  % (name, st, len(ct["atoms"]), len(ct["bonds"]),
                     ", cell" if ct["cell"] else ""))
    return base


_POLYMER = set(
    "ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP "
    "TYR VAL HID HIE HIP HISB HISD HISE LYSH ASPH GLUH CYX CYM A C G U DA DC "
    "DG DT ACE NMA NME".split())


def register(_self=None):
    if _self is None:
        from pymol import cmd as _self
    import pymol.importing as I
    for ext in ("mae", "maegz", "cms"):
        I.loadfunctions[ext] = load_mae
    _self.extend("load_mae", load_mae)


try:
    register()
except Exception as _e:                            # importable outside PyMOL
    pass
