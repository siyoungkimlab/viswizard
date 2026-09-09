"""
glue.py -- keep unbonded components together across PBC, then align.

Run it on a loaded trajectory and the ligand stops hopping across the box:

    run glue.py
    glue_traj glue="polymer or resn LIG", fit="polymer and name CA"

Orthorhombic cells.  For triclinic, replace the /L and *L below with the
inverse-cell and cell matrices.
"""
import numpy as np
import pymol
from pymol import cmd

__all__ = ["glue_traj"]


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


def _adjacency(obj):
    """0-based bond list -> CSR-ish neighbour arrays."""
    model = cmd.get_model(obj)
    nat = len(model.atom)
    bonds = np.array([b.index for b in model.bond], dtype=np.int64).reshape(-1, 2)
    deg = np.bincount(bonds.ravel(), minlength=nat)
    start = np.concatenate([[0], np.cumsum(deg)])
    nbr = np.empty(2 * len(bonds), dtype=np.int64)
    fill = start[:-1].copy()
    for i, j in bonds:
        nbr[fill[i]] = j; fill[i] += 1
        nbr[fill[j]] = i; fill[j] += 1
    return nat, start, nbr


def _bfs(nat, start, nbr):
    """Connected components + a BFS spanning tree grouped by depth."""
    labels = np.full(nat, -1, dtype=np.int64)
    levels, ncomp = [], 0
    frontier_all = []
    for seed in range(nat):
        if labels[seed] >= 0:
            continue
        labels[seed] = ncomp
        frontier = [seed]
        depth = 0
        while frontier:
            par, chi = [], []
            for a in frontier:
                for k in range(start[a], start[a + 1]):
                    b = nbr[k]
                    if labels[b] < 0:
                        labels[b] = ncomp
                        par.append(a); chi.append(b)
            if not par:
                break
            while len(levels) <= depth:
                levels.append(([], []))
            levels[depth][0].extend(par)
            levels[depth][1].extend(chi)
            frontier = chi
            depth += 1
        ncomp += 1
    levels = [(np.array(p), np.array(c)) for p, c in levels]
    return labels, ncomp, levels


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


def glue_traj(glue="polymer", fit="polymer and name CA", obj=None, wrap=1,
              quiet=0, align=None):
    if align:                      # -align is an alias for -fit
        fit = align
    obj = obj or cmd.get_object_list()[0]
    wrap, quiet = int(wrap), int(quiet)
    nat, start, nbr = _adjacency(obj)
    labels, ncomp, levels = _bfs(nat, start, nbr)

    gidx = _indices("(%s) and (%s)" % (obj, glue))
    if not len(gidx):
        raise pymol.CmdException("glue selection matched nothing")
    gcomps = np.unique(labels[gidx])
    glued = np.isin(labels, gcomps)                 # every atom of every glued comp
    csel = [gidx[labels[gidx] == c] for c in gcomps]
    msel = [np.flatnonzero(labels == c) for c in gcomps]
    others = [np.flatnonzero(labels == c) for c in range(ncomp) if c not in set(gcomps)]
    if not quiet:
        print("glue: %d atoms in %d components; %d other molecules"
              % (len(gidx), len(gcomps), len(others)))

    fit_idx = _indices("(%s) and (%s)" % (obj, fit))
    if len(fit_idx) < 3:
        raise pymol.CmdException("fit selection needs at least 3 atoms")
    ref = None

    nstates = cmd.count_states(obj)
    for st in range(1, nstates + 1):
        # get_coords, NOT get_coordset: coordset rows are not ordered by the
        # internal atom index, so indexing them with a selection's indices
        # silently pairs up the wrong atoms.
        pos = cmd.get_coords(obj, st).astype(float)

        # per state: an NPT box changes size from frame to frame
        sym = cmd.get_symmetry(obj, st)
        if not sym or min(sym[:3]) <= 2.0:
            # no usable cell (a boxless file reports a placeholder): the PBC
            # steps would destroy the structure, so align only
            if st == 1 and not quiet:
                print("glue: no usable periodic cell -- aligning only")
            L = None
        else:
            if not np.allclose(sym[3:6], 90.0):
                raise pymol.CmdException("triclinic cell not supported")
            L = np.array(sym[:3], dtype=float)

        if L is not None:
            # 1. fix bonds, level by level down the spanning tree
            for par, chi in levels:
                d = pos[chi] - pos[par]
                pos[chi] -= np.round(d / L) * L

            # 2. glue: shift whole components onto their jointly optimal images
            cen = np.array([pos[ix].mean(0) for ix in csel])
            sh = np.stack([_optimal_shifts(cen[:, k] / L[k]) for k in range(3)],
                          axis=1)
            for ix, sft in zip(msel, sh):
                if sft.any():
                    pos[ix] += sft * L

            # 3. wrap everything else -- never the glued set, or 2 is undone
            if wrap and others:
                gcen = pos[glued].mean(0)
                for ix in others:
                    pos[ix] -= np.round((pos[ix].mean(0) - gcen) / L) * L

        # 4. align, last.  State 1 has been made whole above, so it is a sane
        #    reference -- fitting to a split structure gives a bogus rotation.
        #    Done here rather than with cmd.intra_fit, which computes a fit but
        #    does not write it back to the coordsets this code manipulates.
        if ref is None:
            ref = pos[fit_idx].copy()
        else:
            R, pc, qc = _kabsch(pos[fit_idx], ref)
            pos = (pos - pc) @ R.T + qc

        cmd.load_coords(pos, obj, st)
    if not quiet:
        print("glue: processed %d states" % nstates)


cmd.extend("glue_traj", glue_traj)
