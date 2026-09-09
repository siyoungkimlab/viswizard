"""
superpose.py -- sequence-based structural superposition (matchmaker style).

Aligns two structures by SEQUENCE first, so residue numbering need not match,
then iteratively fits the matched CA pairs, dropping outliers each round.
Reads the CA dump VMD writes and prints the 4x4 transform.

    python3 superpose.py dump.txt [cutoff] [iterations]
"""
import sys

THREE2ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "HID": "H", "HIE": "H", "HIP": "H", "HSD": "H",
    "HSE": "H", "HSP": "H", "CYX": "C", "CYM": "C", "LYN": "K", "ASH": "D",
    "GLH": "E", "MSE": "M", "SEC": "U", "PYL": "O", "LYSH": "K", "HISB": "H",
    "NLE": "L", "ASPH": "D", "GLUH": "E",
}


def _nw(a, b, match=2, mismatch=-1, gap=-2):
    """Needleman-Wunsch; returns list of (i, j) aligned index pairs."""
    n, m = len(a), len(b)
    S = [[0] * (m + 1) for _ in range(n + 1)]
    P = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        S[i][0] = gap * i
        P[i][0] = 1
    for j in range(1, m + 1):
        S[0][j] = gap * j
        P[0][j] = 2
    for i in range(1, n + 1):
        ai = a[i - 1]
        Si, Sp = S[i], S[i - 1]
        Pi = P[i]
        for j in range(1, m + 1):
            d = Sp[j - 1] + (match if ai == b[j - 1] else mismatch)
            u = Sp[j] + gap
            l = Si[j - 1] + gap
            if d >= u and d >= l:
                Si[j], Pi[j] = d, 0
            elif u >= l:
                Si[j], Pi[j] = u, 1
            else:
                Si[j], Pi[j] = l, 2
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        p = P[i][j]
        if p == 0 and i > 0 and j > 0:
            i -= 1; j -= 1
            if a[i] == b[j]:
                pairs.append((i, j))
        elif p == 1 and i > 0:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def _kabsch(P, Q):
    import numpy as np
    pc = P.mean(0); qc = Q.mean(0)
    H = (P - pc).T @ (Q - qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return R, qc - R @ pc


def read_dump(path):
    A, B = [], []
    for line in open(path):
        f = line.split("\t")
        if f[0] in ("A", "B"):
            rec = (f[1], float(f[2]), float(f[3]), float(f[4]))
            (A if f[0] == "A" else B).append(rec)
    return A, B


def superpose(A, B, cutoff=2.0, iterations=5):
    import numpy as np
    sa = "".join(THREE2ONE.get(r[0].upper(), "X") for r in A)
    sb = "".join(THREE2ONE.get(r[0].upper(), "X") for r in B)
    pairs = _nw(sa, sb)
    if len(pairs) < 3:
        raise SystemExit("superpose: only %d matched residues" % len(pairs))
    P = np.array([[A[i][1], A[i][2], A[i][3]] for i, _ in pairs])
    Q = np.array([[B[j][1], B[j][2], B[j][3]] for _, j in pairs])

    n0 = len(pairs)
    for _ in range(int(iterations)):
        R, t = _kabsch(P, Q)
        d = np.sqrt(((P @ R.T + t - Q) ** 2).sum(1))
        keep = d <= cutoff
        if keep.sum() < 3 or keep.all():
            break
        P, Q = P[keep], Q[keep]
    R, t = _kabsch(P, Q)
    rms = float(np.sqrt(((P @ R.T + t - Q) ** 2).sum(1).mean()))
    return R, t, rms, n0, len(P)


if __name__ == "__main__":
    dump = sys.argv[1]
    cutoff = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    A, B = read_dump(dump)
    R, t, rms, n0, nk = superpose(A, B, cutoff, iters)
    # VMD row-major 4x4
    rows = [list(R[i]) + [t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]
    print("MATRIX " + " ".join("%.10f" % v for r in rows for v in r))
    print("STATS %d %d %.4f" % (n0, nk, rms))
