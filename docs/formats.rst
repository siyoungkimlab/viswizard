Structure formats
=================

MAE and DMS both carry explicit bonds, so nothing is guessed by distance.
Prefer them over a bare PDB.

Why bonds matter
----------------

A PDB without ``CONECT`` records has no connectivity, so VMD infers bonds by
distance. In one real case it bonded a chloride ion to a water oxygen:

.. code-block:: text

   MAE ions: 1  (bonds: {})           <- correctly unbonded
   PDB ions: 2  (bonds: 6320 {})      <- an invented bond to a water

Gluing is built on the bond graph. If a distance guess fuses your ligand to
the protein, the two are already one component and gluing silently becomes a
no-op.

What each tool supports
-----------------------

===========  ==========  ===========  ==================================
Format       VMD read    VMD write    PyMOL
===========  ==========  ===========  ==================================
``.pdb``     yes         yes          yes
``.mae``     yes         **no**       incentive only; reader provided
``.dms``     **no**      **no**       none; reader and writer provided
===========  ==========  ===========  ==================================

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

Parser notes
------------

Two things in the ``.mae`` format that a naive parser gets wrong, both covered
by the test suite:

**Property names may contain brackets.** ``[`` is structural only in a size
specifier like ``m_atom[204] {``. Treating every ``[`` as structural
desynchronises the column list and mangles every row that follows.

**Virtual sites live in ``ffio_ff/ffio_pseudo``, not ``m_atom``.** Miss them
and a 3840-atom system reads as 2304 atoms — and the count will not match its
trajectory. They carry no explicit parent, so each is bonded to the nearest
real atom via a spatial grid; residue numbers cannot be used, because the two
blocks number residues differently, from 1 and from 0.
