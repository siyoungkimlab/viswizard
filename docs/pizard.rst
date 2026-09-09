pizard (PyMOL)
==============

.. code-block:: bash

   pizard sys.pdb traj.dcd --ligand "resn LIG"
   pizard sys.dms --ligand "resn LIG" --pocket 8
   pizard a.pdb a.dcd b.pdb b.dcd 3ptb --ref 1ubq
   pizard --help

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
