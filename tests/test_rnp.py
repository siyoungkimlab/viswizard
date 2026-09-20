"""PLINDER system ids for pizard (pizard/rnp.py), no PyMOL and no network."""
import io
import os
import urllib.error

import pytest

import rnp

SID = "8g62__1__1.A__1.F_1.J_1.L"


def test_parse_splits_the_four_fields():
    s = rnp.parse(SID)
    assert (s.pdb_id, s.assembly) == ("8g62", "1")
    assert s.receptor == ["1.A"]
    assert s.ligands == ["1.F", "1.J", "1.L"]
    assert s.chains == ["1.A", "1.F", "1.J", "1.L"]


def test_parse_handles_several_receptor_chains():
    s = rnp.parse("7ts2__1__1.A_1.B__1.K_1.L_1.M")
    assert s.receptor == ["1.A", "1.B"]
    assert s.ligands == ["1.K", "1.L", "1.M"]


@pytest.mark.parametrize("bad", [
    "8g62__1__1.A",                  # too few fields
    "8g62__1__1.A__1.F__extra",      # too many
    "8g6__1__1.A__1.F",              # not a 4-character PDB id
    "8g62__1__A__1.F",               # chain without an instance
    "8g62__1__1.A__F",
])
def test_parse_rejects_what_is_not_a_system_id(bad):
    with pytest.raises(ValueError):
        rnp.parse(bad)


def test_asym_and_instance():
    assert rnp.asym("1.F") == "F"
    assert rnp.asym("2.BA") == "BA"
    assert rnp.instance("2.A") == 2


def test_resolve_ligand_takes_either_spelling():
    s = rnp.parse(SID)
    assert rnp.resolve_ligand(s, "1.F") == "1.F"
    assert rnp.resolve_ligand(s, "F") == "1.F"
    assert rnp.resolve_ligand(s, "f") == "1.F"
    assert rnp.resolve_ligand(s, None) is None


def test_resolve_ligand_says_what_the_choices_are():
    s = rnp.parse(SID)
    with pytest.raises(ValueError) as e:
        rnp.resolve_ligand(s, "1.Z")
    assert "1.F, 1.J, 1.L" in str(e.value)


def test_resolve_ligand_refuses_a_receptor_chain():
    # 1.A is a chain of the system, but not one of its ligands
    with pytest.raises(ValueError):
        rnp.resolve_ligand(rnp.parse(SID), "1.A")


def test_selection_is_segi_because_that_is_where_label_asym_id_lands():
    # RCSB file: the bare label_asym_id, which PyMOL puts in segi
    assert rnp.selection(["1.F"], local=False) == "segi F"
    assert rnp.selection(["1.A", "1.F"], local=False) == "segi A+F"
    # ground-truth system.cif: chains are already called 1.A and 1.F
    assert rnp.selection(["1.A", "1.F"], local=True) == "segi 1.A+1.F"
    assert rnp.selection([], local=False) == "none"


def test_ground_truth_finds_an_unpacked_system(tmp_path):
    d = tmp_path / "ground_truth" / SID
    d.mkdir(parents=True)
    (d / "system.cif").write_text("data_x\n")
    assert rnp.ground_truth(SID, [str(tmp_path / "ground_truth")]) == str(
        d / "system.cif")
    assert rnp.ground_truth("nope__1__1.A__1.B",
                            [str(tmp_path / "ground_truth")]) is None


def test_ground_truth_skips_an_unset_environment_variable(tmp_path):
    assert rnp.ground_truth(SID, ["$RNP_NOT_SET_ANYWHERE"]) is None


def test_prepare_builds_a_pizard_command_line(tmp_path):
    seen = {}

    def fake_fetch(pdb_id, dest):
        seen["pdb_id"], seen["dest"] = pdb_id, dest
        return os.path.join(dest, pdb_id + ".cif")

    ctx = rnp.prepare([SID, "1.F"], dirs=[], fetcher=fake_fetch)
    assert seen["pdb_id"] == "8g62"
    argv = ctx.argv
    assert argv[0].endswith("8g62.cif")
    assert argv[argv.index("--ligand") + 1] == "segi F"
    assert argv[argv.index("--only") + 1] == "segi A+F+J+L"
    assert argv[argv.index("--strip") + 1] == "none"
    assert argv[argv.index("--object") + 1] == "8g62"
    assert ctx.others == ["1.J", "1.L"]      # drawn as grey lines
    assert ctx.local is False

    # the CIF lives in a temporary directory and goes away after loading
    assert os.path.isdir(ctx.temp)
    ctx.cleanup()
    assert not os.path.exists(seen["dest"])


def test_prepare_without_a_ligand_chain_takes_them_all():
    ctx = rnp.prepare([SID], dirs=[], fetcher=lambda p, d: os.path.join(d, "x.cif"))
    assert ctx.argv[ctx.argv.index("--ligand") + 1] == "segi F+J+L"
    assert ctx.others == []
    ctx.cleanup()


def test_prepare_prefers_a_local_ground_truth_and_downloads_nothing(tmp_path):
    d = tmp_path / SID
    d.mkdir()
    (d / "system.cif").write_text("data_x\n")

    def no_fetch(pdb_id, dest):
        raise AssertionError("should not download when ground truth is there")

    ctx = rnp.prepare([SID, "1.F"], dirs=[str(tmp_path)], fetcher=no_fetch)
    assert ctx.local is True and ctx.temp is None
    assert ctx.argv[0] == str(d / "system.cif")
    assert ctx.argv[ctx.argv.index("--ligand") + 1] == "segi 1.F"
    assert ctx.argv[ctx.argv.index("--only") + 1] == "segi 1.A+1.F+1.J+1.L"


def test_prepare_passes_other_flags_through():
    ctx = rnp.prepare([SID, "1.F", "--pocket", "8", "--out", "m.mp4"],
                      dirs=[], fetcher=lambda p, d: os.path.join(d, "x.cif"))
    assert ctx.argv[-4:] == ["--pocket", "8", "--out", "m.mp4"]
    ctx.cleanup()


def test_prepare_complains_about_a_third_positional():
    with pytest.raises(SystemExit):
        rnp.prepare([SID, "1.F", "1.J"], dirs=[],
                    fetcher=lambda p, d: os.path.join(d, "x.cif"))


def test_prepare_needs_a_system_id():
    with pytest.raises(SystemExit):
        rnp.prepare(["--pocket", "8"], dirs=[])


# ---- electron density ---------------------------------------------------

def test_density_kinds():
    assert rnp.density_kinds("2fofc") == ["2fofc"]
    assert rnp.density_kinds("fofc") == ["fofc"]
    assert rnp.density_kinds("both") == ["2fofc", "fofc"]
    for off in ("off", "none", "no", "0", ""):
        assert rnp.density_kinds(off) == []


def test_density_kinds_rejects_anything_else():
    with pytest.raises(SystemExit):
        rnp.density_kinds("2fofc-ish")


def test_map_urls_are_the_two_pdbe_files():
    assert rnp.PDBE_MAPS["2fofc"] % "8g62" == (
        "https://www.ebi.ac.uk/pdbe/entry-files/8g62.ccp4")
    assert rnp.PDBE_MAPS["fofc"] % "8g62" == (
        "https://www.ebi.ac.uk/pdbe/entry-files/8g62_diff.ccp4")


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_fetch_map_writes_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(rnp.urllib.request, "urlopen",
                        lambda url, timeout=0: _FakeResponse(b"MAP DATA"))
    p = rnp.fetch_map("8G62", "2fofc", str(tmp_path))
    assert os.path.basename(p) == "8g62_2fofc.ccp4"
    assert open(p, "rb").read() == b"MAP DATA"


def test_fetch_map_returns_none_when_there_is_no_map(tmp_path, monkeypatch):
    def boom(url, timeout=0):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(rnp.urllib.request, "urlopen", boom)
    assert rnp.fetch_map("2kod", "2fofc", str(tmp_path)) is None
    # and it leaves no half-written file behind
    assert os.listdir(str(tmp_path)) == []


def test_tempdir_is_made_on_demand_for_a_local_system(tmp_path):
    d = tmp_path / SID
    d.mkdir()
    (d / "system.cif").write_text("data_x\n")
    ctx = rnp.prepare([SID], dirs=[str(tmp_path)],
                      fetcher=lambda p, dd: None)
    assert ctx.temp is None          # nothing downloaded yet
    scratch = ctx.tempdir()          # ... until a map needs somewhere to go
    assert os.path.isdir(scratch)
    ctx.cleanup()
    assert not os.path.exists(scratch)
