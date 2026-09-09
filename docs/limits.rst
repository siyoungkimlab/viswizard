Known limits
============

- **Orthorhombic cells only.** Triclinic boxes — truncated octahedron, rhombic
  dodecahedron — need the fractional projection to go through the inverse cell
  matrix instead of dividing by the three box lengths. It is a contained
  change in one place per implementation, but it is not done.

- **Three ligand-carbon colours in VMD.** VMD has only three independent
  colour categories (``Element``, ``Name``, ``Type``), so a fourth molecule
  falls back to a solid ligand colour and loses element colours on its
  heteroatoms. PyMOL has no such limit.

- **No movie helper for PyMOL.** ``vizard_movie`` is VMD-only.

- **The superposition does not refuse nonsense.** Unrelated proteins still
  produce a transform; judge by the reported RMSD and match count, which are
  warned about when they look bad.

Traps worth knowing
-------------------

These are VMD behaviours that produce wrong output rather than errors. Each
one cost a debugging round and is commented in the source.

``pbc join`` silently does nothing without ``-bondlist``:

.. code-block:: text

   raw             max bond 50.32
   join fragment   max bond 50.26      <- did nothing
   join -bondlist  max bond  1.57      <- correct

**A file with no periodic cell reports a 1 × 1 × 1 Å box**, not zeros. Running
the PBC steps on that shifts every atom whose bond exceeds half a cell — which
is every atom — and destroys the structure with no error. That case is
detected and only the alignment is applied.

**``-e`` does not stop on error.** A failed step is followed by the next one,
so a script can report success having done nothing. Everything runs inside a
proc wrapped in ``catch``.

**``-args`` splits into words in GUI mode but not in ``-dispdev text``**, so a
quoted selection arrives as one value in one mode and several in the other.

**The alignment reference must be whole first.** Fitting to a structure split
across the periodic boundary produces a garbage rotation — 31 Å RMSD in the
case that first exposed it.
