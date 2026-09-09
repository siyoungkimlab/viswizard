Getting started
===============

Install
-------

.. code-block:: bash

   git clone https://github.com/siyoungkimlab/viswizard.git ~/viswizard
   bash ~/viswizard/install.sh

That creates ``~/.local/bin/vizard`` and ``~/.local/bin/pizard``, and registers
the in-session commands and the DMS/MAE handlers with VMD and PyMOL.
Re-running it is safe.

What it does
------------

In a periodic simulation a ligand that is not bonded to its protein wraps
independently of it, so it jumps across the box between frames. viswizard
makes molecules whole, keeps the ligand with its protein, wraps everything
else, and fits the trajectory — in that order, since re-wrapping after a fit
would undo it.

First run
---------

.. code-block:: bash

   vizard equilibrated.pdb trajectory.dcd --ligand "resname LIG"

.. code-block:: text

   vizard: ligand 'resname LIG'                     38 atoms
   vizard: glue   'protein or (resname LIG)'      3241 atoms
   vizard: align  'protein and name CA'            201 atoms
   glue: processed 10 frames in 0.34 s (34 ms/frame)
   vizard: OK -- 621 protein/ligand contacts within 5 A in frame 0

Several systems at once
-----------------------

A structure — or a bare four-character PDB id — starts a new molecule, and any
trajectories after it attach to it. Each gets its own color and is superposed
onto the first.

.. code-block:: bash

   vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resname LIG" --ref 1ubq
   pizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resn LIG"    --ref 1ubq

``--ref`` places the first system on a reference structure, given as a file or
a PDB id. Residue numbering need not match.

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 14 30 40

   * - Flag
     - Default
     - Meaning
   * - ``--ligand``
     - ``resname LIG`` / ``resn LIG``
     - reps, coloring, pocket, view center
   * - ``--glue``
     - ``protein or (<ligand>)``
     - held together across the boundary
   * - ``--align``
     - ``... and name CA``
     - what the fit is computed on
   * - ``--pocket``
     - ``6``
     - pocket residue cutoff, ångström
   * - ``--ref``
     - –
     - reference file or PDB id
   * - ``--out``
     - –
     - render a video (VMD only)
