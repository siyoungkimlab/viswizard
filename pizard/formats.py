"""
formats.py -- DMS reader/writer and MAE writer.

Works two ways:

  * inside PyMOL, registering itself so `load x.dms` and `save x.dms` /
    `save x.mae` behave like any other format;
  * standalone, as a converter VMD can shell out to (VMD has no DMS plugin
    and its .mae plugin is read-only):

        python3 formats.py in.dms out.mae

DMS is a SQLite database: particle / bond / global_cell.  MAE is a
block-structured text format.  Both carry explicit bonds, so nothing is guessed by distance.
"""
import os
import sqlite3
import sys

__all__ = ["read_dms", "write_dms", "write_mae", "convert",
           "load_dms", "save_dms", "save_mae"]

ELEMENTS = (
    "LP H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe "
    "Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn "
    "Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W "
    "Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf "
    "Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split()
_SYM2NUM = {s.upper(): i for i, s in enumerate(ELEMENTS)}


# --------------------------------------------------------------------- DMS
def read_dms(path):
    """-> {'atoms': [...], 'bonds': [(i, j, order)], 'cell': 3x3 or None}"""
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    con.row_factory = sqlite3.Row
    have = {r[0] for r in con.execute(
        "select name from sqlite_master where type='table'")}
    if "particle" not in have:
        raise ValueError("%s is not a DMS file (no particle table)" % path)

    cols = {r[1] for r in con.execute("pragma table_info(particle)")}

    def col(row, name, default=None):
        return row[name] if name in cols and row[name] is not None else default

    atoms, ids = [], {}
    for row in con.execute("select * from particle order by id"):
        ids[row["id"]] = len(atoms)
        anum = int(col(row, "anum", 0) or 0)
        atoms.append({
            "anum": anum,
            "elem": ELEMENTS[anum] if 0 <= anum < len(ELEMENTS) else "",
            "name": (col(row, "name", "") or "").strip(),
            "resname": (col(row, "resname", "") or "").strip(),
            "resid": int(col(row, "resid", 1) or 1),
            "chain": (col(row, "chain", "") or "").strip(),
            "segid": (col(row, "segid", "") or "").strip(),
            "x": float(col(row, "x", 0.0) or 0.0),
            "y": float(col(row, "y", 0.0) or 0.0),
            "z": float(col(row, "z", 0.0) or 0.0),
            "mass": float(col(row, "mass", 0.0) or 0.0),
            "charge": float(col(row, "charge", 0.0) or 0.0),
            "formal_charge": int(col(row, "formal_charge", 0) or 0),
        })

    bonds = []
    if "bond" in have:
        bcols = {r[1] for r in con.execute("pragma table_info(bond)")}
        for row in con.execute("select * from bond"):
            a, b = ids.get(row["p0"]), ids.get(row["p1"])
            if a is None or b is None:
                continue
            o = int(row["order"]) if "order" in bcols and row["order"] else 1
            bonds.append((min(a, b), max(a, b), max(1, o)))

    cell = None
    if "global_cell" in have:
        v = [(r["x"], r["y"], r["z"])
             for r in con.execute("select * from global_cell order by id")]
        if len(v) == 3 and any(abs(c) > 1e-9 for row in v for c in row):
            cell = [list(map(float, r)) for r in v]
    con.close()
    return {"atoms": atoms, "bonds": bonds, "cell": cell}


def write_dms(path, atoms, bonds, cell=None):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute("create table dms_version (major integer, minor integer)")
    con.execute("insert into dms_version values (1, 7)")
    con.execute("""create table particle (
        id integer primary key, anum integer, name text, x float, y float,
        z float, vx float, vy float, vz float, resname text, resid integer,
        chain text, segid text, mass float, charge float,
        formal_charge integer)""")
    con.executemany(
        "insert into particle (id,anum,name,x,y,z,vx,vy,vz,resname,resid,"
        "chain,segid,mass,charge,formal_charge) "
        "values (?,?,?,?,?,?,0,0,0,?,?,?,?,?,?,?)",
        [(i, a.get("anum", 0), a.get("name", ""), a["x"], a["y"], a["z"],
          a.get("resname", ""), a.get("resid", 1), a.get("chain", ""),
          a.get("segid", ""), a.get("mass", 0.0), a.get("charge", 0.0),
          a.get("formal_charge", 0)) for i, a in enumerate(atoms)])
    con.execute("create table bond (p0 integer, p1 integer, 'order' integer)")
    con.executemany("insert into bond values (?,?,?)",
                    [(int(i), int(j), int(o)) for i, j, o in bonds])
    con.execute("create table global_cell (id integer primary key, "
                "x float, y float, z float)")
    c = cell or [[0.0, 0.0, 0.0]] * 3
    con.executemany("insert into global_cell values (?,?,?,?)",
                    [(k, c[k][0], c[k][1], c[k][2]) for k in range(3)])
    con.execute("create table provenance (id integer primary key, version text,"
                " timestamp text, user text, workdir text, cmdline text,"
                " executable text)")
    con.execute("insert into provenance (id, version, cmdline, executable) "
                "values (0, 'vizard', ?, 'formats.py')", (" ".join(sys.argv),))
    con.commit()
    con.close()
    return path


# --------------------------------------------------------------------- MAE
def _q(s):
    s = "" if s is None else str(s)
    if s == "":
        return '""'
    if any(ch in s for ch in ' \t"\\{}[]'):
        return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')
    return s


def write_mae(path, atoms, bonds, cell=None, title="vizard"):
    out = ["{", "  s_m_m2io_version", "  :::", "  2.0.0", "}", ""]
    props = [("s_m_title", title)]
    if cell:
        for vi, vname in enumerate("abc"):
            for ci, cname in enumerate("xyz"):
                props.append(("r_chorus_box_%s%s" % (vname, cname),
                              "%.6f" % cell[vi][ci]))
    out.append("f_m_ct {")
    for k, _ in props:
        out.append("  " + k)
    out.append("  :::")
    for k, v in props:
        out.append("  " + (_q(v) if k.startswith("s_") else str(v)))

    acols = ["i_m_atomic_number", "r_m_x_coord", "r_m_y_coord", "r_m_z_coord",
             "i_m_residue_number", "s_m_pdb_residue_name", "s_m_pdb_atom_name",
             "s_m_chain_name", "s_m_pdb_segment_name", "i_m_formal_charge",
             "r_m_charge1"]
    out.append("  m_atom[%d] {" % len(atoms))
    for c in acols:
        out.append("    " + c)
    out.append("    :::")
    for i, a in enumerate(atoms, 1):
        out.append("    %d %d %.6f %.6f %.6f %d %s %s %s %s %d %.6f" % (
            i, a.get("anum", 0), a["x"], a["y"], a["z"], a.get("resid", 1),
            _q(a.get("resname", "")), _q(a.get("name", "")),
            _q(a.get("chain", "")), _q(a.get("segid", "")),
            a.get("formal_charge", 0), a.get("charge", 0.0)))
    out += ["    :::", "  }"]

    if bonds:
        out.append("  m_bond[%d] {" % len(bonds))
        for c in ("i_m_from", "i_m_to", "i_m_order"):
            out.append("    " + c)
        out.append("    :::")
        for k, (i, j, o) in enumerate(bonds, 1):
            out.append("    %d %d %d %d" % (k, i + 1, j + 1, o))
        out += ["    :::", "  }"]
    out += ["}", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    return path


# ----------------------------------------------------------------- convert
def _read_any(path):
    if path.lower().endswith(".vizdump"):
        return read_dump(path)
    if path.lower().endswith(".dms"):
        return read_dms(path)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from mae_reader import parse_mae
    cts = parse_mae(path)
    atoms, bonds, off = [], [], 0
    for ct in cts:
        for a in ct["atoms"]:
            atoms.append({"anum": _SYM2NUM.get(a["elem"].upper(), 0),
                          "elem": a["elem"], "name": a["name"],
                          "resname": a["resn"],
                          "resid": int(a["resi"] or 1) if str(a["resi"]).lstrip("-").isdigit() else 1,
                          "chain": a["chain"], "segid": a["segi"],
                          "x": a["coord"][0], "y": a["coord"][1], "z": a["coord"][2],
                          "mass": 0.0, "charge": 0.0,
                          "formal_charge": a["formal_charge"]})
        for i, j, o in ct["bonds"]:
            bonds.append((i + off, j + off, o))
        off += len(ct["atoms"])
    cell = None
    if cts and cts[0]["cell"]:
        import math
        a, b, c, al, be, ga = cts[0]["cell"]
        ca, cb, cg = (math.cos(math.radians(v)) for v in (al, be, ga))
        sg = math.sin(math.radians(ga))
        cell = [[a, 0.0, 0.0], [b * cg, b * sg, 0.0],
                [c * cb, c * (ca - cb * cg) / sg,
                 c * math.sqrt(max(0.0, 1 - cb * cb - ((ca - cb * cg) / sg) ** 2))]]
    return {"atoms": atoms, "bonds": bonds, "cell": cell}


def read_dump(path):
    """Read the simple text dump VMD writes (it has no sqlite3 in Tcl)."""
    atoms, bonds, cell = [], [], None
    with open(path) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[0] == "CELL":
                v = [float(x) for x in f[1:10]]
                if any(abs(x) > 1e-9 for x in v):
                    cell = [v[0:3], v[3:6], v[6:9]]
            elif f[0] == "ATOM":
                atoms.append({"anum": int(f[1]), "name": f[2], "resname": f[3],
                              "resid": int(float(f[4])), "chain": f[5], "segid": f[6],
                              "x": float(f[7]), "y": float(f[8]), "z": float(f[9]),
                              "mass": float(f[10]), "charge": float(f[11]),
                              "formal_charge": 0})
            elif f[0] == "BOND":
                bonds.append((int(f[1]), int(f[2]), int(float(f[3])) or 1))
    return {"atoms": atoms, "bonds": bonds, "cell": cell}


def convert(src, dst):
    d = _read_any(src)
    if dst.lower().endswith(".dms"):
        write_dms(dst, d["atoms"], d["bonds"], d["cell"])
    else:
        write_mae(dst, d["atoms"], d["bonds"], d["cell"],
                  title=os.path.basename(src))
    return len(d["atoms"]), len(d["bonds"])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: formats.py <in.dms|in.mae> <out.dms|out.mae>")
    na, nb = convert(sys.argv[1], sys.argv[2])
    print("formats: wrote %s (%d atoms, %d bonds)" % (sys.argv[2], na, nb))


# ------------------------------------------------------------------ PyMOL
def _model_to_lists(obj_or_sel):
    from pymol import cmd
    m = cmd.get_model(obj_or_sel)
    atoms = []
    for a in m.atom:
        sym = (a.symbol or "").strip()
        atoms.append({
            "anum": _SYM2NUM.get(sym.upper(), 0), "elem": sym,
            "name": a.name, "resname": a.resn,
            "resid": int(a.resi) if str(a.resi).lstrip("-").isdigit() else 1,
            "chain": a.chain, "segid": a.segi,
            "x": a.coord[0], "y": a.coord[1], "z": a.coord[2],
            "mass": getattr(a, "get_mass", lambda: 0.0)() if hasattr(a, "get_mass") else 0.0,
            "charge": getattr(a, "partial_charge", 0.0) or 0.0,
            "formal_charge": getattr(a, "formal_charge", 0) or 0,
        })
    bonds = [(min(b.index), max(b.index), getattr(b, "order", 1) or 1)
             for b in m.bond]
    # get_symmetry needs exactly one object, but a selection may span several
    # ("polymer or resn LIG" once more than one structure is loaded). Take the
    # cell from the first object the selection touches.
    objs = cmd.get_object_list(obj_or_sel)
    sym = cmd.get_symmetry(objs[0]) if objs else None
    cell = None
    if sym and all(v > 1e-6 for v in sym[:3]):
        import math
        a, b, c, al, be, ga = sym[:6]
        ca, cb, cg = (math.cos(math.radians(v)) for v in (al, be, ga))
        sg = math.sin(math.radians(ga))
        cell = [[a, 0.0, 0.0], [b * cg, b * sg, 0.0],
                [c * cb, c * (ca - cb * cg) / sg,
                 c * math.sqrt(max(0.0, 1 - cb * cb - ((ca - cb * cg) / sg) ** 2))]]
    return atoms, bonds, cell


def load_dms(filename, object="", state=0, quiet=1, zoom=-1, _self=None):
    from chempy import Atom, Bond
    from chempy.models import Indexed
    if _self is None:
        from pymol import cmd as _self
    d = read_dms(filename)
    model = Indexed()
    for a in d["atoms"]:
        at = Atom()
        at.coord = [a["x"], a["y"], a["z"]]
        at.symbol = a["elem"]
        at.name = a["name"] or a["elem"]
        at.resn, at.chain, at.segi = a["resname"], a["chain"], a["segid"]
        at.resi = str(a["resid"])
        at.formal_charge = a["formal_charge"]
        at.partial_charge = a["charge"]
        model.atom.append(at)
    for i, j, o in d["bonds"]:
        bd = Bond(); bd.index = [i, j]; bd.order = o
        model.bond.append(bd)
    name = object or os.path.splitext(os.path.basename(filename))[0]
    _self.load_model(model, name, state=state if state > 0 else 1, zoom=zoom)
    if d["cell"]:
        import math
        v = d["cell"]

        def norm(u):
            return math.sqrt(sum(x * x for x in u))

        def ang(u, w):
            return math.degrees(math.acos(max(-1.0, min(1.0,
                   sum(p * q for p, q in zip(u, w)) / (norm(u) * norm(w))))))
        _self.set_symmetry(name, norm(v[0]), norm(v[1]), norm(v[2]),
                           ang(v[1], v[2]), ang(v[0], v[2]), ang(v[0], v[1]), "P 1")
    if not quiet:
        print(" DMS: %s: %d atoms, %d bonds" % (name, len(d["atoms"]), len(d["bonds"])))
    return name


def save_dms(filename, selection="(all)", state=-1, quiet=1, _self=None):
    atoms, bonds, cell = _model_to_lists(selection)
    write_dms(filename, atoms, bonds, cell)
    if not quiet:
        print(" DMS: wrote %s (%d atoms, %d bonds)" % (filename, len(atoms), len(bonds)))
    return filename


def save_mae(filename, selection="(all)", state=-1, quiet=1, _self=None):
    atoms, bonds, cell = _model_to_lists(selection)
    write_mae(filename, atoms, bonds, cell,
              title=os.path.splitext(os.path.basename(filename))[0])
    if not quiet:
        print(" MAE: wrote %s (%d atoms, %d bonds)" % (filename, len(atoms), len(bonds)))
    return filename


def register(_self=None, force_mae=False):
    if _self is None:
        from pymol import cmd as _self
    import pymol.importing as I
    import pymol.exporting as E
    I.loadfunctions["dms"] = load_dms
    E.savefunctions["dms"] = save_dms
    # do not shadow the incentive build's own MAE writer unless asked
    if force_mae or "mae" not in E.savefunctions:
        E.savefunctions["mae"] = save_mae
    _self.extend("load_dms", load_dms)
    _self.extend("save_dms", save_dms)
    _self.extend("save_mae", save_mae)


try:
    register()
except Exception:
    pass
