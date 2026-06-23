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
    """Draw the Spiritbound emblem - a glowing spirit wisp with a bonded heart -
    at a given square size; returns a Surface."""
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
    by = size * 0.60          # centre of the wisp's round base
    br = size * 0.27          # base radius
    tipy = size * 0.11        # flame tip
    w = br * 0.98

    def scl(pts):
        return [(int(round(x)), int(round(y))) for x, y in pts]

    def flame(col, grow=0.0, tip=tipy):
        """A teardrop: round base + tapering point, drawn as a circle plus a
        triangle in one colour so they merge into a flame."""
        pygame.draw.circle(s, col, (int(round(cx)), int(round(by))), int(round(br + grow)))
        pts = [(cx - (w + grow), by),
               (cx - (w + grow) * 0.45, size * 0.42),
               (cx, tip),
               (cx + (w + grow) * 0.45, size * 0.42),
               (cx + (w + grow), by)]
        pygame.draw.polygon(s, col, scl(pts))

    # soft aura behind the wisp (layered translucent halos)
    aura = pygame.Surface((size, size), pygame.SRCALPHA)
    for rr, aa in ((0.48, 38), (0.38, 58), (0.30, 86)):
        pygame.draw.circle(aura, (CYAN[0], CYAN[1], CYAN[2], aa),
                           (int(cx), int(size * 0.56)), max(1, int(size * rr)))
    s.blit(aura, (0, 0))

    # darker rim, then the body, then a hotter inner core flame
    flame(CYAN_LO, grow=max(1.0, size * 0.035))
    flame(CYAN, grow=0.0)
    # inner core (smaller, brighter)
    cby, cbr, cw = size * 0.62, br * 0.56, br * 0.52
    pygame.draw.circle(s, CYAN_HI, (int(round(cx)), int(round(cby))), int(round(cbr)))
    pygame.draw.polygon(s, CYAN_HI, scl([(cx - cw, cby), (cx - cw * 0.45, size * 0.50),
                                         (cx, size * 0.27),
                                         (cx + cw * 0.45, size * 0.50), (cx + cw, cby)]))

    # the bonded heart: a warm gold soul-spark at the centre
    hx, hy = int(round(cx)), int(round(size * 0.585))
    hr = max(1, int(round(size * 0.075)))
    pygame.draw.circle(s, GOLD, (hx, hy), hr)
    if size >= 32:
        pygame.draw.circle(s, (255, 250, 236), (hx, hy - max(1, hr // 3)), max(1, hr // 2))

    # orbiting spirit motes once there's room for them to read
    if size >= 40:
        for mx, my, mr in ((-0.33, 0.30, 0.050), (0.35, 0.44, 0.045), (0.31, 0.20, 0.034)):
            pygame.draw.circle(s, GOLD, (int(round(cx + mx * size)), int(round(by + my * size * 0.6))),
                               max(1, int(round(size * mr))))

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
