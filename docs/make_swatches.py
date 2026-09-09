#!/usr/bin/env python3
"""Render the colour-scheme swatches used in docs/colors.rst.

Run from the repository root:

    python docs/make_swatches.py

The palette here is the single source of truth: vizard/align.tcl and
pizard/pizard.py carry the same values, and tests/test_palette.py checks that
all three agree.
"""
import os

from PIL import Image, ImageDraw, ImageFont

# (name, cartoon, pocket carbons, ligand carbons) as 0-255 RGB
PALETTE = [
    ("green",     (51, 153, 51), (102, 187, 102), (166, 230, 166)),
    ("raspberry", (178, 77, 102), (213, 128, 156), (255, 191, 222)),
    ("olive",     (196, 179, 0), (223, 213, 57), (255, 255, 128)),
    ("blue",      (64, 64, 166), (121, 121, 206), (191, 191, 255)),
    ("red",       (178, 33, 33), (213, 87, 87), (255, 153, 153)),
    ("teal",      (26, 153, 153), (106, 199, 199), (204, 255, 255)),
    ("purple",    (153, 26, 153), (199, 71, 199), (255, 128, 255)),
    ("brown",     (166, 82, 43), (205, 139, 98), (252, 209, 166)),
]

W, H, PAD = 720, 64, 8
BG = (18, 18, 20)
FG = (235, 235, 235)


def _font(size=13):
    for p in ("/System/Library/Fonts/Menlo.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def hexcode(rgb):
    return "#%02X%02X%02X" % rgb


def swatch(name, colours, path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f = _font()
    labels = ("cartoon", "pocket C", "ligand C")
    cw = (W - 4 * PAD) // 3
    for i, (c, lab) in enumerate(zip(colours, labels)):
        x = PAD + i * (cw + PAD)
        d.rectangle([x, PAD, x + cw, H - PAD - 16], fill=c)
        d.text((x, H - PAD - 14), "%-9s %s" % (lab, hexcode(c)), fill=FG, font=f)
    img.save(path)


def strip(path):
    """One row per scheme: cartoon | pocket | ligand."""
    rh, n = 34, len(PALETTE)
    img = Image.new("RGB", (W, rh * n + 2 * PAD), BG)
    d = ImageDraw.Draw(img)
    f = _font(12)
    cw = (W - 110 - 4 * PAD) // 3
    for r, (name, *colours) in enumerate(PALETTE):
        y = PAD + r * rh
        d.text((PAD, y + 9), "%-10s %d" % (name, r), fill=FG, font=f)
        for i, c in enumerate(colours):
            x = 100 + PAD + i * (cw + PAD)
            d.rectangle([x, y + 2, x + cw, y + rh - 6], fill=c)
    img.save(path)


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "_static", "colors")
    os.makedirs(out, exist_ok=True)
    # Names carry the scheme name, so reordering the palette leaves the old
    # files behind. Clear them, or CI's "swatches are current" check passes
    # while the directory still holds images nothing references.
    for f in os.listdir(out):
        if f.startswith("scheme") and f.endswith(".png"):
            os.remove(os.path.join(out, f))
    for i, (name, *colours) in enumerate(PALETTE):
        swatch(name, colours, os.path.join(out, "scheme%d_%s.png" % (i, name)))
    strip(os.path.join(out, "palette.png"))
    print("wrote %d swatches to %s" % (len(PALETTE) + 1, out))


if __name__ == "__main__":
    main()
