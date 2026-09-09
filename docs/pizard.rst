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
