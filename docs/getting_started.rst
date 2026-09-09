Getting started
===============

``vizard`` is a VMD wizard and ``pizard`` is a PyMOL wizard! It helps
visualizing trajectories with various useful functions.

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

In a molecular dynamics simulation, a protein or ligand jumps across the box
between frames because of periodic boundary conditions. viswizard makes
molecules whole, keeps the ligand with its protein, wraps everything else, and
fits the trajectory — in that order, since re-wrapping after a fit would undo
it.

Examples
--------

A trajectory, in either viewer:

.. code-block:: bash

   vizard equilibrated.pdb trajectory.dcd --ligand "resname LIG"
   pizard equilibrated.pdb trajectory.dcd --ligand "resn LIG"

A single structure, when there is no trajectory to play:

.. code-block:: bash

   vizard complex.pdb --ligand "resname LIG"

Formats VMD cannot open by itself — the DMS is converted on the way in:

.. code-block:: bash

   vizard system.dms trajectory.dcd --ligand "resname LIG"
   vizard system.mae trajectory.dcd --ligand "resname LIG"

Two trajectories overlaid, each in its own color, the second superposed onto
the first:

.. code-block:: bash

   vizard a.pdb a.dcd b.pdb b.dcd --ligand "resname LIG"

Compare against a crystal structure by fetching it. A bare four-character PDB
id is loaded as another molecule; ``--ref`` instead places the trajectory onto
that structure:

.. code-block:: bash

   vizard sys.pdb traj.dcd 3ptb --ligand "resname LIG"
   vizard sys.pdb traj.dcd --ligand "resname LIG" --ref 3ptb

When the binding site matters more than the whole protein, fit on it and widen
the pocket:

.. code-block:: bash

   vizard sys.pdb traj.dcd --align "protein and name CA and resid 145 to 149" \
                           --pocket 8

Straight to a video, without opening a session:

.. code-block:: bash

   vizard sys.pdb traj.dcd --ligand "resname LIG" --out movie.mp4
   vizard sys.pdb traj.dcd --ligand "resname LIG" --out movie.mp4 \
          --size 1920 1080 --fps 30 --step 5

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 16 20 20 34

   * - Option
     - ``vizard`` (VMD)
     - ``pizard`` (PyMOL)
     - When to use it
   * - ``--ligand``, ``--lig``
     - ``resname LIG``
     - ``resn LIG``
     - whenever the ligand is not called ``LIG``
   * - ``--glue``
     - ``protein or (<ligand>)``
     - ``polymer or (<ligand>)``
     - to hold more than the ligand together — a cofactor, a metal, a
       second chain
   * - ``--align``, ``--fit``
     - ``protein and name CA``
     - ``polymer and name CA``
     - to fit on a domain or a loop instead of the whole protein
   * - ``--pocket``
     - ``6``
     - ``6``
     - to show more or less of the binding site, in ångström
   * - ``--ref``
     - –
     - –
     - to place the trajectory onto a reference; a file or a PDB id
   * - ``--object``
     - not available
     - ``sys``
     - to name the PyMOL object something other than ``sys``
   * - ``--out``
     - –
     - not available
     - to render a video instead of opening a session
   * - ``--size``
     - ``1280 720``
     - not available
     - with ``--out``, to set the frame size
   * - ``--fps``
     - ``24``
     - not available
     - with ``--out``, to set the playback rate
   * - ``--step``
     - ``1``
     - not available
     - with ``--out``, to render every Nth frame for a quick preview
   * - ``--zoom``
     - ``1``
     - not available
     - with ``--out``, to tighten the framing
   * - ``--keep``
     - ``0``
     - not available
     - with ``--out``, to keep the intermediate frames
   * - ``--reframe``
     - ``1``
     - not available
     - with ``--out``, ``0`` renders the view as it stands
   * - ``--help``, ``-h``
     - –
     - –
     - to print this list and exit

VMD's own flags pass through as well, so ``vizard -dispdev text ...`` runs
headless.
