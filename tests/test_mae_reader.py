"""The .mae parser, including the syntax that used to break it."""
import gzip

import mae_reader

MINIMAL = """{
  s_m_m2io_version
  :::
  2.0.0
}

f_m_ct {
  s_m_title
  r_chorus_box_ax
  r_chorus_box_ay
  r_chorus_box_az
  r_chorus_box_bx
  r_chorus_box_by
  r_chorus_box_bz
  r_chorus_box_cx
  r_chorus_box_cy
  r_chorus_box_cz
  :::
  "a title with spaces"
  30.0
  0.0
  0.0
  0.0
  30.0
  0.0
  0.0
  0.0
  30.0
  m_atom[2] {
    i_m_atomic_number
    r_m_x_coord
    r_m_y_coord
    r_m_z_coord
    i_m_residue_number
    s_m_pdb_residue_name
    s_m_pdb_atom_name
    :::
    1 8 0.0 0.0 0.0 1 "SOL " " OW "
    2 1 0.96 0.0 0.0 1 "SOL " " HW1"
    :::
  }
  m_bond[1] {
    i_m_from
    i_m_to
    i_m_order
    :::
    1 1 2 1
    :::
  }
}
"""


def test_minimal(tmp_path):
    p = tmp_path / "m.mae"
    p.write_text(MINIMAL)
    cts = mae_reader.parse_mae(str(p))
    assert len(cts) == 1
    ct = cts[0]
    assert len(ct["atoms"]) == 2
    assert ct["bonds"] == [(0, 1, 1)]
    assert ct["atoms"][0]["elem"] == "O"
    assert ct["atoms"][0]["name"] == "OW"
    assert ct["atoms"][0]["resn"] == "SOL"
    assert ct["cell"][:3] == [30.0, 30.0, 30.0]


def test_gzip(tmp_path):
    p = tmp_path / "m.mae.gz"
    with gzip.open(str(p), "wt") as fh:
        fh.write(MINIMAL)
    assert len(mae_reader.parse_mae(str(p))[0]["atoms"]) == 2


def test_property_name_containing_brackets(tmp_path):
    """A '[' is only structural in "m_atom[2] {".

    Property names may contain brackets. Treating every '[' as structural
    desynchronises the column list and silently mangles every row.
    """
    text = MINIMAL.replace("  s_m_title\n",
                           "  s_m_title\n  r_odd_name_with_[brackets,_x]_here\n")
    text = text.replace('  "a title with spaces"\n',
                        '  "a title with spaces"\n  1234.5\n')
    p = tmp_path / "b.mae"
    p.write_text(text)
    ct = mae_reader.parse_mae(str(p))[0]
    assert len(ct["atoms"]) == 2
    assert ct["atoms"][1]["name"] == "HW1"
    assert ct["props"]["r_odd_name_with_[brackets,_x]_here"] == "1234.5"


def test_absent_values(tmp_path):
    p = tmp_path / "a.mae"
    p.write_text(MINIMAL.replace('1 8 0.0 0.0 0.0 1 "SOL " " OW "',
                                 '1 8 0.0 0.0 0.0 1 <> " OW "'))
    ct = mae_reader.parse_mae(str(p))[0]
    assert ct["atoms"][0]["resn"] == ""


def _ct(tmp_path, text=MINIMAL):
    p = tmp_path / "one.mae"
    p.write_text(text)
    return mae_reader.parse_mae(str(p))[0]


def test_merge_keeps_file_order_and_renumbers_bonds(tmp_path):
    ct = _ct(tmp_path)
    merged = mae_reader.merge_cts([ct, ct, ct])
    assert len(merged["atoms"]) == 6
    # each block's bond 0-1 moves along with its atoms
    assert merged["bonds"] == [(0, 1, 1), (2, 3, 1), (4, 5, 1)]
    assert [a["name"] for a in merged["atoms"]] == ["OW", "HW1"] * 3
    assert merged["cell"] == ct["cell"]


def test_blocks_in_one_box_are_one_system(tmp_path):
    ct = _ct(tmp_path)
    assert mae_reader.one_system([ct, ct])            # solute + water + ions
    assert not mae_reader.one_system([ct])            # nothing to merge


def test_blocks_without_a_common_box_stay_apart(tmp_path):
    ct = _ct(tmp_path)
    other = dict(ct, cell=[40.0, 40.0, 40.0, 90.0, 90.0, 90.0])
    boxless = dict(ct, cell=None)
    assert not mae_reader.one_system([ct, other])     # different boxes
    assert not mae_reader.one_system([boxless, boxless])   # poses, say
