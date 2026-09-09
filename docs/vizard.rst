vizard (VMD)
============

.. code-block:: bash

   vizard sys.pdb traj.dcd --ligand "resname LIG"
   vizard sys.dms traj.dcd --ligand "resname LIG"          # DMS converted for you
   vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ref 1ubq
   vizard sys.pdb traj.dcd --ligand "resname LIG" --out movie.mp4
   vizard --help

Selections are VMD syntax. Some that work:

.. code-block:: bash

   --ligand "resname LIG"
   --ligand "resname UNK and not hydrogen"
   --ligand "chain B and not protein"
   --align  "protein and name CA"
   --align  "protein and name CA and resid 145 to 149"
   --align  "protein and backbone and chain A"
   --glue   "protein or resname LIG"
   --glue   "protein or resname LIG or resname ZN"

VMD's own flags still work: ``vizard -dispdev text ...``.

In a session
------------

The commands are loaded by ``~/.vmdrc``, so they exist in every VMD session,
not only ones started through ``vizard``.

============================================  ==========================================
Command                                       What it does
============================================  ==========================================
``view 1 0``                                  frame on rep 1 of molid 0
``viewsel "resid 45"``                        frame on any selection
``pick on``                                   shift + left-click an atom to focus it
``movie -out movie.mp4``                      render the current view to a video
``fetch 1ubq``                                download from RCSB and apply the reps
``mm 1 0``                                    superpose molid 1 onto 0 by sequence
``reps 0``                                    re-apply the standard reps
``glue_strip -sel SEL -o solute``             write a small, already-glued trajectory
``vizard_load_dms sys.dms``                   VMD has no DMS plugin
``vizard_write_mae SEL out.mae``              VMD's own .mae plugin is read-only
============================================  ==========================================

``view``, ``mm``, ``movie``, ``fetch``, ``reps`` and ``pick`` are aliases; the
``vizard_*`` names always work. It is not called ``focus`` because in a GUI
session Tk is loaded and ``focus`` is Tk's own keyboard-focus command.

Framing
-------

``view`` frames on the representations you name and leaves the rest alone,
keeping your current orientation.

Movies
------

.. code-block:: tcl

   vizard_movie -out movie.mp4                  ; # exactly the view you see
   vizard_movie -out m.mp4 -size {1920 1080} -fps 30
   vizard_movie -out preview.mp4 -step 10       ; # every 10th frame
   vizard_movie -h

Rendering is done by Tachyon in memory and muxed with ffmpeg, and works
headless. Budget roughly 1.2 s/frame at 640×360 and 1.7 s/frame at 960×540.

The batch form takes ``--out`` on the command line and renders without opening
a session.

Superposition
-------------

.. code-block:: tcl

   mm 1 0                                  ; # move molid 1 onto molid 0
   mm 1 0 -cutoff 1.0 -sel "protein and name CA and resid 1 to 40"

``vizard_matchmaker`` aligns the two sequences first, so residue numbering,
gaps and different chain lengths are all fine. It then fits the matched Cα
pairs and re-fits while dropping outliers past ``-cutoff``, reporting how many
residues matched and the final RMSD — judge the result by those two numbers,
since unrelated proteins still produce a transform.

Speed
-----

Making molecules whole is the whole cost of gluing, and it is per-fragment, so
``-join`` defaults to the glue selection rather than the whole system — about
40 ms/frame on a 32k-atom box. Pass ``-join all`` if you render solvent.
``glue_strip`` writes a solute-only trajectory, roughly 9× smaller.
