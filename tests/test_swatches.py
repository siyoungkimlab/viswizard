"""The committed swatch images really do show the documented colours.

Comparing the PNGs byte for byte does not work: the label font differs between
platforms, so the same palette renders to different bytes. Sample the colour
blocks instead, which is what the image is actually for.
"""
import importlib.util
import os

import pytest

PIL = pytest.importorskip("PIL.Image")
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLORS = os.path.join(ROOT, "docs", "_static", "colors")


def _swatch_module():
    spec = importlib.util.spec_from_file_location(
        "make_swatches", os.path.join(ROOT, "docs", "make_swatches.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


MS = _swatch_module()


def test_every_scheme_has_an_image():
    for i, (name, *_c) in enumerate(MS.PALETTE):
        p = os.path.join(COLORS, "scheme%d_%s.png" % (i, name))
        assert os.path.isfile(p), "missing swatch for scheme %d (%s)" % (i, name)
    assert os.path.isfile(os.path.join(COLORS, "palette.png"))


def test_no_stale_images():
    """Reordering the palette renames files; the old ones must not linger."""
    want = {"palette.png"} | {"scheme%d_%s.png" % (i, n)
                              for i, (n, *_c) in enumerate(MS.PALETTE)}
    have = {f for f in os.listdir(COLORS) if f.endswith(".png")}
    assert have == want, "unexpected files: %s" % sorted(have - want)


@pytest.mark.parametrize("i", range(8))
def test_swatch_blocks_carry_the_palette_colours(i):
    name, *colours = MS.PALETTE[i]
    img = Image.open(os.path.join(COLORS, "scheme%d_%s.png" % (i, name))).convert("RGB")
    cw = (MS.W - 4 * MS.PAD) // 3
    y = (MS.PAD + MS.H - MS.PAD - 16) // 2
    for j, want in enumerate(colours):
        x = MS.PAD + j * (cw + MS.PAD) + cw // 2
        assert img.getpixel((x, y)) == want, (
            "block %d of scheme %d (%s) is %s, expected %s"
            % (j, i, name, img.getpixel((x, y)), want))


def test_palette_strip_rows():
    img = Image.open(os.path.join(COLORS, "palette.png")).convert("RGB")
    rh = 34
    cw = (MS.W - 110 - 4 * MS.PAD) // 3
    for r, (name, *colours) in enumerate(MS.PALETTE):
        y = MS.PAD + r * rh + rh // 2 - 2
        for j, want in enumerate(colours):
            x = 100 + MS.PAD + j * (cw + MS.PAD) + cw // 2
            assert img.getpixel((x, y)) == want, (
                "row %d block %d is %s, expected %s"
                % (r, j, img.getpixel((x, y)), want))
