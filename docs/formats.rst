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

``load`` and ``save`` handle both formats directly:

.. code-block:: text

   PyMOL> load system.dms
   PyMOL> load system.mae
   PyMOL> save out.dms, polymer or resn LIG
   PyMOL> save_mae out.mae, polymer or resn LIG

``save_mae`` always writes with viswizard's writer. Plain ``save out.mae``
works too, using PyMOL's own writer where the build has one.
