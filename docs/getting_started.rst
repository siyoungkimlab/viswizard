Getting started
===============

Install
-------

.. code-block:: bash

   git clone https://github.com/siyoungkimlab/viswizard.git ~/viswizard
   bash ~/viswizard/install.sh

That creates ``~/.local/bin/vizard`` and ``~/.local/bin/pizard``, and writes a
marked block into ``~/.vmdrc`` and ``~/.pymolrc.py`` so the in-session commands
and the DMS/MAE handlers are available everywhere. Re-running it is safe: the
blocks are replaced between ``# >>> viswizard >>>`` markers rather than
appended.

.. note::

   A user ``~/.vmdrc`` is read *instead of* VMD's own, and VMD's own is where
   ``menu main on`` lives. ``install.sh`` therefore sources VMD's defaults
   first; without that you get a render window and no Main menu.

The problem it solves
---------------------

In a periodic simulation a ligand that is not bonded to its protein wraps
independently, so it jumps from one side of the box to the other between
frames. Nothing in VMD keeps two unbonded molecules together, and re-wrapping
after an alignment undoes the alignment. viswizard does the four steps in the
only order that works: make molecules whole, glue the ligand to the protein,
wrap everything else, then fit — fitting last, and to a reference that has
itself been made whole.

On a 32k-atom box, before and after:

==============  ===================  ==================
Frame           Protein–ligand       Cα RMSD
==============  ===================  ==================
raw             1.7 – 67.1 Å         up to 68.7 Å
processed       1.74 – 2.14 Å        0.83 – 1.23 Å
==============  ===================  ==================

The residual RMSD is real conformational drift; the rigid-body tumbling and
box-hopping are gone.

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

Every line is a checkpoint. If a step fails you get ``vizard: FAILED -- ...``
instead of a silently wrong picture, which matters because VMD's ``-e`` does
not stop on error.

Several systems at once
-----------------------

A structure — or a bare four-character PDB id — starts a new molecule, and any
trajectories after it attach to it. Each gets its own colour and is superposed
onto the first.

.. code-block:: bash

   vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resname LIG" --ref 1ubq
   pizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resn LIG"    --ref 1ubq

``--ref`` positions the first system: the trajectory is fitted internally
first, then placed onto the reference by structural or sequence alignment, so
residue numbering need not match.

Common options
--------------

.. list-table::
   :header-rows: 1
   :widths: 14 30 40

   * - Flag
     - Default
     - Meaning
   * - ``--ligand``
     - ``resname LIG`` / ``resn LIG``
     - reps, colouring, pocket, view centre
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
