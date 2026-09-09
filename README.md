# viswizard

A VMD and PyMOL toolkit for protein–ligand molecular dynamics. It keeps a
ligand with its protein across periodic boundaries, aligns the trajectory, and
sets up a view worth looking at — from one command line.

```bash
vizard sys.pdb traj.dcd --ligand "resname LIG"     # VMD
pizard sys.pdb traj.dcd --ligand "resn LIG"        # PyMOL
```

**Documentation:** https://viswizard.readthedocs.io

```
viswizard/
  vizard/     VMD side    ->  the `vizard` command
  pizard/     PyMOL side  ->  the `pizard` command
```

Two commands rather than one with a flag, because the two programs speak
different selection languages — `resname LIG` against `resn LIG`, `resid 145
to 149` against `resi 145-149` — and the command name is the reminder of which
dialect to type.

## Installation

```bash
git clone https://github.com/siyoungkimlab/viswizard.git ~/viswizard
bash ~/viswizard/install.sh
```

Creates `~/.local/bin/vizard` and `~/.local/bin/pizard`, and writes a marked
block into `~/.vmdrc` and `~/.pymolrc.py` so the in-session commands and the
DMS/MAE handlers exist everywhere. Re-running it is safe.

## What it does

In a periodic simulation a ligand that is not bonded to its protein wraps
independently, so it jumps across the box between frames. Nothing in VMD keeps
two unbonded molecules together, and re-wrapping after an alignment undoes the
alignment. viswizard does the four steps in the only order that works: make
molecules whole, glue the ligand to the protein, wrap everything else, then
fit — fitting last, to a reference that has itself been made whole.

| | Protein–ligand | Cα RMSD |
|---|---|---|
| raw | 1.7 – 67.1 Å | up to 68.7 Å |
| processed | 1.74 – 2.14 Å | 0.83 – 1.23 Å |

The residual RMSD is real conformational drift.

## Highlights

- **Several systems at once.** A structure — or a bare four-character PDB id —
  starts a new molecule, and trajectories after it attach to it. Each gets its
  own colour and is superposed onto the first.
  ```bash
  vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resname LIG" --ref 1ubq
  ```
- **Formats VMD cannot handle.** It reads `.mae` but cannot write it and has no
  DMS plugin at all; its Tcl has no `sqlite3`. Both are supplied, and work in
  PyMOL too.
- **Movies in one line.** `vizard_movie -out movie.mp4` renders what you are
  looking at with Tachyon's in-memory renderer and ffmpeg. Works headless.
- **Sequence-based superposition for VMD.** `mm 1 0` aligns by sequence first,
  so residue numbering need not match — which `measure fit` cannot do.
- **A palette built for overlays.** Eight schemes, each one hue: dark cartoon,
  bright ligand carbons, with element colours preserved for heteroatoms. See
  [the colour page](https://viswizard.readthedocs.io/en/latest/colors.html).

## Requirements

VMD and/or PyMOL, Python 3.9+ with numpy, and ffmpeg for movies. Nothing else.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
