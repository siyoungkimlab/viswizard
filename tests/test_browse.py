"""Object picking for the PyMOL browse command (pizard/browse.py), no PyMOL."""
import browse


class FakeCmd:
    """Just enough of cmd for the parts that do not touch the viewer."""

    def __init__(self, objects, counts=None):
        self.objects = objects
        self.counts = counts or {}

    def get_object_list(self):
        return list(self.objects)

    def count_atoms(self, sel):
        return self.counts.get(sel, 0)


def test_browsable_skips_the_reference_structure(monkeypatch):
    monkeypatch.setattr(browse, "cmd", FakeCmd(["apo", "holo", "ref"]))
    assert browse._browsable() == ["apo", "holo"]


def test_browsable_takes_an_explicit_list(monkeypatch):
    monkeypatch.setattr(browse, "cmd", FakeCmd(["a", "b", "c"]))
    assert browse._browsable("b, c") == ["b", "c"]
    assert browse._browsable("b c") == ["b", "c"]


def test_zoom_target_is_the_ligand_when_it_matches(monkeypatch):
    monkeypatch.setattr(browse, "cmd",
                        FakeCmd(["apo"], {"(apo) and (chain L)": 9}))
    assert browse._zoom_target("apo", "chain L") == ("(apo) and (chain L)", 9)


def test_zoom_target_falls_back_to_the_whole_structure(monkeypatch):
    monkeypatch.setattr(browse, "cmd", FakeCmd(["apo"]))
    assert browse._zoom_target("apo", "chain L") == ("apo", 0)
    assert browse._zoom_target("apo", "") == ("apo", 0)
