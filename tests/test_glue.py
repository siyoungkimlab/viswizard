"""The numpy core of the PyMOL glue (pizard/glue.py), without PyMOL."""
import numpy as np

import glue

L0 = 30.0
NA, NB, NW = 25, 15, 40          # chain A, chain B, three-atom waters


def _system(seed=0):
    """Two chains in contact plus waters: coordinates, bonds, glue indices."""
    rng = np.random.default_rng(seed)

    def chain(n, first):
        steps = rng.normal(size=(n - 1, 3))
        steps *= 1.5 / np.linalg.norm(steps, axis=1)[:, None]
        return np.vstack([first, first + np.cumsum(steps, axis=0)])

    a = chain(NA, np.array([10.0, 10.0, 10.0]))
    b = chain(NB, a[-1] + [3.5, 0.0, 0.0])       # touches A, not bonded to it
    o = rng.uniform(0, L0, size=(NW, 3))
    w = np.stack([o, o + [0.96, 0, 0], o + [0, 0.96, 0]], axis=1).reshape(-1, 3)
    xyz = np.vstack([a, b, w])

    bonds = [(i, i + 1) for i in range(NA - 1)]
    bonds += [(NA + i, NA + i + 1) for i in range(NB - 1)]
    for m in range(NW):
        o_ = NA + NB + 3 * m
        bonds += [(o_, o_ + 1), (o_, o_ + 2)]
    return xyz, np.array(bonds), np.arange(NA + NB)


def _frames(xyz, n=12, seed=1):
    """Moved and jiggled copies, then wrapped ATOM-wise: every molecule split."""
    rng = np.random.default_rng(seed)
    cells = [np.full(3, L0 * (1 + 0.01 * f)) for f in range(n)]   # NPT-like
    truth = np.stack([xyz + rng.uniform(-40, 40, 3) + rng.normal(0, 0.05, xyz.shape)
                      for _ in range(n)])
    split = np.stack([x - np.floor(x / L) * L for x, L in zip(truth, cells)])
    return truth, split, cells


def _topology(xyz, bonds, gidx):
    start, nbr = glue._csr(len(xyz), bonds)
    return glue._Topology(len(xyz), start, nbr, gidx)


def _bond_lengths(x, bonds):
    return np.linalg.norm(x[bonds[:, 0]] - x[bonds[:, 1]], axis=1)


def _min_ab(x):
    a, b = x[:NA], x[NA:NA + NB]
    return np.linalg.norm(a[:, None] - b[None], axis=2).min()


def _run(split, cells, t, fit_idx, threads, block):
    out = np.full_like(split, np.nan)
    order = []

    def fetch(states):
        return split[np.array(states) - 1].copy()

    def load(states, P):
        order.extend(states)
        out[np.array(states) - 1] = P

    glue._process(len(split), fetch, load, cells, t, fit_idx, 1, threads, block)
    return out, order


def test_split_system_is_whole_glued_and_wrapped():
    xyz, bonds, gidx = _system()
    truth, split, cells = _frames(xyz)
    t = _topology(xyz, bonds, gidx)
    P = glue._glue_block(split.copy(), np.array(cells), t)
    for f in range(len(P)):
        # every bond is whole again -- chains and waters alike
        assert np.allclose(_bond_lengths(P[f], bonds), _bond_lengths(truth[f], bonds))
        # the two chains are back in contact, not a box apart
        assert np.isclose(_min_ab(P[f]), _min_ab(truth[f]))
        # every water sits within half a box of the glued pair
        gcen = P[f][:NA + NB].mean(0)
        wcen = P[f][NA + NB:].reshape(NW, 3, 3).mean(1)
        assert (np.abs(wcen - gcen) <= cells[f] / 2 + 1e-9).all()


def test_threads_give_the_serial_result_in_state_order():
    xyz, bonds, gidx = _system()
    _, split, cells = _frames(xyz, n=23)
    t = _topology(xyz, bonds, gidx)
    fit_idx = np.arange(NA)
    serial, order1 = _run(split, cells, t, fit_idx, threads=1, block=5)
    threaded, order4 = _run(split, cells, t, fit_idx, threads=4, block=3)
    assert np.array_equal(serial, threaded)
    assert order1 == order4 == list(range(1, 24))
    # and each output state is ITS OWN input state, glued and fitted
    ref = glue._glue_block(split[:1].copy(), np.array(cells[:1]), t)[0][fit_idx]
    for f in (0, 7, 22):
        x = glue._glue_block(split[f:f + 1].copy(), np.array(cells[f:f + 1]), t)[0]
        if f:
            R, pc, qc = glue._kabsch(x[fit_idx], ref)
            x = (x - pc) @ R.T + qc
        assert np.allclose(threaded[f], x)


def test_states_without_a_cell_are_only_aligned():
    xyz, bonds, gidx = _system()
    truth, _, _ = _frames(xyz, n=6)
    t = _topology(xyz, bonds, gidx)
    out, _ = _run(truth, [None] * 6, t, np.arange(NA), threads=2, block=4)
    for f in range(6):
        d_in = np.linalg.norm(truth[f][:, None] - truth[f][None], axis=2)
        d_out = np.linalg.norm(out[f][:, None] - out[f][None], axis=2)
        assert np.allclose(d_in, d_out)          # rigid: nothing was unwrapped
