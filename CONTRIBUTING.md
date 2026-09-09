# Contributing to viswizard

## Setting up

```bash
python -m pip install -e '.[dev]'
bash install.sh
```

`install.sh` writes the two wrapper commands and the rc-file blocks. It is
idempotent — the blocks live between `# >>> viswizard >>>` markers and are
replaced, not appended.

## Working on a change

`main` takes changes through a pull request whose checks have passed.

```bash
git switch -c short-descriptive-branch-name
pytest tests -q                                      # the suite CI runs
tclsh tests/tcl_complete.tcl vizard/*.tcl            # Tcl parses
python -m sphinx -b html -W docs docs/_build/html    # docs, warnings as errors
```

## Testing what cannot be unit tested

The Python side — the DMS and MAE readers and writers, and the sequence
superposition — is covered by `pytest` and runs in CI without VMD or PyMOL.

The Tcl side cannot be. It is checked by running the real thing headless:

```bash
vizard -dispdev text sys.pdb traj.dcd --ligand "resname LIG"
pizard -cq sys.pdb traj.dcd --ligand "resn LIG"
```

Both report enough to tell success from failure without a window: atom counts
per selection, timing, the protein–ligand contact count, and `FAILED` with a
reason if a step did not run. When changing the gluing, check the numbers that
matter — the minimum protein–ligand distance should be constant across frames,
and the longest backbone bond should stay near 1.5 Å.

## Changing the colour palette

The palette is written down in three places: `docs/make_swatches.py` draws it,
`vizard/align.tcl` defines it for VMD, `pizard/pizard.py` for PyMOL.
`tests/test_palette.py` asserts all three agree, that consecutive schemes are
far enough apart to tell overlaid molecules apart, and CI regenerates the
swatches and fails if they moved. Change all three together and re-run
`python docs/make_swatches.py`.

## Notes on the two viewers

Several behaviours in VMD and PyMOL produce wrong output rather than errors —
`pbc join` without `-bondlist`, a boxless file reporting a 1 × 1 × 1 Å cell,
`cmd.get_coordset` rows not being ordered by atom index. They are documented in
[docs/limits.rst](docs/limits.rst) and commented at the point of use. Please
keep those comments with the code they explain.
