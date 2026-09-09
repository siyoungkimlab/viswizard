viswizard
=========

A VMD and PyMOL toolkit for protein–ligand molecular dynamics. It keeps a
ligand with its protein across periodic boundaries, aligns the trajectory,
and sets up a view worth looking at — from one command line.

.. code-block:: bash

   vizard sys.pdb traj.dcd --ligand "resname LIG"     # VMD
   pizard sys.pdb traj.dcd --ligand "resn LIG"        # PyMOL

Two commands, one package:

.. list-table::
   :header-rows: 1
   :widths: 20 20 40

   * - Command
     - Directory
     - Drives
   * - ``vizard``
     - ``vizard/``
     - VMD
   * - ``pizard``
     - ``pizard/``
     - PyMOL

They are separate on purpose. The two programs speak different selection
languages — ``resname LIG`` against ``resn LIG``, ``resid 145 to 149``
against ``resi 145-149`` — and the command name is the reminder of which
dialect to type.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   getting_started
   vizard
   pizard
   colors
   formats
