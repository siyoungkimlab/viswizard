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
molecules whole, keeps the ligand with its protein, puts the protein in the
middle of the box and wraps everything else around it, then fits the
trajectory — in that order, since re-wrapping after a fit would undo it.

Each molecule is moved as a whole onto the image nearest the protein, so
nothing is broken and nothing is left on the far side of the box. The protein
in question is the whole molecule the fit selection sits on, so ``--align`` can
name a single loop without dragging that centre into a corner.

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
     - ``chain LIG L or resname LIG``, else ``vizard_ligand``
     - ``organic and not resn ACE+NMA+NME``
     - whenever the default catches the wrong thing — in ``vizard``, a ligand
       that is neither called ``LIG`` nor in chain ``LIG``/``L``. With no
       ligand at all, the protein alone is glued — its chains held together —
       and shown
   * - ``--glue``
     - ``protein or (<ligand>)``
     - ``polymer or (<ligand>)``
     - to hold more than the ligand together — a cofactor, a metal, a
       second chain. More than 8 ligand molecules is taken as co-solvent
       rather than a ligand: it is wrapped around the protein instead of held
       with it, which is both what it is for and what stays still
   * - ``--align``, ``--fit``
     - ``(protein and name CA) or name BB GC``
     - ``(name CA and elem C) or (polymer and name BB+GC)``
     - to fit on a domain or a loop instead of the whole protein. The default
       covers all-atom (``CA``), Martini (``BB``) and SIRAH (``GC``) models.
       ``pizard`` renames a backbone bead ``CA`` as it reads it, so ``elem C``
       is what keeps a calcium ion out of the fit
   * - ``--pocket``
     - ``6``
     - ``6``
     - to show more or less of the binding site, in ångström
   * - ``--strip``
     - ``water or ions``
     - ``solvent or inorganic``
     - to keep solvent (``none``) or to drop more than the default, a
       membrane say; dropped right after loading, which is most of the speed.
       For a coarse-grained model the default names the bead residues instead
       (``W``, ``WT4``, ``ION``, …), since ``water`` and ``solvent`` match none
       of them
   * - ``--stride``
     - ``1``
     - ``1``
     - to load every Nth frame instead of all of them. Loading, not playback:
       the frames that are skipped are never read, so a 1000-frame box at
       ``--stride 10`` starts in a quarter of the time and holds a tenth of the
       coordinates. ``--step`` is the one for ``--out``
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
     - –
     - to render a video instead of opening a session
   * - ``--size``
     - ``1280 720``
     - current viewport
     - with ``--out``, to set the frame size
   * - ``--fps``
     - ``24``
     - ``24``
     - with ``--out``, to set the playback rate
   * - ``--step``
     - ``1``
     - ``1``
     - with ``--out``, to render every Nth frame for a quick preview
   * - ``--zoom``
     - ``1``
     - not available
     - with ``--out``, to tighten the framing (VMD only)
   * - ``--keep``
     - ``0``
     - ``0``
     - with ``--out``, to keep the intermediate frames
   * - ``--ray``
     - not available
     - ``1``
     - with ``--out``, ``0`` skips ray tracing for speed
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
