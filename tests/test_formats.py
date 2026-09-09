"""DMS and MAE reading and writing, without VMD or PyMOL."""
import math

import pytest

import formats


def _system():
    """Three atoms of water plus a lone ion, with a cubic cell."""
    atoms = [
        dict(anum=8, elem="O", name="OW", resname="SOL", resid=1, chain="A",
             segid="W", x=0.0, y=0.0, z=0.0, mass=16.0, charge=-0.8,
             formal_charge=0),
        dict(anum=1, elem="H", name="HW1", resname="SOL", resid=1, chain="A",
             segid="W", x=0.96, y=0.0, z=0.0, mass=1.0, charge=0.4,
             formal_charge=0),
        dict(anum=1, elem="H", name="HW2", resname="SOL", resid=1, chain="A",
             segid="W", x=-0.24, y=0.93, z=0.0, mass=1.0, charge=0.4,
             formal_charge=0),
        dict(anum=11, elem="Na", name="NA", resname="NA", resid=2, chain="B",
             segid="I", x=5.0, y=5.0, z=5.0, mass=23.0, charge=1.0,
             formal_charge=1),
    ]
    bonds = [(0, 1, 1), (0, 2, 1)]
    cell = [[30.0, 0.0, 0.0], [0.0, 30.0, 0.0], [0.0, 0.0, 30.0]]
    return atoms, bonds, cell


def test_dms_round_trip(tmp_path):
    atoms, bonds, cell = _system()
    p = str(tmp_path / "s.dms")
    formats.write_dms(p, atoms, bonds, cell)
    got = formats.read_dms(p)

    assert len(got["atoms"]) == len(atoms)
    assert len(got["bonds"]) == len(bonds)
    assert got["cell"] == cell
    for a, b in zip(atoms, got["atoms"]):
        assert a["anum"] == b["anum"]
        assert a["name"] == b["name"]
        assert a["resname"] == b["resname"]
        assert a["resid"] == b["resid"]
        assert a["chain"] == b["chain"]
        assert b["elem"] == a["elem"]
        for k in "xyz":
            assert a[k] == pytest.approx(b[k])
    assert sorted(got["bonds"]) == sorted(bonds)


def test_mae_round_trip(tmp_path):
    atoms, bonds, cell = _system()
    p = str(tmp_path / "s.mae")
    formats.write_mae(p, atoms, bonds, cell)
    d = formats._read_any(p)

    assert len(d["atoms"]) == len(atoms)
    assert len(d["bonds"]) == len(bonds)
    # the cell survives as lengths and angles, so compare vector norms
    for want, got in zip(cell, d["cell"]):
        assert math.dist(want, [0, 0, 0]) == pytest.approx(
            math.dist(got, [0, 0, 0]), abs=1e-3)
    assert [a["name"] for a in d["atoms"]] == [a["name"] for a in atoms]


def test_dms_to_mae_to_dms(tmp_path):
    atoms, bonds, cell = _system()
    a = str(tmp_path / "a.dms")
    b = str(tmp_path / "b.mae")
    c = str(tmp_path / "c.dms")
    formats.write_dms(a, atoms, bonds, cell)
    assert formats.convert(a, b) == (len(atoms), len(bonds))
    assert formats.convert(b, c) == (len(atoms), len(bonds))
    end = formats.read_dms(c)
    assert len(end["atoms"]) == len(atoms)
    assert sorted(end["bonds"]) == sorted(bonds)


def test_read_dms_rejects_a_non_dms_file(tmp_path):
    p = tmp_path / "not.dms"
    p.write_bytes(b"this is not a database")
    with pytest.raises(Exception):
        formats.read_dms(str(p))


def test_dump_reader(tmp_path):
    """The text dump the VMD side writes, since its Tcl has no sqlite3."""
    p = tmp_path / "d.vizdump"
    p.write_text("\t".join(["CELL"] + ["30", "0", "0", "0", "30", "0",
                                       "0", "0", "30"]) + "\n"
                 + "\t".join(["ATOM", "8", "OW", "SOL", "1", "A", "W",
                              "0.0", "0.0", "0.0", "16.0", "-0.8"]) + "\n"
                 + "\t".join(["ATOM", "1", "HW1", "SOL", "1", "A", "W",
                              "0.96", "0.0", "0.0", "1.0", "0.4"]) + "\n"
                 + "\t".join(["BOND", "0", "1", "1"]) + "\n")
    d = formats.read_dump(str(p))
    assert len(d["atoms"]) == 2
    assert d["bonds"] == [(0, 1, 1)]
    assert d["cell"][0][0] == 30.0
