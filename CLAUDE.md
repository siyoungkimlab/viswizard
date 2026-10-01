# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two parallel implementations of the same tool, not one tool with two frontends:
`vizard/` is Tcl for VMD, `pizard/` is Python for PyMOL. They deliberately
duplicate behaviour rather than share a core, because the two viewers speak
different selection languages (`resname LIG` / `resid 145 to 149` against
`resn LIG` / `resi 145-149`) and expose different primitives. A change to one
side almost always needs the mirror change on the other.

See `README.md` for what the tool does and `CONTRIBUTING.md` for the house
rules on comments, the palette, and verifying what cannot be unit tested.

## Commands

```bash
python -m pip install -e '.[dev]'                     # dev deps (pytest, pillow, sphinx, furo)
bash install.sh                                       # (re)generate the wrapper commands + rc blocks

pytest tests -q                                       # the suite CI runs
pytest tests/test_cg.py -q                            # one file
pytest tests/test_glue.py::test_threads_give_the_serial_result_in_state_order
pytest tests -q -k sirah                              # by name

tclsh tests/tcl_complete.tcl vizard/*.tcl             # Tcl files are complete scripts
bash -n install.sh                                    # shell parses
python -m sphinx -b html -W docs docs/_build/html      # docs, warnings are errors
python docs/make_swatches.py                          # after any palette change
```

There is no linter or type checker configured — do not invent `ruff`/`mypy`
steps. CI is `pytest` (ubuntu+macos × py3.11/3.13), the Tcl/shell syntax job,
`sphinx`, and an `all checks` aggregate job that branch protection requires.

### Verifying the parts CI cannot reach

Most of the real behaviour only exists inside VMD or PyMOL. Run them headless
and read the numbers they print:

```bash
# pizard: drive main() with argv, then measure in the same session
/Applications/PyMOL.app/Contents/bin/pymol -cq script.py   # script sets sys.argv then exec()s pizard/pizard.py

# vizard: the launcher owns -e, so send follow-up commands on stdin
cat check.tcl | ~/.local/bin/vizard -dispdev text sys.dms traj.dcd
```

What to check after touching the gluing: the longest bond stays near its raw
value (a break shows up as ~box length), the minimum protein–ligand distance is
constant across frames, the protein centre lands on the box middle, and
co-solvent centres stay within half a box of the protein.

Two traps worth knowing: PyMOL reserves single letters like `b` and `x`, so a
test object named `b` is silently renamed and every later selection on it fails;
and VMD matches `resname` case-sensitively while PyMOL's `resn` does not.

## Architecture

### The PBC pipeline

Both sides implement the same four steps in this order, then fit last — order
matters, since re-wrapping after a fit would undo it:

1. make every molecule whole by walking its **bonds** (never by distance);
2. place the glue selection's components on their jointly best images;
3. move every other molecule as a unit onto the image nearest the protein;
4. put the protein in the middle of the box; then Kabsch-fit each frame onto
   frame 1.

The "protein" in 3–4 is the whole molecule the **fit** selection sits on, not
the fit atoms and not the glued set's own centre. `pizard/glue.py` is a pure
numpy implementation (`_Topology` precomputes the BFS spanning tree, difference
array and component labels once; `_glue_block` runs whole-array over a block of
states). `vizard/glue.tcl` does the same with `tree_join` plus `pbc wrap`.

Parallelism differs by necessity: pizard runs numpy over blocks of states on
threads (each block carries its own state numbers, so a state's coordinates can
only go back to that state); vizard forks worker VMD processes over consecutive
frame ranges (`glue_worker.tcl`), which reload the structure file and refuse to
run if their `fragment` numbering differs from the parent's — so the parent
ships its bond list along.

### Coarse-grained models (Martini and SIRAH)

The single constraint that shapes all of this: **PyMOL decides what each residue
is while it reads the file and never revisits it.** A bead with a bogus element
is not part of a protein, and correcting it afterwards does not undo that — a
`cmd.sort()` brings back guide atoms and `cealign`, but `align` and `super` stay
broken. So `pizard/formats.py` (DMS) and `pizard/mae_reader.py` (MAE) fix the
model *as they build it*: real element per bead, backbone bead renamed `CA`,
beads of a known residue marked non-hetatm, and a SIRAH residue written as the
three-letter name PyMOL knows (`sL` → `LEU`, original kept in `custom`). The
bead's own name is kept in `text_type`, which is also how pizard knows a reader
has been there. A coarse-grained PDB or GRO is read by PyMOL before pizard sees
it, so `pizard.py` patches those up with `alter` + `cmd.sort()`.

VMD needs none of that — `::CG::protein` names the residues directly, and
`resname` keeps its case, which is what distinguishes a SIRAH `sS` from the
dipeptide probe `SS` in a pocket search. On the Python side that test must run
in Python (`cg.is_protein_residue`), never as a `resn` selection.

A pocket search fills the box with hundreds of dipeptide probes that carry
backbone beads of their own. Anything meaning "the protein" — the fit, the glue,
the pocket, the cartoon trace, the bead bonding, matchmaker, the fallback ligand
— must therefore be restricted to the protein's own residues, or it ends up
fitting on free solvent.

### Knowledge duplicated on purpose, with tests to hold it together

- Bead element/residue/solvent tables: `pizard/cg.py` ↔ `vizard/cg.tcl`,
  asserted equal by `tests/test_cg.py::test_tcl_and_python_tables_agree`
  (it regex-parses the Tcl).
- The palette lives in three places (`docs/make_swatches.py`,
  `vizard/align.tcl`, `pizard/pizard.py`) — see `CONTRIBUTING.md`.

### Entry points and loading

`install.sh` generates `~/.local/bin/{vizard,pizard}` from heredocs and writes
marked blocks into `~/.vmdrc` and `~/.pymolrc.py`. Edit `install.sh` and re-run
it; never edit the installed copies. The wrappers split the command line into
files / tool flags / viewer flags, and convert DMS and CMS to MAE for VMD into
`~/.viswizard_cache`, keyed on the file's whole path (two different
`solvated.dms` files otherwise shared one entry).

In-session Tcl commands are `vizard_*` procs with short aliases (`mm`, `view`,
`reps`, `fetch`, `movie`, `ao`, `browse`, `cgelem`). `pizard/` is not an
importable package: PyMOL loads it from a path, `tests/conftest.py` puts it on
`sys.path`, and the cores (`glue.py`, `cg.py`, `superpose.py`, `formats.py`,
`mae_reader.py`) must keep importing without PyMOL so CI can test them.

## Workflow

`main` takes changes through a PR with passing checks, squash-merged — the PR
description becomes the commit message, so write it as one: what was wrong, the
measured before/after, and what was checked and left unchanged.
