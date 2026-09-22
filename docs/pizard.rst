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


Runs N' Poses / PLINDER systems
-------------------------------

.. code-block:: bash

   pizard rnp 8g62__1__1.A__1.F_1.J_1.L        # the whole system
   pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F    # zoomed on that one ligand

A PLINDER system id already says which chains the complex is:

.. code-block:: text

   8g62 __ 1 __ 1.A __ 1.F_1.J_1.L
   ^       ^     ^      ^
   PDB     |     |      ligand chains, joined by "_"
   entry   |     receptor chains, joined by "_"
           biological assembly

so ``rnp`` opens it without being told anything else. The entry is downloaded
from RCSB unless an unpacked ``ground_truth/`` has it — ``$RNP_GROUND_TRUTH``,
then ``~/runs-n-poses/ground_truth``, then ``~/data/paper_data/ground_truth``,
then ``./ground_truth`` — in which case the benchmark's own pose is used, since
that is the one its numbers were computed against. A downloaded CIF goes to a
temporary directory and is deleted the moment it is loaded; nothing is left in
the working directory.

Everything outside the system's own chains is dropped, which matters because an
entry often holds several copies of the complex: 8G62 has three, and the other
two would be superposed on top of what you are looking at. Name a ligand chain
and that one gets the sticks and the zoom while the rest of the system's
ligands are drawn as grey lines — they are part of the crystal contents the
pose has to share its pocket with, so they are worth seeing, just not worth
centring on. ``1.F`` and ``F`` both name the same chain.

The chain letters are mmCIF ``label_asym_id``\ s, **not** author chains. In
8G62 all three ligands are author chain A — F is the inhibitor YOO, J and L are
acetates from the buffer — so ``chain F`` would select nothing at all. PyMOL
keeps ``label_asym_id`` in the segment identifier, which is why the selections
this builds are ``segi``:

.. code-block:: text

   PyMOL> iterate segi F and name C10, print(resn, chain, resi)
   YOO A 503

A PLINDER ground-truth ``system.cif`` needs no translation: its chains are
already called ``1.A`` and ``1.F``, and the selection becomes ``segi 1.F``.

Electron density
~~~~~~~~~~~~~~~~

The entry's map comes too, from PDBe — there is a ready-made one per X-ray
entry, so nothing has to be phased here:

.. code-block:: bash

   pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F                    # 2Fo-Fc, 1 sigma
   pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F --density fofc     # Fo-Fc, +/-3 sigma
   pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F --density both
   pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F --density off
   pizard rnp 8g62__1__1.A__1.F_1.J_1.L 1.F --sigma 1.5 --carve 2.5

``2fofc`` (the default) is the map the model was built into, drawn as a blue
mesh at ``--sigma`` sigma. ``fofc`` is the difference map: green at +3 sigma
where there is density the model does not explain, red at −3 sigma where an
atom sits in none. The mesh is carved to within ``--carve`` angstroms of the
ligand and nothing else, because the question a map answers here is whether
this pose is the one the crystal shows — a mesh over the whole pocket buries
that in the protein's own density.

The maps go to the same temporary directory as the CIF and are deleted once
PyMOL has them, and the map objects themselves are loaded but disabled: what
you look at is the mesh. They are on the crystal cell, with the symmetry in
their own header, which is how PyMOL places a mesh on a ligand whose
coordinates are outside the deposited box.

Density is skipped, with a line saying why, when the entry has none (an NMR or
cryo-EM entry, or no deposited structure factors), when ``--ref`` has moved the
structure out of the crystal frame, and when the system is an assembly copy
rather than the deposited chains.

Every other flag still applies, so ``--pocket 8``, ``--ref 1ubq`` and ``--out
movie.mp4`` work as they do anywhere else.

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
