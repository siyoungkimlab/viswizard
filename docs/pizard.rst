pizard (PyMOL)
==============

.. code-block:: bash

   pizard sys.pdb traj.dcd --ligand "resn LIG"
   pizard sys.dms --ligand "resn LIG" --pocket 8
   pizard a.pdb a.dcd b.pdb b.dcd 3ptb --ref 1ubq
   pizard --help

PyMOL selection syntax: ``resn``, ``resi 145-165``, ``polymer``. Ranges with a
hyphen are fine here, unlike VMD.

.. note::

   PyMOL cannot load a trajectory without an object to attach it to, so the
   files go to the script rather than to pymol. Written out in full that is
   ``pymol pizard.py -- files flags``; the ``pizard`` wrapper hides it.

Formats
-------

``~/.pymolrc.py`` registers the handlers, so these work with no setup:

.. code-block:: text

   PyMOL> load solute.dms
   PyMOL> save out.dms, polymer or resn LIG
   PyMOL> save_mae out.mae, polymer or resn LIG

The ``.mae`` reader matters only on open-source PyMOL; the incentive build
reads ``.mae`` natively. DMS is the real gain either way — PyMOL has no DMS
support at all.

What PyMOL already does better
------------------------------

There is deliberately no ``fetch`` or superposition helper on this side.

.. code-block:: text

   PyMOL> fetch 1ubq
   PyMOL> cealign 1ubq, 1d3z

``cealign`` is structure-based rather than sequence-based and handles cases
the VMD-side matchmaker would struggle with. The one real gap is that there is
no movie helper for PyMOL.

Implementation notes
--------------------

Two PyMOL behaviours the code has to work around, both of which caused silent
wrong answers before they were understood:

``cmd.get_coordset`` rows are **not** ordered by internal atom index.
Indexing them with indices from a selection pairs up the wrong atoms — with no
error. ``cmd.get_coords`` and ``cmd.load_coords`` are index-ordered and are
what the gluing uses.

``cmd.identify`` returns the **file serial** (``ID``), not the internal index,
and PyMOL reorders atoms on load unless ``retain_order`` is set. Atom 132 by
ID was really index 29084 in one test. Selections are resolved with
``cmd.iterate`` and its ``index`` instead.

PyMOL also silently renames an object whose name is a reserved selection
keyword — ``b`` becomes ``b_``, and likewise ``x``, ``y``, ``z``, ``q``,
``ss``. The loader asks PyMOL what object it actually created rather than
assuming.
