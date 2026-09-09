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

So a ``.mae`` file can be written from VMD, and DMS — which neither program
knows about — can be read and written from both.

viswizard fills every gap in that table. VMD's Tcl has no ``sqlite3``, so DMS
cannot be handled in Tcl at all; the VMD side shells out to
``pizard/formats.py``, which also runs standalone:

.. code-block:: bash

   python3 ~/viswizard/pizard/formats.py in.dms out.mae

``vizard file.dms`` converts on the way in automatically, caching the result
in ``~/.viswizard_cache``.

In a VMD session
----------------

.. code-block:: tcl

   vizard_load_dms system.dms
   vizard_write_mae "protein or resname LIG" out.mae
   vizard_write_dms "protein or resname LIG" out.dms
