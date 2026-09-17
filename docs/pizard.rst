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


Browsing
--------

Several structures are loaded overlaid, each in its own color. To look at them
one at a time instead:

.. code-block:: text

   PyMOL> browse                  # up/down arrows switch structure
   PyMOL> browse chain L          # zoom on this selection instead
   PyMOL> browse off              # show everything again

Down goes to the next structure and up to the previous one, wrapping around.
Each is shown alone and zoomed on its ligand — by default the same
``--ligand`` selection the session was set up with — while the orientation
stays put, so the structures can be compared from the same angle. One whose
selection matches nothing is framed whole, and a ``--ref`` structure stays
visible as context rather than being stepped through.

PyMOL leaves the up and down arrows unbound (left and right step frames), so
nothing is taken away; ``browse off`` puts back whatever was there.

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
