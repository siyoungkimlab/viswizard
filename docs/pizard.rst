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
