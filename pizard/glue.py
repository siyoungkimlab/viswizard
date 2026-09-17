"""
glue.py -- keep unbonded components together across PBC, then align.

Run it on a loaded trajectory and the ligand stops hopping across the box:

    run glue.py
    glue_traj glue="polymer or resn LIG", fit="polymer and name CA"

Orthorhombic cells.  For triclinic, replace the /L and *L below with the
inverse-cell and cell matrices.

Every step is whole-array numpy over a block of states, and blocks run on
several threads (numpy releases the GIL for this work).  PyMOL itself is only
called from the calling thread, and each block carries its own state numbers,
so a state's coordinates always go back into that same state.
"""
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np

try:
    import pymol
    from pymol import cmd
except ImportError:          # the numpy core is importable, and tested, without PyMOL
    pymol = cmd = None

__all__ = ["glue_traj"]


def _fail(msg):
    raise (pymol.CmdException if pymol is not None else RuntimeError)(msg)


def _indices(sel):
    """Internal atom indices (0-based) for a selection.

    NOT cmd.identify(): that returns the file serial (ID), and with
    retain_order=0 PyMOL reorders atoms on load, so ID-1 can point at a
    completely different atom.  iterate's `index` is the internal rank, which
    is what get_model() and get_coords() are ordered by.
    """
    out = []
    cmd.iterate(sel, "out.append(index - 1)", space={"out": out})
    return np.array(sorted(out), dtype=np.int64)


def _csr(nat, bonds):
    """0-based bond list -> CSR-ish neighbour arrays."""
    bonds = np.asarray(bonds, dtype=np.int64).reshape(-1, 2)
    deg = np.bincount(bonds.ravel(), minlength=nat)
    start = np.concatenate([[0], np.cumsum(deg)])
    nbr = np.empty(2 * len(bonds), dtype=np.int64)
    fill = start[:-1].copy()
    for i, j in bonds:
        nbr[fill[i]] = j; fill[i] += 1
        nbr[fill[j]] = i; fill[j] += 1
    return start, nbr


def _adjacency(obj):
    model = cmd.get_model(obj)
    nat = len(model.atom)
    start, nbr = _csr(nat, [b.index for b in model.bond])
    return nat, start, nbr


def _optimal_shifts(x):
    """Integer cell shifts, x fractional."""
    n = len(x)
    if n < 2:
        return np.zeros(n)
    s = -np.floor(x + 0.5)                 # bring each into [-1/2, 1/2)
    y = x + s
    tot, tot2 = y.sum(), (y * y).sum()
    xx = np.sort(y)
    v = np.empty(n)
    v[0] = n * tot2 - tot * tot
    v[1:] = v[0] + np.cumsum((n - 1) - 2 * (tot + np.arange(n - 1) - n * xx[:-1]))
    left = xx[v.argmin()]
    return s + (y < left)


def _kabsch(P, Q):
    """Rotation/translation putting P onto Q (both n x 3)."""
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return R, pc, qc


class _Topology:
    """Everything about the system that does not change from state to state.

    Bond fixing needs no walk over the atoms per state.  Take a BFS spanning
    tree of the bonds.  An atom's cell shift is the sum of the per-edge shifts
    on its path from the root, and each per-edge shift depends only on the RAW
    coordinates -- the parent's own shift is a whole number of cells:

        k_e = -round((x_child - x_parent) / L)

    Adding k_e to a whole subtree is a range update in DFS preorder, where a
    subtree is a contiguous run, so all of them together are one difference
    array and one cumsum.  Nearly every k_e is zero, and a block of states
    whose molecules are already whole skips the step.
    """

    def __init__(self, nat, start, nbr, gidx):
        st, nb = start.tolist(), nbr.tolist()
        label, parent = [-1] * nat, [-1] * nat
        ncomp = 0
        for seed in range(nat):
            if label[seed] >= 0:
                continue
            label[seed] = ncomp
            queue = [seed]
            for a in queue:                 # grows while it is walked: BFS
                for b in nb[st[a]:st[a + 1]]:
                    if label[b] < 0:
                        label[b] = ncomp
                        parent[b] = a
                        queue.append(b)
            ncomp += 1
        labels = np.array(label, dtype=np.int64)
        parent = np.array(parent, dtype=np.int64)

        child = np.flatnonzero(parent >= 0)
        par = parent[child]
        kids = child[np.argsort(par, kind="stable")].tolist()
        kstart = np.concatenate([[0], np.cumsum(np.bincount(par, minlength=nat))]).tolist()
        pre = np.empty(nat, dtype=np.int64)
        visit = []
        for root in np.flatnonzero(parent < 0).tolist():
            stack = [root]
            while stack:
                a = stack.pop()
                pre[a] = len(visit)
                visit.append(a)
                stack.extend(reversed(kids[kstart[a]:kstart[a + 1]]))
        size = [1] * nat
        for a in reversed(visit):           # children are visited after parents
            if parent[a] >= 0:
                size[parent[a]] += size[a]
        size = np.array(size, dtype=np.int64)

        self.nat, self.ncomp, self.labels = nat, ncomp, labels
        self.child, self.parent, self.pre = child, par, pre
        self.lo, self.hi = pre[child], pre[child] + size[child]
        self.gidx = gidx
        self.gcomps = np.unique(labels[gidx])
        self.gslot = np.searchsorted(self.gcomps, labels[gidx])
        self.gcount = np.bincount(self.gslot, minlength=len(self.gcomps)).astype(float)
        self.glued = np.isin(labels, self.gcomps)    # every atom of every glued comp
        self.count = np.bincount(labels, minlength=ncomp).astype(float)
        self.nothers = ncomp - len(self.gcomps)


def _sums(X, idx, n):
    """Per-group coordinate sums for every state at once: X is F x M x 3."""
    F, M = X.shape[:2]
    flat = (np.arange(F)[:, None] * n + idx[None, :]).ravel()
    X = X.reshape(-1, 3)
    return np.stack([np.bincount(flat, X[:, a], F * n) for a in range(3)],
                    axis=1).reshape(F, n, 3)


def _glue_block(P, L, t, wrap=1):
    """Steps 1-3, in place, on P (F x N x 3) with orthorhombic cells L (F x 3)."""
    F, nat = len(P), t.nat
    Lb = L[:, None, :]

    # 1. fix bonds: one difference array and one cumsum, see _Topology
    k = -np.round((P[:, t.child] - P[:, t.parent]) / Lb)
    f, e = np.nonzero(k.any(axis=2))
    if len(f):
        D = np.zeros((F, nat + 1, 3))
        np.add.at(D, (f, t.lo[e]), k[f, e])
        np.add.at(D, (f, t.hi[e]), -k[f, e])
        P += np.cumsum(D[:, :nat], axis=1)[:, t.pre] * Lb

    # 2. glue: shift whole components onto their jointly optimal images
    ng = len(t.gcomps)
    if ng > 1:
        cen = _sums(P[:, t.gidx], t.gslot, ng) / t.gcount[None, :, None]
        sh = np.zeros((F, t.ncomp, 3))
        for i in range(F):
            sh[i, t.gcomps] = np.stack([_optimal_shifts(cen[i, :, a] / L[i, a])
                                        for a in range(3)], axis=1) * L[i]
        if sh.any():
            P += sh[:, t.labels]

    # 3. wrap everything else -- never the glued set, or 2 is undone
    if wrap and t.nothers:
        gcen = P[:, t.glued].mean(axis=1)
        cen = _sums(P, t.labels, t.ncomp) / t.count[None, :, None]
        sh = -np.round((cen - gcen[:, None, :]) / Lb) * Lb
        sh[:, t.gcomps] = 0.0
        P += sh[:, t.labels]
    return P


def _process(nstates, fetch, load, cells, t, fit_idx, wrap=1, threads=1, block=16):
    """Steps 1-4 for states 1..nstates.

    fetch(states) -> coordinates (len(states) x N x 3) and load(states, P) are
    called from this thread only, in state order; the numpy work in between
    runs on `threads` threads.  cells[s - 1] is state s's cell, or None.
    """
    def glue(P, Ls):
        boxed = [i for i, L in enumerate(Ls) if L is not None]
        if boxed:
            sub = P[boxed]
            _glue_block(sub, np.array([Ls[i] for i in boxed]), t, wrap)
            P[boxed] = sub
        return P

    # 4. align, last.  State 1 has been made whole, so it is a sane reference
    #    -- fitting to a split structure gives a bogus rotation.
    ref = glue(fetch([1]), cells[:1])[0][fit_idx].copy()

    def work(states, P):
        glue(P, [cells[s - 1] for s in states])
        for i, s in enumerate(states):
            if s != 1:
                R, pc, qc = _kabsch(P[i][fit_idx], ref)
                P[i] = (P[i] - pc) @ R.T + qc
        return P

    threads = max(1, threads)
    pending = deque()
    with ThreadPoolExecutor(max_workers=threads) as ex:
        for s0 in range(1, nstates + 1, block):
            states = list(range(s0, min(s0 + block, nstates + 1)))
            pending.append((states, ex.submit(work, states, fetch(states))))
            if len(pending) > threads:          # bound the memory in flight
                states, fut = pending.popleft()
                load(states, fut.result())
        while pending:
            states, fut = pending.popleft()
            load(states, fut.result())


def _cell_kind(sym):
    """What one state's symmetry is: box, crystal, triclinic or none.

    Only a "box" is a periodic MD cell that the PBC steps may touch.  A
    crystal structure's cell is not one: wrapping its waters around the
    protein moves them a whole cell vector, and its angles need not be 90
    degrees at all.  An MD box is written as P 1; anything else
    (P 21 21 21, C 1 2 1 ...) came from a diffraction experiment.
    """
    # a boxless file reports a placeholder rather than nothing
    if not sym or min(sym[:3]) <= 2.0:
        return "none"
    if _is_crystal(sym):
        return "crystal"
    if not np.allclose(sym[3:6], 90.0):
        return "triclinic"
    return "box"


def _is_crystal(sym):
    """True for a diffraction cell, i.e. any spacegroup other than P 1."""
    sg = str(sym[6]).strip() if sym is not None and len(sym) > 6 else ""
    return bool(sg) and sg.replace(" ", "").upper() != "P1"


def _cell(obj, state):
    """Orthorhombic cell edges of one state, or None when there is no usable box."""
    # per state: an NPT box changes size from frame to frame
    sym = cmd.get_symmetry(obj, state)
    if _cell_kind(sym) != "box":
        return None
    return np.array(sym[:3], dtype=float)


def glue_traj(glue="polymer", fit="polymer and name CA", obj=None, wrap=1,
              quiet=0, align=None, threads=0):
    """threads: numpy threads for the gluing; 0 = one per CPU."""
    if align:                      # -align is an alias for -fit
        fit = align
    obj = obj or cmd.get_object_list()[0]
    wrap, quiet, threads = int(wrap), int(quiet), int(threads)
    threads = threads if threads > 0 else (os.cpu_count() or 1)
    t0 = time.time()

    nat, start, nbr = _adjacency(obj)
    gidx = _indices("(%s) and (%s)" % (obj, glue))
    if not len(gidx):
        _fail("glue selection matched nothing")
    t = _Topology(nat, start, nbr, gidx)
    if not quiet:
        print("glue: %d atoms in %d components; %d other molecules"
              % (len(gidx), len(t.gcomps), t.nothers))

    fit_idx = _indices("(%s) and (%s)" % (obj, fit))
    if len(fit_idx) < 3:
        _fail("fit selection needs at least 3 atoms")

    nstates = cmd.count_states(obj)
    cells = [_cell(obj, st) for st in range(1, nstates + 1)]
    # said even when quiet: "the trajectory is not glued" is not a detail
    if cells[0] is None:
        sym = cmd.get_symmetry(obj, 1)
        kind = _cell_kind(sym)
        if kind == "crystal":
            print("glue: %s is a crystal cell, not a periodic box"
                  " -- aligning only" % str(sym[6]).strip())
        elif kind == "triclinic":
            print("glue: triclinic box (%.1f %.1f %.1f, %.1f %.1f %.1f)"
                  " not supported -- aligning only" % tuple(sym[:6]))
        else:
            print("glue: no usable periodic cell -- aligning only")

    def fetch(states):
        # get_coords, NOT get_coordset: coordset rows are not ordered by the
        # internal atom index, so indexing them with a selection's indices
        # silently pairs up the wrong atoms.
        return np.stack([cmd.get_coords(obj, s) for s in states]).astype(float)

    def load(states, P):
        # The fit is computed here rather than with cmd.intra_fit, which
        # computes a fit but does not write it back to the coordsets.
        for s, x in zip(states, P):
            cmd.load_coords(x, obj, s)

    # ~16 states per block, fewer for very large systems to bound memory
    block = max(1, min(16, 4000000 // max(nat, 1)))
    _process(nstates, fetch, load, cells, t, fit_idx, wrap, threads, block)
    if not quiet:
        print("glue: processed %d states in %.1f s on %d threads"
              % (nstates, time.time() - t0, threads))


if cmd is not None:
    cmd.extend("glue_traj", glue_traj)
