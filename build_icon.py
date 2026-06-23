"""
Spiritbound - procedural icon generator.

Renders the game's emblem to a multi-size Windows .ico, in keeping with
the project's "no asset files" rule: the icon is generated at build time from
code, never committed. Used by the release workflow (and runnable by hand) to
produce `spiritbound.ico` for PyInstaller's `--icon`.

    python build_icon.py            # writes spiritbound.ico next to this file
    python build_icon.py out.ico    # custom path

Pure pygame for drawing plus a tiny stdlib ICO container writer, so it needs no
dependency beyond pygame-ce (already required to run the game).

Written by LJ "HawaiizFynest" Eblacas
"""

import io
import os
import struct
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

# Brand palette (mirrors game/config.py so the icon matches the title screen).
CYAN = (64, 210, 224)
CYAN_HI = (170, 244, 250)
CYAN_LO = (28, 120, 150)
GOLD = (240, 196, 92)
BG_TOP = (24, 30, 52)
BG_BOT = (14, 18, 34)
OUTLINE = (10, 14, 26)

# Windows .ico sizes most apps ship. 256 is stored as PNG, the rest as BMP.
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _render(size):
    """Draw the faceted crystal at a given square size; returns a Surface."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)

    # rounded-square backdrop with a vertical gradient
    for y in range(size):
        f = y / max(1, size - 1)
        col = (int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * f),
               int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * f),
               int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * f))
        pygame.draw.line(s, col, (0, y), (size, y))
    radius = max(2, size // 6)
    # mask the gradient to a rounded rect by punching transparent corners
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, size, size), border_radius=radius)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    cx = size / 2
    w = size * 0.40           # half-width of the crystal
    top = size * 0.14
    shoulder = size * 0.40    # where the body widens out
    bottom = size * 0.90

    left = cx - w
    right = cx + w
    # crystal silhouette: a tall hexagon-ish gem
    body = [
        (cx, top),
        (right, shoulder),
        (right, size * 0.62),
        (cx, bottom),
        (left, size * 0.62),
        (left, shoulder),
    ]

    def scl(pts):
        return [(int(round(x)), int(round(y))) for x, y in pts]

    # base fill
    pygame.draw.polygon(s, CYAN, scl(body))
    # left facet (lighter), right facet (darker) for a faceted gem read
    left_facet = [(cx, top), (left, shoulder), (left, size * 0.62),
                  (cx, bottom), (cx, size * 0.50)]
    right_facet = [(cx, top), (right, shoulder), (right, size * 0.62),
                   (cx, bottom), (cx, size * 0.50)]
    pygame.draw.polygon(s, CYAN_HI, scl(left_facet))
    pygame.draw.polygon(s, CYAN_LO, scl(right_facet))
    # central highlight ridge
    pygame.draw.polygon(s, CYAN, scl([(cx, top), (cx + w * 0.18, shoulder),
                                      (cx, size * 0.50),
                                      (cx - w * 0.18, shoulder)]))

    if size >= 24:
        ow = max(1, size // 32)
        pygame.draw.polygon(s, OUTLINE, scl(body), ow)
        # a small gold spark at the top, the "bond" glint
        gx, gy = int(cx), int(top + size * 0.02)
        gr = max(1, size // 22)
        pygame.draw.circle(s, GOLD, (gx, gy), gr)
        if size >= 48:
            pygame.draw.circle(s, (255, 245, 210), (gx, gy), max(1, gr // 2))

    return s


def _surface_png_bytes(surf):
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "PNG")
    return buf.getvalue()


def _bmp_for_ico(surf):
    """A 32-bit BGRA DIB (BITMAPINFOHEADER + pixels + AND mask) for the ICO."""
    w, h = surf.get_size()
    # bottom-up rows, BGRA
    rows = []
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = surf.get_at((x, y))
            row += bytes((b, g, r, a))
        rows.append(bytes(row))
    pixels = b"".join(rows)

    # BITMAPINFOHEADER: height is doubled (color + AND mask) per ICO spec
    header = struct.pack("<IiiHHIIiiII",
                         40, w, h * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
    # AND mask: all-zero (opaque handled by alpha), padded to 32-bit per row
    and_row = ((w + 31) // 32) * 4
    and_mask = b"\x00" * (and_row * h)
    return header + pixels + and_mask


def write_ico(path):
    pygame.init()
    images = []   # (size, payload_bytes, is_png)
    for sz in SIZES:
        surf = _render(sz)
        if sz >= 256:
            images.append((sz, _surface_png_bytes(surf), True))
        else:
            images.append((sz, _bmp_for_ico(surf), False))

    # ICONDIR + ICONDIRENTRY table + image data
    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, len(images)))   # reserved, type=icon, count
    offset = 6 + 16 * len(images)
    for sz, data, _is_png in images:
        bsz = 0 if sz >= 256 else sz
        out.write(struct.pack("<BBBBHHII",
                              bsz, bsz, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    for _sz, data, _is_png in images:
        out.write(data)

    with open(path, "wb") as f:
        f.write(out.getvalue())
    pygame.quit()
    return path


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "spiritbound.ico")
    write_ico(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
