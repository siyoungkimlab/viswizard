"""Sequence-based superposition used by the VMD matchmaker."""
import numpy as np
import pytest

import superpose

ONE2THREE = {"A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE",
             "G": "GLY", "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU",
             "M": "MET", "N": "ASN", "P": "PRO", "Q": "GLN", "R": "ARG",
             "S": "SER", "T": "THR", "V": "VAL", "W": "TRP", "Y": "TYR"}
SEQ = "ACDEFGHIKLMNPQRSTVWY" * 5


def _chain(seed=0, n=100):
    rng = np.random.default_rng(seed)
    xyz = np.cumsum(rng.normal(size=(n, 3)) * 3.0, axis=0)
    return [(ONE2THREE[SEQ[i]], *xyz[i]) for i in range(n)], xyz


def _rotate(xyz, angle=0.9, shift=(12.0, -5.0, 3.0)):
    c, s = np.cos(angle), np.sin(angle)
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    return xyz @ R.T + np.asarray(shift)


def test_identical_chains_superpose_exactly():
    A, xyz = _chain()
    B = [(rn, *p) for rn, p in zip([a[0] for a in A], _rotate(xyz))]
    R, t, rms, n0, kept = superpose.superpose(A, B)
    assert n0 == 100 and kept == 100
    assert rms == pytest.approx(0.0, abs=1e-6)


def test_offset_numbering_still_matches():
    """The point of aligning by sequence: B is missing its first 10 residues."""
    A, xyz = _chain()
    moved = _rotate(xyz)
    B = [(A[i][0], *moved[i]) for i in range(10, 100)]
    R, t, rms, n0, kept = superpose.superpose(A, B)
    assert n0 == 90
    assert rms == pytest.approx(0.0, abs=1e-6)


def test_outliers_are_pruned():
    A, xyz = _chain()
    moved = _rotate(xyz)
    moved[:5] += 25.0                      # five residues badly out of place
    B = [(A[i][0], *moved[i]) for i in range(100)]
    R, t, rms, n0, kept = superpose.superpose(A, B, cutoff=2.0, iterations=5)
    assert kept < n0
    assert rms < 1.0


def test_too_few_residues_is_an_error():
    A, _ = _chain(n=2)
    with pytest.raises(SystemExit):
        superpose.superpose(A, A)
