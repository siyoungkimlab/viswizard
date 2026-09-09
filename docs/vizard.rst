vizard (VMD)
============

.. code-block:: bash

   vizard sys.pdb traj.dcd --ligand "resname LIG"
   vizard sys.dms traj.dcd --ligand "resname LIG"          # DMS converted for you
   vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ref 1ubq
   vizard sys.pdb traj.dcd --ligand "resname LIG" --out movie.mp4
   vizard --help

VMD selection syntax: ``resname``, ``resid 145 to 149``, ``protein``.
``resid 145-149`` is a syntax error — use ``to``.

.. note::

   Files are passed to the script rather than to VMD, because VMD puts every
   file given on its command line into a *single* molecule, which is wrong for
   several systems. Passing VMD's own flags still works:
   ``vizard -dispdev text ...``.

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

``view`` does exactly what you would do by hand: switch off the other
representations, press ``=``, switch them back on. ``display resetview`` fits
whatever is *displayed*, which is why hiding the cartoon first frames on the
ligand and pocket instead of the whole protein.

It preserves your orientation. ``display resetview`` on its own also resets
the rotation, so zooming to a ligand would throw away however you had turned
the molecule.

Movies
------

.. code-block:: tcl

   vizard_movie -out movie.mp4                  ; # exactly the view you see
   vizard_movie -out m.mp4 -size {1920 1080} -fps 30
   vizard_movie -out preview.mp4 -step 10       ; # every 10th frame
   vizard_movie -h

Frames are rendered with Tachyon's in-memory renderer — no scene files — and
muxed with ffmpeg. It works headless: ``-dispdev text`` renders fine. Budget
roughly 1.2 s/frame at 640×360 and 1.7 s/frame at 960×540.

The batch form takes ``--out`` on the command line and renders without opening
a session.

Superposition
-------------

.. code-block:: tcl

   mm 1 0                                  ; # move molid 1 onto molid 0
   mm 1 0 -cutoff 1.0 -sel "protein and name CA and resid 1 to 40"

``vizard_matchmaker`` aligns the two *sequences* first, so residue numbering,
gaps and different chain lengths are all fine — the thing VMD's ``measure
fit`` cannot do, since it needs equal atom counts in matching order. It then
fits the matched Cα pairs and re-fits while dropping outliers past
``-cutoff``.

It does not refuse nonsense. Unrelated proteins still produce a transform, so
it warns when the match is poor:

.. code-block:: text

   vizard_matchmaker: 201 vs 76 CA -> 36 aligned, 36 kept, rmsd 16.0829 A
   vizard_matchmaker: WARNING -- only 47% of the shorter chain matched and
                      rmsd is 16.1 A; are these the same protein?

Speed
-----

``pbc join`` is the whole cost of gluing, and it is per-fragment: making ~9700
waters whole dominates everything else. ``-join`` therefore defaults to the
glue selection rather than the whole system.

=================================  ==========
Step (32k atoms, 10 frames)        Time
=================================  ==========
``pbc join``, all fragments        22 247 ms
``pbc join``, glue selection only     383 ms
``pbc wrap`` (water and ions)          55 ms
``measure fit`` and move                1 ms
=================================  ==========

22.3 s to 0.4 s, identical output. Pass ``-join all`` if you render solvent.
Removing water from the files buys only about 8 % more — do that for file size
and memory with ``glue_strip`` (9× smaller here), not for glue speed.
