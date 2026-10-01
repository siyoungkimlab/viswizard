pizard (PyMOL)
==============

.. code-block:: bash

   pizard sys.pdb traj.dcd
   pizard sys.pdb traj.dcd --ligand "resn LIG"
   pizard sys.dms --ligand "resn LIG" --pocket 8
   pizard a.pdb a.dcd b.pdb b.dcd 3ptb --ref 1ubq
   pizard --help

``--ligand`` defaults to ``organic and not resn ACE+NMA+NME`` — every organic
molecule that is not a peptide cap — so a ligand usually needs no flag at all.
Name it when the default catches too much (lipids and organic cosolvents are
organic too) or too little. With nothing matching, the polymer alone is glued
and shown. Of the hydrogens, only the polar ones are drawn — those on N, O or S.

With several systems, each object is named after its file. When the files are
all called the same thing — ``apo/solvated.pdb``, ``holo/solvated.pdb`` — the
directory above them is used instead, so the objects become ``apo`` and
``holo``. ``--object`` names a single object.

Selections are PyMOL syntax. Some that work:

.. code-block:: bash

   --ligand "resn LIG"
   --ligand "resn UNK and not hydro"
   --ligand "chain B and not polymer"
   --align  "polymer and name CA"
   --align  "polymer and name CA and resi 145-165"
   --align  "polymer and backbone and chain A"
   --glue   "polymer or resn LIG"
   --glue   "polymer or resn LIG or resn ZN"


Selections
----------

Two named selections are made on start-up: ``ligand``, what ``--ligand``
matched, and ``pocket``, the residues around it. They are there to type
against and to click in the object panel:

.. code-block:: text

   PyMOL> show spheres, ligand
   PyMOL> iterate pocket and name CA, print(resi, resn)

PyMOL has no user-defined selection keywords — no equivalent of VMD's
``vizard_ligand`` macro — so these are fixed sets of atoms rather than
expressions that get re-evaluated. That is what the pocket already was, and a
topology does not change. If an object of your own is called ``ligand``, the
selection becomes ``pizard_ligand`` instead.

Browsing
--------

Several structures are loaded overlaid, each in its own color. To look at them
one at a time instead:

.. code-block:: text

   PyMOL> browse                  # s/w, j/k or down/up switch structure
   PyMOL> browse chain L          # zoom on this selection instead
   PyMOL> browse off              # show everything again

Each structure is shown alone and zoomed on its ligand — by default the same
``--ligand`` selection the session was set up with — while the orientation
stays put, so they can be compared from the same angle. One whose selection
matches nothing is framed whole, and a ``--ref`` structure stays visible as
context rather than being stepped through.

``s`` or ``j`` is the next structure, ``w`` or ``k`` the previous, and so are
the down and up arrows; all of them wrap around. Browsing takes the keyboard
for the 3D window while it is on, so the keys work straight away; click the
command line whenever you want to type there, and it behaves as usual, history
and all. ``browse_next``/``browse_prev`` (``bnext``, ``bprev``) are the same
step typed as a command, wherever the focus is.

Nothing PyMOL already binds is taken. ``set_key`` is no use for this: it takes
only F1–F12, left, right, pgup, pgdn, home, insert and the CTRL/ALT
combinations — it refuses plain letters, and although it accepts ``up`` and
``down`` it never fires them. The page keys are spoken for (scenes) and are
missing from a Mac laptop keyboard anyway. So the keys come from a Qt event
filter, which stands aside for text boxes and is removed by ``browse off``.

PyMOL normally aims the 3D widget's keyboard focus at the command line — that
is why typing in the viewport lands at the prompt, and why clicking the 3D
window alone does not hand the keys over. Wizards drop that focus proxy to get
the keyboard; browsing does the same, and ``browse off`` restores it.
Add a function key too if you want one:

.. code-block:: text

   PyMOL> browse keys="F3 F4"     # next, previous, through set_key

``browse off`` puts back whatever those were bound to. Left and right are left
alone throughout, so they keep stepping trajectory frames.

Speed
-----

Waters and ions are never drawn and are most of the atoms, so they are dropped
as soon as the trajectory is loaded — ``--strip`` decides what goes, and
``--strip none`` keeps everything. On a 47k-atom box with 1000 states that
takes 0.04 s and makes everything after it smaller: the glue goes from 3.5 s
to 0.45 s, the session from 5.7 s to 2.5 s, and the trajectory in memory from
564 MB to 57 MB. The protein and ligand end up in exactly the same place
either way.

.. code-block:: bash

   pizard sys.pdb traj.dcd --strip "solvent or inorganic"   # the default
   pizard sys.pdb traj.dcd --strip "solvent or resn POPC"   # membrane too
   pizard sys.pdb traj.dcd --strip none                     # keep it all

Coarse-grained models
---------------------

Such a file names beads, not atoms, and says nothing about elements, so each
bead is given the element it stands for: ``BB`` and Martini's side-chain beads
carbon, SIRAH's ``GN``/``GC``/``GO`` nitrogen, carbon and oxygen — SIRAH names
a bead for the atom it is centred on, so the second letter is the element —
water beads oxygen, and an ion bead its own ion. PyMOL would otherwise guess from the name and read Martini water ``W`` as tungsten, the sodium bead ``SOD`` as sulfur, and the glycerol beads ``GL1``/``GL2`` as an element ``G`` that does not exist.

The backbone bead — Martini's ``BB``, SIRAH's ``GC`` — is renamed ``CA`` on the
way in, and the beads of an amino acid are marked as polymer. That is what
makes PyMOL treat the model as a protein: ``polymer`` selects it, the residues
get guide atoms, and ``align``, ``super``, ``cealign`` and the GUI's
**action → align → to molecule** all work on it, against another
coarse-grained model or against a structure you fetched. The bead's own name
is kept in ``text_type``, so ``iterate`` still tells you what it was.

This has to happen while the file is being read. PyMOL settles what each
residue is as it reads it and does not revisit the question, so a bead that
arrived with a bogus element is not part of a protein and cannot be made into
one afterwards: correcting the elements and re-sorting brings back the guide
atoms and ``cealign``, but ``align`` and ``super`` stay broken. The DMS and
MAE readers therefore do it in place, as the model is built. A coarse-grained
PDB or GRO is read by PyMOL itself, before pizard sees it, so such a model
gets its elements, its cartoon and ``cealign``, but not ``align`` and
``super``.

The fit selection follows from the rename: ``(name CA and elem C) or (polymer
and name BB+GC)`` — one bead per residue, which is what the fit and the
sequence superposition want. The ``elem C`` half is what keeps a calcium ion,
also called ``CA``, out of the fit; it is exactly what ``polymer and name CA``
used to do, and it works on a model PyMOL never called a polymer. ``name
BB+GC`` covers a model loaded outside pizard, under the names its file uses,
and ``polymer`` guards it: a box can hold beads called ``BB`` that are not the
protein at all. In a pocket search, each dipeptide probe carries one, and
their residue names (``WW``, ``FY``, ``EE``, …) are not names any reader
knows, so they are beads and nothing more. Fitting on 420 probes diffusing
through the box left the protein wandering 36 Å; fitting on the protein's own
85 backbone beads holds it still.

If a model has no residue the reader recognised — a box of nothing but probes,
say — the guard would leave the fit empty, so the beads are taken under their
own names after all, and pizard says so.

The backbone gets a cartoon, through ``cartoon_trace_atoms``, which is PyMOL's setting for exactly this: it traces the beads themselves rather than looking for a backbone, drawn as a tube. A plain cartoon on the same beads draws nothing at all.

A coarse-grained file's beads sit ~3.5 Å apart, well beyond any distance-based
bond search, so a format that carries no bonds — a PDB or a GRO — arrives with
none, and every bead is its own molecule. That matters more than it sounds:
"make molecules whole" has nothing to walk, and the wrap moves beads instead of
molecules, which tears a two-bead probe in half across the box. A DMS or an MAE
does carry its bonds, and pizard keeps them.


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

A molecule that happens to sit half a box away still flips between frames —
every wrap has that boundary somewhere, and with free solvent diffusing ~18 Å
between saved frames a fifth of it is near one. What is gone is the whole
cloud moving at once.

Crystal structures
------------------

A structure from RCSB carries a crystallographic cell, not a periodic box, so
there is nothing to make whole and nothing to wrap — it is only aligned. The
tell is the spacegroup: an MD box is written as ``P 1``, while a deposited
structure has a real one (``P 21 21 21``, ``C 1 2 1``, …), whose angles need
not be 90° either. Gluing against such a cell used to move the odd crystal
water a whole cell vector, or fail outright on a non-90° angle.

Movies
------

.. code-block:: text

   PyMOL> pizard_movie out=movie.mp4
   PyMOL> pizard_movie out=m.mp4, size=1920x1080, fps=30
   PyMOL> pizard_movie out=preview.mp4, step=10, ray=0
   PyMOL> pizard_movie out=-h

Or straight from the command line, without opening a session:

.. code-block:: bash

   pizard sys.pdb traj.dcd --ligand "resn LIG" --out movie.mp4 \
          --size 1920x1080 --fps 30

Frames go through ``cmd.png`` and are muxed with ffmpeg. It renders headless,
so no window has to stay in front. ``ray=0`` trades quality for speed on a long
trajectory. ``pmovie`` is a shorter alias.

The command is not called ``movie``: that name is PyMOL's own module, and
taking it would break ``movie.produce`` and ``movie.roll``.

Formats
-------

``.dms`` and ``.mae`` can be given on the command line, and ``load`` and
``save`` handle them inside a session — see :doc:`formats`.
