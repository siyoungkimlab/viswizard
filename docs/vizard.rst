vizard (VMD)
============

.. code-block:: bash

   vizard sys.pdb traj.dcd --ligand "resname LIG"
   vizard sys.dms traj.dcd --ligand "resname LIG"          # DMS converted for you
   vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ref 1ubq
   vizard sys.pdb traj.dcd --ligand "resname LIG" --out movie.mp4
   vizard --help

``--ligand`` defaults to ``chain LIG L or resname LIG`` — a ligand named
``LIG``, or one sitting in chain ``LIG`` or ``L`` — so it often needs no flag.
When nothing is called that, as in a fetched entry whose ligand is ``ACO`` or
``BEN``, it falls back to the ``vizard_ligand`` macro: whatever is left once
protein, nucleic acids, solvent, ions, lipid and sugar are taken away, minus
peptide caps (``ACE``, ``NME``, ``NMA``, ``NH2`` — VMD does not count those as
protein) and the usual crystallisation additives (``GOL``, ``SO4``, ``EDO``,
…). Ions are dropped by resname and by atom name, so a stray ``Na`` or ``Cl``
does not come through as a ligand. Redefine it if it catches the wrong thing:

.. code-block:: tcl

   atomselect macro vizard_ligand "resname ACO"

If that finds nothing either — an apo simulation — the protein alone is glued
and shown.

Selections are VMD syntax. Some that work:

.. code-block:: bash

   --ligand "resname LIG"
   --ligand "resname UNK and not hydrogen"
   --ligand "chain B and not protein"
   --align  "protein and name CA"
   --align  "protein and name CA and resid 145 to 149"
   --align  "protein and backbone and chain A"
   --glue   "protein or resname LIG"
   --glue   "protein or resname LIG or resname ZN"

VMD's own flags still work: ``vizard -dispdev text ...``.

In a session
------------

The commands are loaded by ``~/.vmdrc``, so they exist in every VMD session,
not only ones started through ``vizard``.

============================================  ==========================================
Command                                       What it does
============================================  ==========================================
``ao off``                                    drop shadows + AO, for speed
``cgelem``                                    give beads their element
``cgbonds``                                   bond backbone beads in a chain
``browse``                                    step through the molecules
``view 1 0``                                  frame on rep 1 of molid 0
``viewsel "resid 45"``                        frame on any selection
``pick on``                                   shift + left-click an atom to focus it
``movie -out movie.mp4``                      render the current view to a video
``fetch 1ubq``                                download from RCSB and apply the reps
``mm 1 0``                                    superpose molid 1 onto 0 by sequence
``reps 0``                                    re-apply the standard reps
``glue_strip -sel SEL -o solute``             write a small, already-glued trajectory
``vizard_load_dms sys.dms``                   VMD has no DMS plugin
``vizard_write_mae SEL out.mae``              VMD's own .mae plugin is read-only
============================================  ==========================================

``view``, ``mm``, ``movie``, ``fetch``, ``reps`` and ``pick`` are aliases; the
``vizard_*`` names always work. It is not called ``focus`` because in a GUI
session Tk is loaded and ``focus`` is Tk's own keyboard-focus command.

Browsing
--------

Several molecules are loaded overlaid, each in its own color. To look at them
one at a time instead:

.. code-block:: tcl

   browse                  ; # Up/Down over the graphics window switch molecule
   browse off              ; # show them all again

Down is the next molecule and Up the previous, both wrapping around;
``bnext`` and ``bprev`` do the same typed, wherever the mouse is. Each
molecule is shown alone and framed on its ligand and pocket, while the
orientation stays put, so they can be compared from the same angle. A
``--ref`` structure stays on as context rather than being stepped through.

The arrows are what VMD leaves free — most letters are taken, ``j``/``k`` and
``h``/``l`` rotate, ``r``/``t``/``s`` are mouse modes, ``+``/``-`` step frames
— and ``browse off`` puts back whatever they were bound to. The keys act while
the mouse is over the graphics window, as all of VMD's hotkeys do.

Framing
-------

``view`` frames on the representations you name and leaves the rest alone,
keeping your current orientation.

Movies
------

.. code-block:: tcl

   vizard_movie -out movie.mp4                  ; # exactly the view you see
   vizard_movie -out m.mp4 -size {1920 1080} -fps 30
   vizard_movie -out preview.mp4 -step 10       ; # every 10th frame
   vizard_movie -out flat.mp4 -ao 0             ; # no shadows, quicker
   vizard_movie -h

Tachyon renders with whatever the display is set to, so the movie turns
shadows and ambient occlusion on for the render itself — even if ``ao off`` is
in force — and puts the display back afterwards. ``-ao 0`` skips them, which
is flatter and about three times quicker per frame.

Rendering is done by Tachyon in memory and muxed with ffmpeg, and works
headless. Budget roughly 1.2 s/frame at 640×360 and 1.7 s/frame at 960×540.

The batch form takes ``--out`` on the command line and renders without opening
a session.

Superposition
-------------

.. code-block:: tcl

   mm 1 0                                  ; # move molid 1 onto molid 0
   mm 1 0 -cutoff 1.0 -sel "protein and name CA and resid 1 to 40"

``vizard_matchmaker`` aligns the two sequences first, so residue numbering,
gaps and different chain lengths are all fine. It then fits the matched Cα
pairs and re-fits while dropping outliers past ``-cutoff``, reporting how many
residues matched and the final RMSD — judge the result by those two numbers,
since unrelated proteins still produce a transform.

Coarse-grained models
---------------------

The fit selection covers them: ``CA`` for an all-atom model, ``BB`` for
Martini, ``GC`` for SIRAH — one bead per residue in each case, which is what
the fit and the sequence superposition want. A coarse-grained model has no
``CA`` at all, and VMD's ``protein`` does not match its beads either, hence the
``or name`` half of the default.

Such a file names beads, not atoms, and says nothing about elements, so each
bead is given the element it stands for: ``BB`` and Martini's side-chain beads
carbon, SIRAH's ``GN``/``GC``/``GO`` nitrogen, carbon and oxygen — SIRAH names
a bead for the atom it is centred on, so the second letter is the element —
water beads oxygen, and an ion bead its own ion. VMD would otherwise leave every bead as element X, atomic number 0, with a radius taken off the first letter — 1.9 Å for ``SC1``, which is sulfur's. ``cgelem`` does it by hand in a session.

VMD's cartoon styles are no use here: NewCartoon wants a full N/CA/C/O backbone, and Tube, Trace and Ribbons follow atoms named ``CA``, so all of them draw nothing. Instead each backbone bead is bonded to the next one in its chain and drawn as Licorice, which comes out as the same continuous trace; ``cgbonds`` does the bonding by hand.

The fit, the trace, the bead bonding, ``vizard_matchmaker`` and the ligand
``vizard_reps`` falls back on are all restricted to the protein's own beads,
named by residue — ``ALA``, ``LEU`` and the rest for Martini, ``sA``, ``sL``,
``sHe`` for SIRAH, which names its residues its own way. VMD matches a
``resname`` with its case, which is what keeps them apart from the dipeptide
probes of a pocket search: upper-cased, ``sS``, ``sT``, ``sW`` and ``sY`` are
the probes ``SS``, ``ST``, ``SW`` and ``SY``. A pocket search fills the box with dipeptide probes carrying
one ``BB`` bead each, and 420 of those drawn as licorice bury the trace the rep
is for — while bonding ``name BB GC`` wholesale walks the list in file order
and joins beads of different probes that happen to be close, bonds that then
stretch across the box the moment anything is wrapped.

A coarse-grained file's beads sit ~3.5 Å apart, well beyond any distance-based
bond search, so a format that carries no bonds — a PDB or a GRO — arrives with
none, and every bead is its own molecule. That matters more than it sounds:
"make molecules whole" has nothing to walk, and the wrap moves beads instead of
molecules, which tears a two-bead probe in half across the box. A DMS or an MAE
does carry its bonds, and vizard carries them over the ``--strip``
rewrite by hand, in the kept atoms' own numbering: VMD cannot write bonds to a
PDB and guesses them from distance when it reads one back, which is right for
an all-atom model and leaves a coarse-grained one in pieces. Changing an
atom's bonds does not renumber VMD's fragments either, and fragments are what
the wrap moves molecules by, so ``mol reanalyze`` follows every change. A bead
already carrying VMD's maximum of twelve bonds — a Martini elastic network
reaches that — keeps the twelve it has.


Martini water is ``resname W``, which neither VMD's ``water`` nor PyMOL's
``solvent`` matches, and ion beads come under ``ION``, ``NA``, ``SOD`` and the
like. ``--strip`` names them itself for a coarse-grained model, so a 7266-bead
pocket-search box drops 5834 water and ion beads rather than 8 — the list lives
beside the element tables in ``pizard/cg.py`` and ``vizard/cg.tcl``. Everything
else in the model is kept: the probes and the lipids are not solvent, and
``inorganic`` would have taken them too.

Periodic boundaries
-------------------

A trajectory arrives with every molecule placed wherever the periodic box put
it, so the protein sits in a corner one frame and the ligand across the box
the next. Four steps, in this order:

1. every molecule is made whole, by walking its bonds rather than by distance;
2. the protein and anything named by ``--glue`` are placed on their jointly
   best images, so a dimer straddling the boundary comes back together;
3. every other molecule moves as a whole onto the image nearest the protein;
4. the protein is put in the middle of the box, which leaves everything else
   inside the cell, and the fit then carries every frame onto that same frame
   of reference.

The protein here is the whole molecule the fit selection sits on, not the fit
atoms, so ``--align`` can name one loop without pulling the centre into a
corner of the protein — and not the centre of everything glued, which a few
hundred co-solvent molecules would outvote.

That last point is why a ligand of more than 8 molecules is treated as
co-solvent: the dipeptide probes of a pocket search are not a ligand, and
placing 420 of them *with* the protein let them decide where the cluster went.
On a 3lnz Martini box their centre sat 39 Å off the protein, swinging up to
58 Å; wrapped around it instead, it stays within 5.5 Å, which is what 420
molecules of noise looks like. Their own frame-to-frame image flips halved.

Naming ``--glue`` yourself switches that off and glues exactly what you say;
``set vizard_cosolvent 40`` moves the line instead.

A molecule that happens to sit half a box away still flips between frames —
every wrap has that boundary somewhere, and with free solvent diffusing ~18 Å
between saved frames a fifth of it is near one. What is gone is the whole
cloud moving at once.

Reading DMS and CMS
-------------------

VMD has no DMS plugin, so ``vizard`` converts one to MAE on the way in and
caches the result under ``~/.viswizard_cache``. The cache is keyed on the
file's whole path, not its name: a pocket search holds a
``martini3/…/solvated.dms`` and a ``sirah/…/solvated.dms``, and one entry for
both served whichever had been converted last — silently, since the staleness
check only compares times and the older file looks up to date against an entry
written for its namesake.

Crystal structures
------------------

A structure from RCSB carries a crystallographic cell, not a periodic box, so
it is only aligned — nothing is made whole and nothing is wrapped. VMD keeps
the cell but not the spacegroup, so it is read from the ``CRYST1`` line of the
file: an MD box is ``P 1``, a deposited structure has a real spacegroup. A
cell with any angle other than 90° is skipped the same way.

Speed
-----

Shadows and ambient occlusion are recomputed on every redraw, so on a big
enough system they cost something. vizard turns them on for the look;
``ao off`` drops them when the pace matters more than the picture, and
``ao on`` puts them back. Movies render with them either way.

Waters and ions are never drawn and are most of the atoms, so they are dropped
as soon as the trajectory is loaded — ``--strip`` decides what goes, and
``--strip none`` keeps everything. VMD cannot delete atoms from a molecule, so
what is kept is written out and loaded back, which takes about 0.1 s for a
1000-frame box. On a 47k-atom system that turns a 9.5 s start-up into 2.9 s
and drops the trajectory in memory from 564 MB to 57 MB; the protein ends up
in exactly the same place, to 0.0 Å. A crystal structure is left alone, since
rewriting it would lose the spacegroup that keeps its cell from being treated
as a periodic box.

A long trajectory is glued by several VMD processes at once: each takes a
consecutive range of frames, and the ranges are loaded back in order.
``-workers`` sets how many (default one per CPU, up to 8, and at least 25
frames each); ``-workers 1`` keeps everything in one VMD. On a 47k-atom box,
1000 frames take about 4 s, or 14 s in one process. The frames pass through a
temporary directory, so expect about twice the trajectory's size on disk while
it runs. If a worker fails, gluing carries on in the one VMD.

``-join`` defaults to the glue selection rather than the whole system, since
solvent is never drawn; pass ``-join all`` if you render it. ``glue_strip``
writes a solute-only trajectory, roughly 9× smaller.
