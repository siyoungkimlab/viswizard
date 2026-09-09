"""
vizard.py -- glue + align + set up a view, at PyMOL start-up.

    pymol ~/viswizard/pizard/pizard.py -- sys.pdb traj.dcd --ligand "resn LIG"
    pymol ~/viswizard/pizard/pizard.py -- sys.pdb traj.dcd \
        --glue "polymer or resn LIG" --align "polymer and name CA and resi 145-149"

PyMOL cannot load a trajectory on its own -- it needs an object to attach to --
so the files go to this script, not to pymol.  Everything after `--` is argv.

Unlike VMD, PyMOL accepts "resi 145-149" as a range.
"""
import argparse
import os
import re
import sys

from pymol import cmd

# NOTE: inside a script run by PyMOL, __file__ points at PyMOL's own
# __init__.py, not at this file.  sys.argv[0] is the script path.
# Finding our own directory is awkward here: inside a script run by PyMOL,
# __file__ points at PyMOL's own __init__.py, and sys.argv[0] is the LAST
# script on the command line, not this one.  So try, in order: the env var the
# pizard wrapper exports, any argv entry that is this file, the usual install
# location, and the cwd.
_cands = []
if os.environ.get("PIZARD_DIR"):
    _cands.append(os.environ["PIZARD_DIR"])
for _a in sys.argv:
    if os.path.basename(str(_a)) == "pizard.py":
        _cands.append(os.path.dirname(os.path.abspath(_a)))
_cands += [os.path.expanduser("~/viswizard/pizard"), os.getcwd()]
for _d in _cands:
    if _d and os.path.isfile(os.path.join(_d, "glue.py")):
        if _d not in sys.path:
            sys.path.insert(0, _d)
        break
else:
    raise SystemExit("pizard: cannot find glue.py (looked in: %s)" % _cands)
from glue import glue_traj


HELP = """
pizard -- glue a ligand to its protein across PBC, align, and set up a view,
in PyMOL.  (vizard is the same thing for VMD.)

  pizard topology [trajectory] [options]
  pizard sys.pdb traj.dcd --ligand "resn LIG"
  pizard sys.dms --ligand "resn LIG" --pocket 8
  pizard sys.pdb traj.dcd --glue "polymer or resn LIG" \\
         --align "polymer and name CA and resi 145-165"

Options (all optional):
  --ligand SEL   ligand selection: reps, colouring, pocket, view centre
                                                   (default "resn LIG")
  --glue SEL     held together across the periodic boundary
                                                   (default "polymer or (<ligand>)")
  --align SEL    what the trajectory is fitted on  (default "polymer and name CA")
  --pocket A     pocket residue cutoff, angstroms  (default 6)
  --ref FILE|ID  reference structure, a file or a 4-character PDB id (fetched
                 and cached).  The trajectory is put onto it with cealign,
                 which is structure-based, so numbering need not match.
  --object NAME  object name to load into          (default "sys")

  --lig and --fit are accepted as aliases for --ligand and --align.

PyMOL selection syntax, NOT VMD's: resn / resi / polymer, and ranges are
written "resi 145-165".  The VMD side wants "resname" / "resid 145 to 165".

DMS and MAE load directly; ~/.pymolrc.py registers the handlers.
"""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        print(HELP)
        return
    p = argparse.ArgumentParser(prog="pizard", add_help=False)
    p.add_argument("files", nargs="+")
    p.add_argument("--ligand", "--lig", dest="ligand", default="resn LIG")
    p.add_argument("--glue", dest="glue", default=None)
    p.add_argument("--align", "--fit", dest="align", default="polymer and name CA")
    p.add_argument("--pocket", dest="pocket", type=float, default=6.0,
                   help="pocket residue distance cutoff in A (default 6)")
    p.add_argument("--ref", dest="ref", default=None,
                   help="reference structure; the trajectory is put onto it "
                        "with cealign after the internal alignment")
    p.add_argument("--object", dest="obj", default="sys")
    o = p.parse_args(argv)

    # Group the files.  A structure (or a bare 4-character PDB id) starts a new
    # object; trajectories after it attach to that object.  So
    #   a.pdb a.dcd b.pdb b.dcd 1abc 2xyz
    # is four systems, two of them fetched.
    TRAJ = (".dcd", ".xtc", ".trr", ".dtr", ".nc", ".netcdf", ".crd", ".trj")
    PDBID = re.compile(r"^[0-9][0-9A-Za-z]{3}$")
    CACHE = os.path.expanduser("~/.viswizard_cache")

    def load_one(spec, name):
        if os.path.exists(spec):
            cmd.load(spec, name)
            return spec
        if PDBID.match(spec):
            os.makedirs(CACHE, exist_ok=True)
            cmd.set("fetch_path", CACHE)
            cmd.fetch(spec, name, async_=0)
            if cmd.count_atoms(name) == 0:
                raise SystemExit("pizard: could not fetch '%s'" % spec)
            return spec.upper()
        raise SystemExit("pizard: no such file, and '%s' is not a 4-character "
                         "PDB id" % spec)

    groups = []
    for f in o.files:
        if f.lower().endswith(TRAJ) and groups:
            groups[-1][1].append(f)
        else:
            groups.append((f, []))

    objs = []
    for i, (top, trajs) in enumerate(groups):
        base = os.path.splitext(os.path.basename(top))[0]
        if len(groups) == 1:
            name = o.obj
        else:
            name = re.sub(r"\W+", "_", base) or "sys%d" % (i + 1)
        while name in cmd.get_object_list():
            name += "_"
        before = set(cmd.get_object_list())
        load_one(top, name)
        # PyMOL silently renames an object whose name is a reserved selection
        # keyword ("b" -> "b_", and likewise x, y, z, q, ss, index ...), so ask
        # what it actually created rather than assuming.
        created = [n for n in cmd.get_object_list() if n not in before]
        if created:
            name = created[0]
        for t in trajs:
            cmd.load_traj(t, name, state=1)   # state=1 overwrites topology frame
        objs.append(name)
        print("pizard: %-16s %6d atoms, %3d states" %
              (name, cmd.count_atoms(name), cmd.count_states(name)))

    gluesel = o.glue or "polymer or (%s)" % o.ligand
    print("pizard: ligand '%s'   glue '%s'   align '%s'"
          % (o.ligand, gluesel, o.align))

    # ---- glue + internal alignment, per object ------------------------------
    for name in objs:
        nl = cmd.count_atoms("(%s) and (%s)" % (name, o.ligand))
        na = cmd.count_atoms("(%s) and (%s)" % (name, o.align))
        if na < 3:
            print("pizard: %s -- align selection matches %d atoms, skipping" % (name, na))
            continue
        g = gluesel if nl else "polymer"
        if not nl:
            print("pizard: %s -- no ligand matched; gluing polymer only" % name)
        glue_traj(glue=g, align=o.align, obj=name, quiet=1)

    # ---- put everything into one frame of reference ------------------------
    # glue_traj has already fitted every state onto state 1, so moving an
    # object rigidly carries its whole trajectory.  cealign is structure-based,
    # so residue numbering need not match.
    def put_onto(target, mobile, what):
        try:
            r = cmd.cealign(target, mobile)
            msg = "pizard: %s onto %s -- RMSD %.3f over %d atoms" % (
                mobile, what, r["RMSD"], r["alignment_length"])
            if r["RMSD"] > 5.0:
                msg += "   <- high; same protein?"
            print(msg)
        except Exception as e:
            print("pizard: could not align %s onto %s (%s)" % (mobile, what, e))

    if o.ref:
        load_one(o.ref, "ref")
        put_onto("ref", objs[0], "reference " + o.ref)
        cmd.show("cartoon", "ref and polymer")
        cmd.set("cartoon_color", "grey60", "ref")
        cmd.set("cartoon_transparency", 0.55, "ref")
    for name in objs[1:]:
        put_onto(objs[0], name, objs[0])

    # ---- display -----------------------------------------------------------
    cmd.bg_color("black")
    cmd.set("orthoscopic", 1)
    cmd.set("ray_shadows", 0)
    cmd.set("ambient_occlusion_mode", 1)
    cmd.set("valence", 1)

    # PyMOL's own element colours (C/N/O/S/H) are nicer than anything I would
    # invent, so colour every atom with the scheme's carbon colour and then let
    # util.cnc restore the element colours for the non-carbons.
    #
    # cartoon_color is set on the OBJECT, not by colouring atoms: colouring
    # pocket atoms would recolour the cartoon drawn from those same residues.
    # PyMOL's named colours are either saturated (forest, teal) or pale
    # (palegreen); the muted mid-darks a cartoon wants are not in the set, so
    # define them.  One hue per object: dark cartoon, mid pocket, bright ligand.
    # PyMOL's own palette, not colours I invented.  The eight pairs were chosen
    # by searching every (deep, light) combination for the one that maximises
    # the minimum separation between schemes -- both between cartoons AND
    # between ligand carbons -- then ordered so consecutive molecules are as
    # far apart as possible.  My previous hand-picked set had molecules 1 and 2
    # only 0.29 apart in RGB; these are 0.64.
    #             cartoon      pocket carbons        ligand carbons
    schemes = [("forest",      (0.400,0.733,0.400), "palegreen"),
               ("raspberry",   (0.835,0.502,0.612), "lightpink"),
               ("olive",       (0.875,0.835,0.224), "paleyellow"),
               ("deepblue",    (0.475,0.475,0.808), "lightblue"),
               ("firebrick",   (0.835,0.341,0.341), "salmon"),
               ("deepteal",    (0.416,0.780,0.780), "palecyan"),
               ("deeppurple",  (0.780,0.278,0.780), "violet"),
               ("brown",       (0.804,0.545,0.384), "wheat")]
    for i, (c, mid, l) in enumerate(schemes):
        cmd.set_color("vw_pocket%d" % i, list(mid))

    nonpolar_h = "hydro and not (neighbor (elem N+O+S))"
    focus = []
    for i, name in enumerate(objs):
        si = i % len(schemes)
        cartoon_c, _mid, lig_c = schemes[si]
        pocket_c = "vw_pocket%d" % si
        hue = cartoon_c
        lig = "(%s) and (%s)" % (name, o.ligand)
        has_lig = cmd.count_atoms(lig) > 0
        pocket = "byres ((%s) and polymer within %g of (%s))" % (name, o.pocket, lig)

        cmd.hide("everything", name)
        cmd.show("cartoon", "(%s) and polymer" % name)
        cmd.set("cartoon_color", cartoon_c, name)
        cmd.set("cartoon_transparency", 0.0, name)
        if has_lig:
            cmd.show("lines", "(%s) and not (%s)" % (pocket, nonpolar_h))
            cmd.show("sticks", "(%s) and not (%s)" % (lig, nonpolar_h))
            cmd.color(pocket_c, pocket)
            cmd.util.cnc(pocket)
            cmd.color(lig_c, lig)
            cmd.util.cnc(lig)
            focus += [lig, pocket]
        print("pizard: %-16s %s%s" % (name, hue, "" if has_lig else "  (no ligand)"))

    cmd.set("stick_radius", 0.15)
    cmd.set("line_width", 1.4)
    cmd.zoom(" or ".join("(%s)" % f for f in focus) if focus else "polymer", buffer=2.0)
    cmd.mset("1 -%d" % max(cmd.count_states(n) for n in objs))
    print("pizard: ready -- %d object(s), %d states"
          % (len(objs), max(cmd.count_states(n) for n in objs)))


main()
