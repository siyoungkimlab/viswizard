Structure formats
=================

Gluing is built on the bond graph, so connectivity has to be right. A PDB
without ``CONECT`` records carries none, and bonds inferred by distance can
attach a ligand to its surroundings — which quietly makes gluing a no-op. MAE
and DMS both carry explicit bonds. Prefer them.

What each tool supports
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 12 22 26 30

   * - Format
     - VMD, native
     - PyMOL, native
     - with viswizard
   * - ``.pdb``
     - read, write
     - read, write
     - unchanged
   * - ``.mae``
     - read only
     - incentive build only
     - **write** for VMD; **read and write** for PyMOL
   * - ``.dms``
     - not supported
     - not supported
     - **read and write** for both

In a VMD session
----------------

.. code-block:: tcl

   vizard_load_dms system.dms
   vizard_write_mae "protein or resname LIG" out.mae
   vizard_write_dms "protein or resname LIG" out.dms

In a PyMOL session
------------------

``load`` and ``save`` handle every format, chosen by the file extension:

.. code-block:: text

   PyMOL> load system.dms
   PyMOL> load system.mae
   PyMOL> save out.pdb, polymer or resn LIG
   PyMOL> save out.dms, polymer or resn LIG
   PyMOL> save out.mae, polymer or resn LIG

An MAE can hold several blocks. When they all sit in the same box they are one
simulation system — Desmond writes the solute, the waters and the ions as
separate blocks — and they load as one object, in file order, which is what a
trajectory numbers its atoms against and what VMD does. Blocks without a
common box, such as a set of poses, load as separate objects.

Insertion codes
---------------

An antibody or a protease is numbered 60, 60A, 60B, 60C, 60D, 61 — five
residues under one number, told apart by a letter. The number alone makes one
residue of them, with five backbone beads in it, and PyMOL draws a cartoon
trace that knots itself through all five.

The insertion code is carried through every format here: the DMS
``particle.insertion`` column, the MAE ``s_m_insertion_code`` property, the
dump the VMD side writes, and PyMOL's own ``resi``, which keeps the letter on
the end of the number — ``resi 60A``, which is also how you select one.

VMD is the exception, and not by our choice: its MAE plugin reads no insertion
code, from a file of ours or from Maestro's own, so in a VMD session 60 and
60A are one residue however the file was written. Its coarse-grained trace is
drawn from the bonds rather than from the numbering, so the trace itself is
right; a selection such as ``resid 60`` is what picks up more than it looks
like it should.
