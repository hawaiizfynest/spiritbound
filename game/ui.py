"""
Spiritbound - UI widgets and procedural art.

Everything visual is drawn from primitives so the game ships with no image
files. draw_creature renders a distinct stylised look per species from its
shape + palette, draw_player / draw_npc render overworld characters, and
Textbox / Menu provide controller-and-keyboard friendly UI.

Written by LJ "HawaiizFynest" Eblacas
"""

import math
import os

import pygame

from . import config as C
from . import assets
from .core import draw_text, draw_panel, get_font, wrap_text, draw_bar
from .data import SPECIES, ELEMENTS, CATEGORY_NAMES, move_effect_blurb


# ---------------------------------------------------------------------------
# small drawing helpers
# ---------------------------------------------------------------------------
def _poly(surf, color, pts):
    pygame.draw.polygon(surf, color, [(int(x), int(y)) for x, y in pts])


def _circle(surf, color, c, r):
    pygame.draw.circle(surf, color, (int(c[0]), int(c[1])), max(1, int(r)))


def _ellipse(surf, color, rect):
    pygame.draw.ellipse(surf, color, pygame.Rect(int(rect[0]), int(rect[1]),
                                                  max(1, int(rect[2])), max(1, int(rect[3]))))


def _clamp(v):
    return max(0, min(255, int(v)))


def _lighten(c, f):
    return (_clamp(c[0] + (255 - c[0]) * f), _clamp(c[1] + (255 - c[1]) * f),
            _clamp(c[2] + (255 - c[2]) * f))


def _darken(c, f):
    return (_clamp(c[0] * (1 - f)), _clamp(c[1] * (1 - f)), _clamp(c[2] * (1 - f)))


def _mix(a, b, f):
    return (_clamp(a[0] + (b[0] - a[0]) * f), _clamp(a[1] + (b[1] - a[1]) * f),
            _clamp(a[2] + (b[2] - a[2]) * f))


def hp_color(frac):
    if frac > 0.5:
        return C.GREEN
    if frac > 0.2:
        return C.YELLOW
    return C.RED


def draw_pill(surf, x, y, text, color, size=14):
    """A small rounded badge: darkened ring, colored fill, dark label. Returns
    its pixel width. Shared by element badges and the swap recommendation
    badge (#24)."""
    w = get_font(size).size(text)[0] + 14
    rect = pygame.Rect(x, y, w, size + 6)
    pygame.draw.rect(surf, _darken(color, 0.35), rect, border_radius=(size + 6) // 2)
    inner = rect.inflate(-4, -4)
    pygame.draw.rect(surf, color, inner, border_radius=(size + 2) // 2)
    draw_text(surf, text, x + 7, y + 3, size, C.BLACK)
    return w


def draw_type_badge(surf, x, y, type_name, size=16):
    col = C.ELEMENT_COLORS.get(type_name, C.GREY)
    label = type_name if type_name else "Neutral"
    w = draw_pill(surf, x, y, label, col, size)
    return pygame.Rect(x, y, w, size + 6)


def draw_xp_bar(surf, x, y, w, frac, h=6, max_level=False):
    """Thin EXP fill bar (#19), shared by the battle status panel and the pause
    creature-detail / swap screens. `frac` is the 0..1 fill from
    Aether.xp_into_level(); pass the eased display value to animate it. At max
    level the bar reads full in gold."""
    if max_level:
        draw_bar(surf, x, y, w, h, 1.0, C.GOLD)
        return
    draw_bar(surf, x, y, w, h, frac, C.XP_COLOR)


def draw_move_card(surf, rect, move, mp_have=None, title=None):
    """Reusable move stat-card. Lays out a move's name, element badge,
    category, power, accuracy, MP cost and an effect blurb inside `rect`.

    Shared by the fight-menu move window (#21) and the move-learn screen (#18).
      rect    - (x, y, w, h) panel bounds
      move    - a MOVES entry dict
      mp_have - if given, the caster's current MP; the MP value turns red when
                the move can't be afforded
      title   - optional small heading drawn above the name (e.g. "NEW MOVE")
    The border tints to the move's element so it reads as live as the cursor
    moves between moves.
    """
    rect = pygame.Rect(rect)
    col = C.ELEMENT_COLORS.get(move.get("type"), C.ACCENT)
    draw_panel(surf, rect, fill=C.NEAR_BLACK, border=_mix(col, C.BORDER, 0.35),
               width=2, radius=10)
    pad = 12
    x = rect.x + pad
    y = rect.y + pad
    right = rect.right - pad

    if title:
        draw_text(surf, title.upper(), x, y, 15, C.ACCENT)
        y += 19

    # name (left) + element badge (right)
    badge_w = get_font(16).size(move.get("type") or "Neutral")[0] + 14
    draw_text(surf, move["name"], x, y, 24, C.WHITE)
    draw_type_badge(surf, right - badge_w, y + 1, move.get("type"), 16)
    y += 30

    # divider
    pygame.draw.line(surf, _darken(C.BORDER, 0.25), (x, y), (right, y), 1)
    y += 9

    # two-column stat grid: Power / Category, then Accuracy / MP
    col2 = rect.x + rect.width // 2 + 4
    power = move.get("power", 0)
    acc = move.get("acc", 0)
    mp = move.get("mp", 0)
    cat_name = CATEGORY_NAMES.get(move.get("cat"), move.get("cat", "--"))

    def _pair(px, py, label, value, value_col=C.WHITE):
        draw_text(surf, label, px, py, 16, C.GREY)
        draw_text(surf, value, px + 78, py, 18, value_col)

    _pair(x, y, "Power", str(power) if power else "—")
    _pair(col2, y, "Class", cat_name)
    y += 22
    mp_col = C.WHITE
    if mp_have is not None and mp > mp_have:
        mp_col = C.RED
    _pair(x, y, "Accuracy", f"{acc}%" if acc else "—")
    _pair(col2, y, "MP", str(mp) if mp > 0 else "—", value_col=mp_col)
    y += 26

    # effect blurb, wrapped to the remaining width/height
    blurb = move_effect_blurb(move)
    lines = wrap_text(blurb, 16, rect.width - 2 * pad)
    line_h = 18
    max_lines = max(1, (rect.bottom - pad - y) // line_h)
    for ln in lines[:max_lines]:
        draw_text(surf, ln, x, y, 16, C.GREY)
        y += line_h
    return rect


# ---------------------------------------------------------------------------
# Sticker-outline baker: stamp a silhouette in dark around the art, then the
# art on top. Gives every sprite a clean cartoon outline.
# ---------------------------------------------------------------------------
def _outline(art, col=(22, 22, 30), th=3):
    try:
        mask = pygame.mask.from_surface(art)
        sil = mask.to_surface(setcolor=(*col, 255), unsetcolor=(0, 0, 0, 0))
    except Exception:
        return art
    out = pygame.Surface(art.get_size(), pygame.SRCALPHA)
    for dx in range(-th, th + 1):
        for dy in range(-th, th + 1):
            if (dx or dy) and dx * dx + dy * dy <= th * th:
                out.blit(sil, (dx, dy))
    out.blit(art, (0, 0))
    return out


# ---------------------------------------------------------------------------
# Creature rendering (baked + cached shaded sprites)
# ---------------------------------------------------------------------------
_creature_cache = {}


def _eyes(art, cx, cy, S, face=1, r=None, glow=None):
    r = r if r else S * 0.13
    spread = max(r * 1.5, S * 0.2)
    for sgn in (-1, 1):
        ex = cx + sgn * spread
        if glow:
            g = pygame.Surface((int(r * 5), int(r * 5)), pygame.SRCALPHA)
            _circle(g, (*glow, 120), (r * 2.5, r * 2.5), r * 2.2)
            art.blit(g, (int(ex - r * 2.5), int(cy - r * 2.5)))
        _circle(art, (250, 250, 255), (ex, cy), r)
        pcol = glow if glow else (30, 30, 42)
        _circle(art, pcol, (ex + face * r * 0.35, cy), r * 0.6)
        _circle(art, (255, 255, 255), (ex + face * r * 0.35 - r * 0.25, cy - r * 0.28), max(1, r * 0.26))


def _mouth(art, cx, cy, S, col=(40, 30, 40)):
    w = S * 0.16
    pygame.draw.arc(art, col, pygame.Rect(int(cx - w), int(cy - w * 0.3),
                    int(w * 2), int(w)), math.pi + 0.4, 2 * math.pi - 0.4, max(2, int(S * 0.03)))


def _grad_body(art, rect, top, bot):
    """Smooth shaded body mass: base ellipse + upper highlight + lower shadow."""
    x, y, w, h = rect
    mid = _mix(top, bot, 0.45)
    _ellipse(art, mid, (x, y, w, h))
    _ellipse(art, top, (x + w * 0.13, y + h * 0.05, w * 0.66, h * 0.5))
    _ellipse(art, bot, (x + w * 0.17, y + h * 0.56, w * 0.66, h * 0.4))


def _flame(art, x, y, s, warm=(255, 140, 40), hot=(255, 224, 120)):
    _poly(art, warm, [(x, y - s), (x - s * 0.5, y - s * 0.1), (x - s * 0.28, y + s * 0.2),
                      (x, y + s * 0.08), (x + s * 0.28, y + s * 0.2), (x + s * 0.5, y - s * 0.1)])
    _poly(art, hot, [(x, y - s * 0.62), (x - s * 0.24, y), (x, y + s * 0.02), (x + s * 0.24, y)])


def _leaf(art, x, y, s, face, col):
    pts = [(x, y), (x + face * s * 0.7, y - s * 0.5), (x + face * s * 0.2, y - s * 0.85),
           (x - face * s * 0.05, y - s * 0.3)]
    _poly(art, col, pts)
    pygame.draw.line(art, _darken(col, 0.3), (int(x), int(y)),
                     (int(x + face * s * 0.3), int(y - s * 0.6)), max(1, int(s * 0.08)))


def _bolt(art, x, y, s, col=(255, 232, 90)):
    _poly(art, col, [(x, y - s), (x + s * 0.5, y - s * 0.25), (x + s * 0.1, y - s * 0.2),
                     (x + s * 0.5, y + s * 0.5), (x - s * 0.45, y - s * 0.05),
                     (x - s * 0.02, y - s * 0.1)])


def _element_motif(art, el, cx, cy, S, face, accent):
    """Element flourish placed on the head/back."""
    top = cy - S * 0.62
    if el == "Ember":
        _flame(art, cx, top, S * 0.34)
    elif el == "Verdant":
        _leaf(art, cx - S * 0.02, top + S * 0.16, S * 0.42, 1, _lighten(accent, 0.1))
        _leaf(art, cx + S * 0.04, top + S * 0.16, S * 0.36, -1, accent)
    elif el == "Tide":
        # dorsal fin
        _poly(art, _lighten(accent, 0.1),
              [(cx - S * 0.18, cy - S * 0.32), (cx, cy - S * 0.66),
               (cx + S * 0.18, cy - S * 0.32)])
    elif el == "Bolt":
        _bolt(art, cx, top + S * 0.18, S * 0.32, _lighten(accent, 0.2))
    elif el == "Gale":
        for k, rr in enumerate((0.34, 0.22)):
            pygame.draw.arc(art, _lighten(accent, 0.15),
                            pygame.Rect(int(cx - S * rr), int(top - S * 0.04 + k * S * 0.12),
                                        int(S * rr * 2), int(S * rr * 1.3)),
                            0.5, 3.4, max(2, int(S * 0.05)))
    elif el == "Terra":
        for dx in (-0.16, 0.0, 0.16):
            _poly(art, _lighten(accent, 0.12),
                  [(cx + dx * S, cy - S * 0.4), (cx + dx * S - S * 0.1, cy - S * 0.18),
                   (cx + dx * S + S * 0.1, cy - S * 0.18)])


def _feet(art, cx, cy, S, lo, n=2, spread=0.24):
    for sgn in ((-1, 1) if n == 2 else (-1.4, -0.5, 0.5, 1.4)):
        _ellipse(art, lo, (cx + sgn * S * spread - S * 0.1, cy + S * 0.34, S * 0.22, S * 0.16))


_RENDER_SID = None      # species being drawn, set per call in _render_creature

# Each blob species gets a different *body silhouette*, not just a different hat,
# so the eight of them stop reading as one recoloured blob.
_BLOB_FORM = {
    "cindle": "teardrop", "sprigit": "egg", "driblet": "round",
    "thornkin": "gem", "tunneler": "lump", "puffcap": "tall",
    "saltoad": "squat", "voltkit": "pear",
}
# where a blob form's head-top sits (crown anchor y, in S from centre)
_BLOB_HEADTOP = {"round": -0.42, "egg": -0.52, "tall": -0.60, "squat": -0.30,
                 "teardrop": -0.40, "pear": -0.50, "lump": -0.46, "gem": -0.56}
# quad proportions (body length, body height, head radius) - lizard/plant/dragon/ram
_QUAD_FORM = {
    "pyrachs": (1.06, 0.56, 0.25), "floravine": (0.90, 0.68, 0.30),
    "voltagon": (1.22, 0.64, 0.29), "craghorn": (0.94, 0.78, 0.25),
}


def _blob_body(art, cx, cy, S, form, body, accent, hi, lo):
    """Lay down a blob's main silhouette for its form (the later outline pass
    traces whatever we draw). Returns (eye_y, mouth_y) offsets in S and the belly
    rect (or None) so the face sits correctly on each different body."""
    hl = _lighten(body, 0.4)
    if form == "egg":
        _grad_body(art, (cx - S * 0.40, cy - S * 0.54, S * 0.80, S * 1.08), hi, lo)
        return -0.16, 0.10, (cx - S * 0.22, cy - S * 0.02, S * 0.44, S * 0.36)
    if form == "tall":
        _grad_body(art, (cx - S * 0.32, cy - S * 0.62, S * 0.64, S * 1.24), hi, lo)
        return -0.22, 0.04, (cx - S * 0.20, cy - S * 0.04, S * 0.40, S * 0.42)
    if form == "squat":
        _grad_body(art, (cx - S * 0.58, cy - S * 0.22, S * 1.16, S * 0.66), hi, lo)
        return -0.02, 0.16, (cx - S * 0.30, cy + S * 0.08, S * 0.60, S * 0.30)
    if form == "teardrop":
        _circle(art, body, (cx, cy + S * 0.14), S * 0.42)
        _poly(art, body, [(cx - S * 0.30, cy + S * 0.16), (cx, cy - S * 0.58), (cx + S * 0.30, cy + S * 0.16)])
        _ellipse(art, hl, (cx - S * 0.24, cy - S * 0.06, S * 0.30, S * 0.34))
        return -0.02, 0.22, (cx - S * 0.24, cy + S * 0.10, S * 0.48, S * 0.30)
    if form == "pear":
        _circle(art, body, (cx, cy + S * 0.22), S * 0.42)
        _ellipse(art, body, (cx - S * 0.27, cy - S * 0.34, S * 0.54, S * 0.70))
        _ellipse(art, hl, (cx - S * 0.18, cy - S * 0.28, S * 0.24, S * 0.28))
        return -0.18, 0.18, (cx - S * 0.22, cy + S * 0.12, S * 0.44, S * 0.28)
    if form == "lump":
        for dx, dy, r in ((0.0, 0.06, 0.42), (-0.32, 0.18, 0.22), (0.32, 0.16, 0.24),
                          (-0.16, -0.30, 0.24), (0.20, -0.26, 0.22)):
            _circle(art, body, (cx + dx * S, cy + dy * S), S * r)
        _ellipse(art, hl, (cx - S * 0.26, cy - S * 0.16, S * 0.32, S * 0.28))
        return -0.06, 0.18, (cx - S * 0.26, cy + S * 0.08, S * 0.52, S * 0.30)
    if form == "gem":
        _poly(art, body, [(cx, cy - S * 0.58), (cx + S * 0.46, cy - S * 0.06), (cx + S * 0.30, cy + S * 0.50),
                          (cx - S * 0.30, cy + S * 0.50), (cx - S * 0.46, cy - S * 0.06)])
        _poly(art, hl, [(cx, cy - S * 0.50), (cx - S * 0.34, cy - S * 0.02), (cx - S * 0.10, cy - S * 0.02)])
        return -0.06, 0.18, None
    # round (default)
    _grad_body(art, (cx - S * 0.46, cy - S * 0.46, S * 0.92, S * 0.92), hi, lo)
    return -0.08, 0.12, (cx - S * 0.24, cy, S * 0.48, S * 0.34)


def _d_blob(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    form = _BLOB_FORM.get(_RENDER_SID, "round")
    _feet(art, cx, cy, S, lo, n=2, spread=0.22)
    ey, my, belly_rect = _blob_body(art, cx, cy, S, form, body, accent, hi, lo)
    if belly_rect:
        _ellipse(art, _lighten(belly, 0.05), belly_rect)
    for sgn in (-1, 1):
        _circle(art, _mix(accent, (255, 140, 150), 0.5),
                (cx + sgn * S * 0.26, cy + (ey + 0.14) * S), S * 0.055)
    _eyes(art, cx, cy + ey * S, S, face, r=S * 0.12)
    _mouth(art, cx, cy + my * S, S)
    _element_motif(art, el, cx, cy, S, face, accent)


def _d_quad(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    L, H, hr = _QUAD_FORM.get(_RENDER_SID, (1.04, 0.60, 0.27))
    for lx in (-0.34, -0.12, 0.12, 0.34):
        _ellipse(art, lo, (cx + lx * S * L - S * 0.06, cy + S * 0.16, S * 0.16, S * 0.32))
    # tail
    for i, t in enumerate((0.0, 0.5, 1.0)):
        _circle(art, _mix(body, accent, t), (cx - face * (S * L * 0.48 + t * S * 0.22),
                cy - S * 0.05 - t * S * 0.22), S * (0.16 - t * 0.06))
    _grad_body(art, (cx - S * L * 0.5, cy - S * H * 0.47, S * L, S * H), hi, lo)
    _ellipse(art, _lighten(belly, 0.05), (cx - S * 0.34, cy + S * 0.04, S * 0.5, S * 0.22))
    hx = cx + face * S * L * 0.42
    _circle(art, _mix(hi, body, 0.4), (hx, cy - S * 0.16), S * hr)
    # snout
    _ellipse(art, _lighten(belly, 0.05), (hx + face * S * 0.08, cy - S * 0.12, S * 0.26, S * 0.18))
    _eyes(art, hx + face * S * 0.05, cy - S * 0.2, S, face, r=S * 0.08)
    _element_motif(art, el, hx, cy + S * 0.02, S * 0.9, face, accent)


def _d_serpent(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    n = 7
    for i in range(n):
        t = i / (n - 1)
        x = cx - face * (S * 0.46) + face * S * 0.92 * t
        y = cy + math.sin(t * math.pi * 1.6) * S * 0.26 + S * 0.1
        r = S * (0.28 - 0.14 * t)
        seg = _mix(lo, hi, 0.5 + 0.5 * math.sin(t * 6))
        _circle(art, seg, (x, y), r)
        _circle(art, _lighten(seg, 0.18), (x - r * 0.25, y - r * 0.3), r * 0.5)
        if el == "Tide" and i % 2 == 0 and i < n - 1:
            _poly(art, _lighten(accent, 0.1), [(x - S * 0.1, y - r), (x, y - r - S * 0.16),
                                               (x + S * 0.1, y - r)])
    hx = cx + face * S * 0.48
    hy = cy + math.sin(1 * math.pi * 1.6) * S * 0.26 + S * 0.1
    _circle(art, _mix(hi, body, 0.4), (hx, hy - S * 0.12), S * 0.22)
    _eyes(art, hx + face * S * 0.03, hy - S * 0.16, S, face, r=S * 0.075)
    _element_motif(art, el, hx, hy, S * 0.8, face, accent)


def _d_bird(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    _ellipse(art, lo, (cx - S * 0.05, cy + S * 0.3, S * 0.04, S * 0.16))  # legs
    _ellipse(art, lo, (cx + S * 0.06, cy + S * 0.3, S * 0.04, S * 0.16))
    # tail feathers
    for k, dy in enumerate((-0.12, 0.0, 0.12)):
        _poly(art, _mix(accent, body, 0.3),
              [(cx - face * S * 0.28, cy + dy * S), (cx - face * S * 0.66, cy + dy * S - S * 0.06),
               (cx - face * S * 0.66, cy + dy * S + S * 0.06)])
    _grad_body(art, (cx - S * 0.34, cy - S * 0.3, S * 0.68, S * 0.64), hi, lo)
    _ellipse(art, _lighten(belly, 0.06), (cx - S * 0.16, cy + S * 0.0, S * 0.3, S * 0.3))
    # wing (layered)
    for k, sc in enumerate((0.46, 0.32, 0.18)):
        _poly(art, _mix(accent, hi, k * 0.3),
              [(cx + face * S * 0.04, cy - S * 0.12), (cx - face * S * sc, cy + S * 0.02),
               (cx + face * S * 0.04, cy + S * 0.28)])
    hx = cx + face * S * 0.2
    _circle(art, _mix(hi, body, 0.4), (hx, cy - S * 0.34), S * 0.19)
    _poly(art, C.GOLD, [(hx + face * S * 0.14, cy - S * 0.36), (hx + face * S * 0.4, cy - S * 0.31),
                        (hx + face * S * 0.14, cy - S * 0.27)])
    _eyes(art, hx + face * S * 0.03, cy - S * 0.36, S, face, r=S * 0.06)
    _element_motif(art, el, hx, cy - S * 0.2, S * 0.8, face, accent)


def _d_rock(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    # stubby arms
    _ellipse(art, lo, (cx - S * 0.62, cy - S * 0.02, S * 0.22, S * 0.3))
    _ellipse(art, lo, (cx + S * 0.4, cy - S * 0.02, S * 0.22, S * 0.3))
    pts = [(cx - S * 0.46, cy + S * 0.34), (cx - S * 0.5, cy - S * 0.1),
           (cx - S * 0.2, cy - S * 0.44), (cx + S * 0.16, cy - S * 0.46),
           (cx + S * 0.5, cy - S * 0.12), (cx + S * 0.48, cy + S * 0.34)]
    _poly(art, body, pts)
    # facets
    _poly(art, hi, [(cx - S * 0.2, cy - S * 0.44), (cx + S * 0.16, cy - S * 0.46),
                    (cx + S * 0.02, cy - S * 0.04), (cx - S * 0.16, cy - S * 0.06)])
    _poly(art, lo, [(cx + S * 0.16, cy - S * 0.46), (cx + S * 0.5, cy - S * 0.12),
                    (cx + S * 0.3, cy + S * 0.1), (cx + S * 0.02, cy - S * 0.04)])
    pygame.draw.line(art, _darken(dark, 0.1), (int(cx - S * 0.16), int(cy - S * 0.06)),
                     (int(cx + S * 0.0), int(cy + S * 0.34)), max(2, int(S * 0.04)))
    # crystal shards
    for dx in (-0.2, 0.06, 0.28):
        _poly(art, _lighten(accent, 0.2), [(cx + dx * S, cy - S * 0.44),
              (cx + dx * S - S * 0.07, cy - S * 0.24), (cx + dx * S + S * 0.07, cy - S * 0.24)])
    _eyes(art, cx, cy - S * 0.02, S, face, r=S * 0.09,
          glow=_lighten(C.ELEMENT_COLORS.get(el, accent), 0.1))


def _d_wisp(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    # soft outer glow (kept inside art, will not be outlined since semi-transparent)
    glow = pygame.Surface((int(S * 2.0), int(S * 2.0)), pygame.SRCALPHA)
    for rr, a in ((0.95, 40), (0.7, 60), (0.5, 90)):
        _circle(glow, (*_lighten(accent, 0.2), a), (S, S), S * rr)
    art.blit(glow, (int(cx - S), int(cy - S)))
    # trailing wisps
    for k, t in enumerate((0.0, 0.4, 0.8)):
        _poly(art, _mix(accent, body, 0.3),
              [(cx, cy + S * 0.16 + t * S * 0.1),
               (cx - face * (S * 0.3 + t * S * 0.18), cy + S * 0.5 + t * S * 0.1),
               (cx - face * (S * 0.05 + t * S * 0.1), cy + S * 0.46 + t * S * 0.1)])
    _grad_body(art, (cx - S * 0.36, cy - S * 0.4, S * 0.72, S * 0.72), _lighten(hi, 0.1), lo)
    _circle(art, _lighten(hi, 0.3), (cx - S * 0.12, cy - S * 0.18), S * 0.12)
    _eyes(art, cx, cy - S * 0.06, S, face, r=S * 0.1,
          glow=_lighten(C.ELEMENT_COLORS.get(el, accent), 0.1))
    _element_motif(art, el, cx, cy, S, face, accent)


def _d_fish(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    # tail fin
    _poly(art, _mix(accent, body, 0.4),
          [(cx - face * S * 0.36, cy), (cx - face * S * 0.74, cy - S * 0.3),
           (cx - face * S * 0.66, cy), (cx - face * S * 0.74, cy + S * 0.3)])
    _grad_body(art, (cx - S * 0.44, cy - S * 0.32, S * 0.9, S * 0.64), hi, lo)
    _ellipse(art, _lighten(belly, 0.05), (cx - S * 0.18, cy + S * 0.04, S * 0.48, S * 0.2))
    # dorsal + pelvic fins
    _poly(art, _mix(accent, hi, 0.3),
          [(cx - S * 0.06, cy - S * 0.3), (cx + S * 0.14, cy - S * 0.58), (cx + S * 0.22, cy - S * 0.28)])
    _poly(art, _mix(accent, lo, 0.3),
          [(cx + S * 0.0, cy + S * 0.26), (cx + S * 0.16, cy + S * 0.48), (cx + S * 0.24, cy + S * 0.26)])
    # gill curve
    hx = cx + face * S * 0.24
    pygame.draw.arc(art, _darken(body, 0.2),
                    pygame.Rect(int(hx - face * S * 0.06 - S * 0.12), int(cy - S * 0.2),
                                int(S * 0.24), int(S * 0.4)), -1.0, 1.0, max(2, int(S * 0.05)))
    # single eye (side view)
    er = S * 0.12
    _circle(art, (250, 250, 255), (hx + face * S * 0.06, cy - S * 0.05), er)
    _circle(art, (30, 30, 42), (hx + face * S * 0.1, cy - S * 0.05), er * 0.55)
    _circle(art, (255, 255, 255), (hx + face * S * 0.07, cy - S * 0.12), max(1, er * 0.28))
    _element_motif(art, el, cx, cy, S * 0.8, face, accent)


def _d_bug(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    ab = cx - face * S * 0.24
    th = cx + face * S * 0.06
    hd = cx + face * S * 0.36
    # legs (3 pairs)
    for lx in (-0.18, 0.0, 0.18):
        for sgn in (-1, 1):
            pygame.draw.line(art, _darken(dark, 0.0) if dark else lo,
                             (int(cx + lx * S), int(cy + S * 0.14)),
                             (int(cx + lx * S + sgn * S * 0.16), int(cy + S * 0.44)),
                             max(2, int(S * 0.05)))
    # abdomen + thorax
    _grad_body(art, (ab - S * 0.27, cy - S * 0.25, S * 0.54, S * 0.5), hi, lo)
    # segment lines on abdomen
    for k in (-0.1, 0.04, 0.18):
        pygame.draw.arc(art, _darken(body, 0.2),
                        pygame.Rect(int(ab - S * 0.22), int(cy - S * 0.22 + k * S),
                                    int(S * 0.44), int(S * 0.4)), 3.6, 5.8, 1)
    _grad_body(art, (th - S * 0.2, cy - S * 0.23, S * 0.4, S * 0.44), _lighten(hi, 0.05), lo)
    # translucent wing
    wing = pygame.Surface((int(S * 1.0), int(S * 0.7)), pygame.SRCALPHA)
    pygame.draw.ellipse(wing, (*_lighten(accent, 0.5), 110), (0, 0, int(S * 0.9), int(S * 0.5)))
    pygame.draw.ellipse(wing, (*_lighten(accent, 0.2), 150), (0, 0, int(S * 0.9), int(S * 0.5)), 1)
    art.blit(wing, (int(th - face * S * 0.5 if face > 0 else th - S * 0.4), int(cy - S * 0.34)))
    # head + antennae
    _circle(art, _mix(hi, body, 0.4), (hd, cy - S * 0.04), S * 0.17)
    for sgn in (-1, 1):
        ax, ay = hd + face * S * 0.16, cy - S * 0.36 + sgn * S * 0.06
        pygame.draw.line(art, dark if dark else lo, (int(hd), int(cy - S * 0.16)),
                         (int(ax), int(ay)), max(2, int(S * 0.045)))
        _circle(art, _lighten(accent, 0.1), (ax, ay), S * 0.045)
    _eyes(art, hd, cy - S * 0.05, S, face, r=S * 0.07)
    _element_motif(art, el, hd, cy, S * 0.78, face, accent)


def _d_hollow(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, el):
    """The Hollow Guardian (Nullith) - a looming corrupted boss form: hooded
    spectral mass, tattered lower edge, a cracked glowing core, hollow eyes,
    floating crystal shards, and crackling Bolt static. Drawn larger than a
    normal creature so it reads as a boss."""
    eerie = (206, 234, 255)
    spark = (245, 238, 150)

    # corrupted aura
    glow = pygame.Surface((int(S * 2.3), int(S * 2.3)), pygame.SRCALPHA)
    for rr, a in ((1.02, 34), (0.80, 52), (0.58, 76)):
        _circle(glow, (*_lighten(accent, 0.15), a), (S * 1.15, S * 1.15), S * rr)
    art.blit(glow, (int(cx - S * 1.15), int(cy - S * 1.15)))

    # floating crystal shards (corrupted Spring crystals)
    shard = _lighten(accent, 0.25)
    shard_dk = _darken(accent, 0.32)
    for sx, sy, ss in ((-0.95, -0.28, 0.20), (0.98, -0.08, 0.22),
                       (-0.80, 0.48, 0.16), (0.86, 0.50, 0.17)):
        bx, by = cx + sx * S, cy + sy * S
        h = ss * S
        pts = [(bx, by - h), (bx + h * 0.5, by), (bx, by + h * 0.7), (bx - h * 0.5, by)]
        _poly(art, shard_dk, [(p[0] + 1, p[1] + 1) for p in pts])
        _poly(art, shard, pts)
        _poly(art, _lighten(shard, 0.3),
              [(bx, by - h), (bx + h * 0.22, by - h * 0.2), (bx, by), (bx - h * 0.18, by - h * 0.2)])

    # main hooded body mass
    _grad_body(art, (cx - S * 0.62, cy - S * 0.74, S * 1.24, S * 1.12), _lighten(hi, 0.05), lo)
    # raised hood horns
    _poly(art, lo, [(cx - S * 0.5, cy - S * 0.42), (cx - S * 0.64, cy - S * 0.96),
                    (cx - S * 0.26, cy - S * 0.6)])
    _poly(art, lo, [(cx + S * 0.5, cy - S * 0.42), (cx + S * 0.64, cy - S * 0.96),
                    (cx + S * 0.26, cy - S * 0.6)])
    # tattered spectral lower edge
    tat_y = cy + S * 0.34
    for i, tx in enumerate((-0.52, -0.30, -0.08, 0.14, 0.36)):
        depth = S * (0.52 if i % 2 == 0 else 0.36)
        _poly(art, _mix(body, lo, 0.5),
              [(cx + tx * S, tat_y), (cx + (tx + 0.12) * S, tat_y),
               (cx + (tx + 0.06) * S, tat_y + depth)])

    # recessed hollow face
    face_y = cy - S * 0.16
    _ellipse(art, _darken(dark if dark else lo, 0.1),
             (cx - S * 0.34, face_y - S * 0.22, S * 0.68, S * 0.54))
    # jagged brow / mask
    _poly(art, _darken(body, 0.28),
          [(cx - S * 0.36, face_y - S * 0.14), (cx + S * 0.36, face_y - S * 0.14),
           (cx + S * 0.27, face_y), (cx + S * 0.1, face_y - S * 0.1),
           (cx - S * 0.1, face_y - S * 0.1), (cx - S * 0.27, face_y)])

    # glowing hollow eyes - sharp, angry slits
    for sgn in (-1, 1):
        ex, ey = cx + sgn * S * 0.18, face_y + S * 0.03
        g = pygame.Surface((int(S * 0.4), int(S * 0.4)), pygame.SRCALPHA)
        _circle(g, (*eerie, 115), (S * 0.2, S * 0.2), S * 0.13)
        art.blit(g, (int(ex - S * 0.2), int(ey - S * 0.2)))
        _poly(art, eerie,
              [(ex - sgn * S * 0.15, ey - S * 0.08), (ex + sgn * S * 0.12, ey + S * 0.03),
               (ex + sgn * S * 0.02, ey + S * 0.07), (ex - sgn * S * 0.15, ey - S * 0.02)])
        _poly(art, (255, 255, 255),
              [(ex - sgn * S * 0.12, ey - S * 0.055), (ex + sgn * S * 0.06, ey + S * 0.015),
               (ex - sgn * S * 0.03, ey + S * 0.01)])
        _circle(art, (255, 255, 255), (ex - sgn * S * 0.05, ey - S * 0.02), max(1, S * 0.022))

    # central cracked core (the curdled bond)
    core_y = cy + S * 0.2
    _circle(art, _darken(accent, 0.42), (cx, core_y), S * 0.21)
    for ang in (20, 95, 165, 235, 305):
        a = math.radians(ang)
        pygame.draw.line(art, _darken(accent, 0.45), (int(cx), int(core_y)),
                         (int(cx + math.cos(a) * S * 0.42), int(core_y + math.sin(a) * S * 0.42)),
                         max(1, int(S * 0.025)))
    _poly(art, _lighten(accent, 0.1),
          [(cx, core_y - S * 0.18), (cx + S * 0.14, core_y), (cx, core_y + S * 0.18),
           (cx - S * 0.14, core_y)])
    _poly(art, _lighten(eerie, 0.05),
          [(cx, core_y - S * 0.1), (cx + S * 0.06, core_y), (cx, core_y + S * 0.1),
           (cx - S * 0.06, core_y)])

    # crackling Bolt static
    for bx, by in ((-0.5, -0.18), (0.54, 0.06)):
        _bolt(art, cx + bx * S, cy + by * S, S * 0.22, col=spark)


_SHAPE_FN = {"blob": _d_blob, "quad": _d_quad, "serpent": _d_serpent,
             "bird": _d_bird, "rock": _d_rock, "wisp": _d_wisp,
             "fish": _d_fish, "bug": _d_bug, "hollow": _d_hollow}

# Where each shape's head-top sits, as (x-magnitude*face, y-offset, head-radius)
# in S units from the art centre, so a crown can be planted on the right spot.
_SHAPE_HEAD = {
    "blob": (0.00, -0.40, 0.30), "quad": (0.44, -0.34, 0.24),
    "serpent": (0.48, -0.34, 0.20), "bird": (0.20, -0.46, 0.17),
    "rock": (0.02, -0.46, 0.26), "wisp": (0.00, -0.36, 0.26),
    "fish": (0.10, -0.36, 0.20), "bug": (0.36, -0.22, 0.16),
}

# Per-species (crown, body-pattern). Each species gets a distinct combination so
# creatures that share a base shape still read as individuals. Real PNG art (the
# #27 pipeline) overrides all of this when present. Nullith (hollow) is bespoke.
_CREATURE_FEAT = {
    # blob (8) - the most-reused shape, so every crown here is different
    "cindle": ("horns_pair", "none"), "sprigit": ("leaf", "none"),
    "driblet": ("ears_drop", "speckle"), "thornkin": ("spikes", "stripes"),
    "tunneler": ("horn_one", "patch"), "puffcap": ("cap", "spots"),
    "saltoad": ("ears_round", "speckle"), "voltkit": ("ears_tall", "none"),
    # quad (4)
    "pyrachs": ("spikes", "stripes"), "floravine": ("leaf", "none"),
    "voltagon": ("horns_pair", "vee"), "craghorn": ("horns_curl", "patch"),
    # serpent (3)
    "tidewyrm": ("frill", "none"), "coralisk": ("spikes", "spots"),
    "duneworm": ("none", "stripes"),
    # rock (3)
    "magmaw": ("spikes", "none"), "pebblit": ("none", "spots"),
    "boulderon": ("horns_pair", "none"),
    # wisp (3)
    "sparrk": ("spikes", "none"), "zephlit": ("tuft", "none"),
    "glimmer": ("halo", "speckle"),
    # bird (3)
    "galecrest": ("crest", "none"), "plumage": ("plume", "spots"),
    "cinderbat": ("ears_tall", "none"),
    # bug (3)
    "mawbug": ("horn_one", "stripes"), "mantiscar": ("spikes", "none"),
    "breezel": ("plume", "none"),
    # fish (2)
    "finnow": ("frill", "stripes"), "marlance": ("crest", "none"),
}


def _crown(art, hx, hy, S, face, name, body, accent, dark, hi, lo):
    """Per-species head feature, base around (hx, hy), growing upward. Drawn into
    the art surface before outlining so it shares the creature's ink line."""
    dk = _darken(body, 0.20)
    inr = _mix(accent, body, 0.45)
    ac = _lighten(accent, 0.12)
    bone = _lighten(_mix(body, (216, 206, 184), 0.7), 0.12)
    bone_lo = _darken(bone, 0.18)

    if name == "ears_tall":
        for sgn in (-1, 1):
            bx = hx + sgn * S * 0.17
            _poly(art, dk, [(bx - S * 0.08, hy + S * 0.14), (bx + sgn * S * 0.05, hy - S * 0.5),
                            (bx + S * 0.09, hy + S * 0.12)])
            _poly(art, inr, [(bx - S * 0.02, hy + S * 0.08), (bx + sgn * S * 0.02, hy - S * 0.38),
                             (bx + S * 0.04, hy + S * 0.07)])
    elif name == "ears_round":
        for sgn in (-1, 1):
            _circle(art, dk, (hx + sgn * S * 0.24, hy + S * 0.04), S * 0.16)
            _circle(art, inr, (hx + sgn * S * 0.24, hy + S * 0.06), S * 0.085)
    elif name == "ears_drop":
        for sgn in (-1, 1):
            _ellipse(art, dk, (hx + sgn * S * 0.16 - S * 0.1, hy + S * 0.02, S * 0.2, S * 0.36))
            _ellipse(art, inr, (hx + sgn * S * 0.16 - S * 0.05, hy + S * 0.06, S * 0.1, S * 0.24))
    elif name == "horn_one":
        _poly(art, bone, [(hx - S * 0.09, hy + S * 0.1), (hx + face * S * 0.04, hy - S * 0.46),
                          (hx + S * 0.09, hy + S * 0.1)])
        _poly(art, bone_lo, [(hx + S * 0.01, hy + S * 0.06), (hx + face * S * 0.04, hy - S * 0.4),
                             (hx + S * 0.09, hy + S * 0.08)])
    elif name == "horns_pair":
        for sgn in (-1, 1):
            bx = hx + sgn * S * 0.16
            _poly(art, bone, [(bx - S * 0.07, hy + S * 0.08), (bx + sgn * S * 0.16, hy - S * 0.42),
                              (bx + S * 0.07, hy + S * 0.08)])
            _poly(art, bone_lo, [(bx, hy + S * 0.04), (bx + sgn * S * 0.13, hy - S * 0.36),
                                 (bx + sgn * S * 0.05, hy + S * 0.04)])
    elif name == "horns_curl":
        for sgn in (-1, 1):
            cxp = hx + sgn * S * 0.2
            pygame.draw.arc(art, bone, pygame.Rect(int(cxp - S * 0.22), int(hy - S * 0.18),
                            int(S * 0.34), int(S * 0.5)), 0.2 if sgn > 0 else 2.7,
                            3.0 if sgn > 0 else 5.5, max(3, int(S * 0.11)))
    elif name == "antlers":
        for sgn in (-1, 1):
            bx = hx + sgn * S * 0.1
            pygame.draw.line(art, bone, (int(bx), int(hy + S * 0.06)),
                             (int(bx + sgn * S * 0.22), int(hy - S * 0.4)), max(2, int(S * 0.06)))
            pygame.draw.line(art, bone, (int(bx + sgn * S * 0.12), int(hy - S * 0.16)),
                             (int(bx + sgn * S * 0.3), int(hy - S * 0.22)), max(2, int(S * 0.05)))
    elif name == "spikes":
        for k in (-0.2, 0.0, 0.2):
            h = S * (0.3 if k == 0.0 else 0.22)
            _poly(art, dk, [(hx + k * S - S * 0.07, hy + S * 0.08),
                            (hx + k * S, hy - h), (hx + k * S + S * 0.07, hy + S * 0.08)])
            _poly(art, ac, [(hx + k * S - S * 0.03, hy + S * 0.05),
                            (hx + k * S, hy - h * 0.7), (hx + k * S + S * 0.03, hy + S * 0.05)])
    elif name == "crest":
        for k, h in ((-0.16, 0.22), (0.0, 0.42), (0.16, 0.26)):
            _poly(art, ac, [(hx + k * S - S * 0.08, hy + S * 0.1),
                            (hx + k * S + face * S * 0.04, hy - S * h),
                            (hx + k * S + S * 0.08, hy + S * 0.1)])
    elif name == "frill":
        for sgn in (-1, 1):
            for j, sp in enumerate((0.0, 0.16, 0.32)):
                _poly(art, _mix(ac, lo, j * 0.25),
                      [(hx, hy + S * 0.12), (hx + sgn * (S * 0.2 + j * S * 0.14), hy - S * 0.18 + j * S * 0.06),
                       (hx + sgn * (S * 0.12 + j * S * 0.12), hy + S * 0.16)])
    elif name == "plume":
        pygame.draw.arc(art, ac, pygame.Rect(int(hx - S * 0.1), int(hy - S * 0.5),
                        int(S * 0.5 * (1 if face > 0 else -1) or S * 0.5), int(S * 0.6)),
                        0.2, 2.4, max(3, int(S * 0.12)))
        _poly(art, _lighten(ac, 0.15),
              [(hx, hy + S * 0.06), (hx + face * S * 0.06, hy - S * 0.46),
               (hx + face * S * 0.2, hy - S * 0.3)])
    elif name == "tuft":
        for k in (-0.1, 0.04, 0.16):
            pygame.draw.line(art, _mix(hi, accent, 0.4), (int(hx + k * S), int(hy + S * 0.12)),
                             (int(hx + k * S + face * S * 0.08), int(hy - S * 0.34)), max(2, int(S * 0.05)))
    elif name == "halo":
        rg = pygame.Surface((int(S * 0.9), int(S * 0.5)), pygame.SRCALPHA)
        pygame.draw.ellipse(rg, (*ac, 220), (0, 0, int(S * 0.86), int(S * 0.3)), max(2, int(S * 0.05)))
        art.blit(rg, (int(hx - S * 0.43), int(hy - S * 0.36)))
    elif name == "cap":
        _ellipse(art, _darken(accent, 0.1), (hx - S * 0.34, hy - S * 0.18, S * 0.68, S * 0.5))
        _ellipse(art, ac, (hx - S * 0.34, hy - S * 0.22, S * 0.68, S * 0.4))
        for sx in (-0.16, 0.06, 0.2):
            _circle(art, (245, 245, 235), (hx + sx * S, hy - S * 0.04), S * 0.05)
    elif name == "leaf":
        _leaf(art, hx - S * 0.03, hy + S * 0.06, S * 0.4, 1, _lighten(accent, 0.1))
        _leaf(art, hx + S * 0.04, hy + S * 0.06, S * 0.34, -1, accent)


def _body_pattern(art, cx, cy, S, name, col, accent):
    """A light surface pattern kept within the central body mass."""
    if name == "spots":
        for dx, dy, r in ((-0.2, 0.06, 0.09), (0.16, -0.04, 0.07), (0.02, 0.2, 0.08),
                          (0.24, 0.16, 0.06)):
            _circle(art, col, (cx + dx * S, cy + dy * S), S * r)
    elif name == "speckle":
        for dx, dy in ((-0.22, 0.0), (-0.05, 0.12), (0.12, 0.04), (0.22, 0.18),
                       (0.0, 0.24), (-0.16, 0.2)):
            _circle(art, col, (cx + dx * S, cy + dy * S), S * 0.035)
    elif name == "stripes":
        for k in (-0.22, -0.06, 0.1, 0.26):
            pygame.draw.line(art, col, (int(cx + k * S), int(cy - S * 0.16)),
                             (int(cx + k * S - S * 0.1), int(cy + S * 0.24)), max(2, int(S * 0.05)))
    elif name == "patch":
        _ellipse(art, col, (cx - S * 0.04, cy - S * 0.26, S * 0.4, S * 0.3))
    elif name == "vee":
        for off in (0.0, 0.1):
            pygame.draw.line(art, col, (int(cx - S * 0.2), int(cy - S * 0.06 + off * S)),
                             (int(cx), int(cy + S * 0.1 + off * S)), max(2, int(S * 0.045)))
            pygame.draw.line(art, col, (int(cx), int(cy + S * 0.1 + off * S)),
                             (int(cx + S * 0.2), int(cy - S * 0.06 + off * S)), max(2, int(S * 0.045)))


_creature_png_cache = {}   # species_id -> Surface | None (None = looked up, absent)


def _load_creature_png(species_id):
    """Load assets/sprites/creatures/<species_id>.png if present, else None.
    Cached per species; tolerant of having no display yet (skips convert)."""
    if species_id in _creature_png_cache:
        return _creature_png_cache[species_id]
    surf = None
    p = assets.path("sprites", "creatures", species_id + ".png")
    if os.path.isfile(p):
        try:
            img = pygame.image.load(p)
            try:
                img = img.convert_alpha()
            except Exception:
                pass   # no display mode set yet; the raw surface still blits fine
            surf = img
        except Exception:
            surf = None
    _creature_png_cache[species_id] = surf
    return surf


def _fit_png_creature(img, B, face):
    """Scale a sprite PNG to fit a BxB canvas (preserving aspect, nearest-neighbour
    so pixel art stays crisp), centred, flipped to match facing."""
    canvas = pygame.Surface((B, B), pygame.SRCALPHA)
    iw, ih = img.get_width(), img.get_height()
    scale = min(B / iw, B / ih) if iw and ih else 1.0
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    scaled = pygame.transform.scale(img, (nw, nh))
    if face < 0:
        scaled = pygame.transform.flip(scaled, True, False)
    canvas.blit(scaled, ((B - nw) // 2, (B - nh) // 2))
    return canvas


def _render_creature(species_id, S, face):
    B = int(S * 2.2)
    png = _load_creature_png(species_id)
    if png is not None:
        # dedicated sprite art drops in here; procedural path below is the fallback
        return _fit_png_creature(png, B, face), B, B // 2
    sp = SPECIES[species_id]
    body, accent, dark = sp["pal"]
    hi = _lighten(body, 0.42)
    lo = _darken(body, 0.32)
    belly = _lighten(accent, 0.2)
    art = pygame.Surface((B, B), pygame.SRCALPHA)
    cx, cy = B // 2, int(B * 0.5)
    global _RENDER_SID
    _RENDER_SID = species_id     # lets shape fns vary the body per species
    _SHAPE_FN.get(sp["shape"], _d_blob)(art, cx, cy, S, face, body, accent, dark, hi, lo, belly, sp["type"])
    # per-species crown + body pattern, layered on the (now per-species) body so
    # creatures sharing a base shape still read as individuals (PNG art overrides)
    feat = _CREATURE_FEAT.get(species_id)
    if feat:
        crown, patt = feat
        anchor = _SHAPE_HEAD.get(sp["shape"])
        if crown and crown != "none" and anchor:
            xmag, ytop, hr = anchor
            if sp["shape"] == "blob":
                ytop = _BLOB_HEADTOP.get(_BLOB_FORM.get(species_id, "round"), ytop)
            _crown(art, cx + face * xmag * S, cy + ytop * S, S, face, crown,
                   body, accent, dark, hi, lo)
        if patt and patt != "none":
            _body_pattern(art, cx, cy, S, patt, _darken(body, 0.24), accent)
    th = max(2, int(round(S * 0.05)))
    out = _outline(art, _darken(dark, 0.15) if dark else (22, 22, 30), th)
    return out, B, cy


def draw_creature(surf, species_id, cx, cy, S, face=1, bob=0):
    """Draw species centred at (cx, cy). S ~ body height in px.
    face = 1 faces right, -1 faces left. bob shifts vertically (animation)."""
    key = (species_id, int(S), 1 if face >= 0 else -1)
    if key not in _creature_cache:
        _creature_cache[key] = _render_creature(*key)
    spr, B, cyc = _creature_cache[key]
    # ground shadow
    sh = pygame.Surface((B, max(6, B // 4)), pygame.SRCALPHA)
    _ellipse(sh, (0, 0, 0, 70), (B * 0.22, 0, B * 0.56, max(6, B // 4)))
    surf.blit(sh, (int(cx - B / 2), int(cy + S * 0.4)))
    surf.blit(spr, (int(cx - B / 2), int(cy + bob - cyc)))


# ---------------------------------------------------------------------------
# Overworld characters (baked + cached)
# ---------------------------------------------------------------------------
_char_cache = {}


def _accessory(art, code, facing, hcx, hcy, hr, tx, ty, tw, th, cx, cy, s, shirt, trim):
    """Draw a recognizable prop on top of the base figure (before outlining)."""
    if not code:
        return
    f = 1 if facing == "right" else (-1 if facing == "left" else 0)
    side = f != 0

    def rr(col, x, y, w, h, r=2):
        pygame.draw.rect(art, col, (int(round(x)), int(round(y)),
                         int(round(max(1, w))), int(round(max(1, h)))), border_radius=int(r))

    def ell(col, x, y, w, h):
        _ellipse(art, col, (int(round(x)), int(round(y)),
                 int(round(max(1, w))), int(round(max(1, h)))))

    def line(col, x1, y1, x2, y2, w=2):
        pygame.draw.line(art, col, (int(round(x1)), int(round(y1))),
                         (int(round(x2)), int(round(y2))), w)

    def brim_hat(crown, brim, band):
        if facing == "up":
            ell(brim, hcx - hr * 1.3, hcy - hr * 0.35, hr * 2.6, hr * 0.7)
            ell(crown, hcx - hr * 0.85, hcy - hr * 1.25, hr * 1.7, hr * 1.25)
        elif side:
            ell(brim, hcx - hr * 1.0 + f * hr * 0.45, hcy - hr * 0.45, hr * 2.3, hr * 0.66)
            ell(crown, hcx - hr * 0.78, hcy - hr * 1.3, hr * 1.56, hr * 1.25)
            rr(band, hcx - hr * 0.72, hcy - hr * 0.55, hr * 1.44, hr * 0.26, 2)
        else:
            ell(brim, hcx - hr * 1.35, hcy - hr * 0.5, hr * 2.7, hr * 0.78)
            ell(crown, hcx - hr * 0.82, hcy - hr * 1.32, hr * 1.64, hr * 1.26)
            rr(band, hcx - hr * 0.75, hcy - hr * 0.62, hr * 1.5, hr * 0.26, 2)

    def cap(crown, bill):
        if facing == "up":
            ell(crown, hcx - hr * 0.85, hcy - hr * 1.2, hr * 1.7, hr * 1.18)
        elif side:
            ell(crown, hcx - hr * 0.8, hcy - hr * 1.25, hr * 1.6, hr * 1.2)
            pygame.draw.polygon(art, bill, [(hcx + f * hr * 0.35, hcy - hr * 0.5),
                                            (hcx + f * hr * 1.4, hcy - hr * 0.32),
                                            (hcx + f * hr * 0.35, hcy - hr * 0.16)])
        else:
            ell(crown, hcx - hr * 0.85, hcy - hr * 1.28, hr * 1.7, hr * 1.2)
            ell(bill, hcx - hr * 0.7, hcy - hr * 0.5, hr * 1.4, hr * 0.5)

    def nurse_cap():
        white, red = (242, 242, 248), (216, 72, 72)
        if facing == "up":
            ell(white, hcx - hr * 0.7, hcy - hr * 1.05, hr * 1.4, hr * 0.7)
        elif side:
            ell(white, hcx - hr * 0.72, hcy - hr * 1.08, hr * 1.34, hr * 0.66)
        else:
            pygame.draw.polygon(art, white, [(hcx - hr * 0.72, hcy - hr * 0.5),
                                             (hcx - hr * 0.5, hcy - hr * 1.05),
                                             (hcx + hr * 0.5, hcy - hr * 1.05),
                                             (hcx + hr * 0.72, hcy - hr * 0.5)])
            rr(red, hcx - hr * 0.07, hcy - hr * 0.96, hr * 0.14, hr * 0.36, 1)
            rr(red, hcx - hr * 0.22, hcy - hr * 0.82, hr * 0.44, hr * 0.12, 1)

    def glasses():
        col = (44, 42, 54)
        if facing == "up":
            return
        if side:
            pygame.draw.circle(art, col, (int(hcx + f * hr * 0.5), int(hcy + hr * 0.14)),
                               max(2, int(hr * 0.26)), 2)
        else:
            for sgn in (-1, 1):
                pygame.draw.circle(art, col, (int(hcx + sgn * hr * 0.42), int(hcy + hr * 0.18)),
                                   max(2, int(hr * 0.27)), 2)
            line(col, hcx - hr * 0.16, hcy + hr * 0.18, hcx + hr * 0.16, hcy + hr * 0.18, 2)

    def satchel():
        strapc, bagc = (78, 58, 42), (112, 82, 52)
        if facing == "up":
            line(strapc, tx + tw * 0.12, ty, tx + tw * 0.88, ty + th * 0.7, 3)
            rr(bagc, tx + tw * 0.3, ty + th * 0.35, tw * 0.4, th * 0.5, 3)
        elif side:
            line(strapc, tx + tw * 0.32, ty, tx + tw * 0.62, ty + th * 0.8, 3)
            rr(bagc, cx - f * tw * 0.52, ty + th * 0.42, tw * 0.36, th * 0.5, 3)
        else:
            line(strapc, tx + tw * 0.16, ty, tx + tw * 0.8, ty + th * 0.74, 3)
            rr(bagc, tx + tw * 0.64, ty + th * 0.4, tw * 0.42, th * 0.52, 3)

    def apron(col):
        edge = _darken(col, 0.22)
        if facing == "up":
            rr(col, tx + tw * 0.22, ty + th * 0.2, tw * 0.56, th * 0.7, 3)
        elif side:
            rr(col, tx + tw * 0.28, ty + th * 0.14, tw * 0.46, th * 0.82, 3)
        else:
            rr(col, tx + tw * 0.18, ty + th * 0.12, tw * 0.64, th * 0.86, 3)
            line(edge, tx + tw * 0.3, ty + th * 0.12, hcx - hr * 0.2, hcy + hr * 0.72, 2)
            line(edge, tx + tw * 0.7, ty + th * 0.12, hcx + hr * 0.2, hcy + hr * 0.72, 2)

    def backpack(col):
        edge = _darken(col, 0.22)
        if facing == "up":
            rr(col, tx + tw * 0.16, ty + th * 0.02, tw * 0.68, th * 0.78, 4)
        elif side:
            rr(col, cx - f * tw * 0.58, ty + th * 0.0, tw * 0.42, th * 0.74, 4)
            line(edge, cx + f * tw * 0.08, ty + th * 0.04, cx + f * tw * 0.08, ty + th * 0.72, 3)
        else:
            for sgn in (-1, 1):
                line(col, cx + sgn * tw * 0.22, ty + th * 0.02, cx + sgn * tw * 0.22, ty + th * 0.86, 3)

    def cane():
        col = (122, 88, 56)
        bx = (cx + f * tw * 0.66) if side else (tx + tw + tw * 0.06)
        rr(col, bx, cy - s * 0.14, s * 0.05, s * 0.52, 2)
        _circle(art, _lighten(col, 0.22), (bx + s * 0.025, cy - s * 0.14), s * 0.055)

    def headband(col):
        if facing == "up":
            rr(col, hcx - hr * 0.85, hcy - hr * 0.5, hr * 1.7, hr * 0.28, 2)
        else:
            yoff = hcy - hr * (0.35 if side else 0.32)
            rr(col, hcx - hr * 0.9, yoff, hr * 1.8, hr * 0.26, 2)
            if not side:
                _circle(art, _darken(col, 0.2), (hcx + hr * 0.55, yoff + hr * 0.12), hr * 0.12)

    def mantle(col):
        if facing == "up":
            pts = [(tx - tw * 0.12, ty + th * 0.05), (tx + tw * 1.12, ty + th * 0.05),
                   (tx + tw * 0.9, ty + th * 0.55), (tx + tw * 0.1, ty + th * 0.55)]
        elif side:
            pts = [(tx - tw * 0.1, ty), (tx + tw * 1.0, ty),
                   (tx + tw * 0.85, ty + th * 0.5), (tx + tw * 0.05, ty + th * 0.5)]
        else:
            pts = [(tx - tw * 0.14, ty), (tx + tw * 1.14, ty),
                   (tx + tw * 0.88, ty + th * 0.52), (tx + tw * 0.12, ty + th * 0.52)]
        pygame.draw.polygon(art, col, [(int(round(a)), int(round(b))) for a, b in pts])
        pygame.draw.polygon(art, _darken(col, 0.25),
                            [(int(round(a)), int(round(b))) for a, b in pts], 2)

    if code == "hiker":
        backpack((110, 84, 56))
        brim_hat((150, 116, 70), (120, 92, 54), (96, 72, 44))
    elif code == "ranger":
        cap((68, 118, 80), (52, 94, 62))
    elif code == "fisher":
        brim_hat((118, 150, 182), (96, 124, 152), (80, 106, 130))
    elif code == "kid":
        cap((214, 92, 92), (172, 66, 66))
    elif code == "nurse":
        apron((240, 240, 246))
        nurse_cap()
    elif code == "scholar":
        satchel()
        glasses()
    elif code == "shop":
        apron((150, 120, 72))
    elif code == "elder":
        glasses()
        cane()
    elif code == "rival":
        headband((236, 96, 96))
    elif code == "mentor":
        mantle(trim)


_char_png_cache = {}   # (key, facing) -> Surface | None


def _slug(s):
    """'Mentor Wren' -> 'mentor_wren' for sprite file names."""
    return "".join(c if c.isalnum() else "_" for c in str(s).lower()).strip("_")


def _resolve_char_png(key, facing):
    """Find the best character PNG for key+facing under assets/sprites/characters/,
    trying directional variants then a single base file, flipping for left."""
    def load(name):
        p = assets.path("sprites", "characters", name + ".png")
        if not os.path.isfile(p):
            return None
        try:
            img = pygame.image.load(p)
            try:
                img = img.convert_alpha()
            except Exception:
                pass
            return img
        except Exception:
            return None

    img = load("%s_%s" % (key, facing))
    if img:
        return img
    if facing in ("left", "right"):
        side = load("%s_side" % key)
        if side:
            return pygame.transform.flip(side, True, False) if facing == "left" else side
        other = load("%s_right" % key) if facing == "left" else load("%s_left" % key)
        if other:
            return pygame.transform.flip(other, True, False)
    base = load(key)
    if base:
        return pygame.transform.flip(base, True, False) if facing == "left" else base
    return None


def _char_png_for(key, facing):
    if not key:
        return None
    ck = (key, facing)
    if ck not in _char_png_cache:
        _char_png_cache[ck] = _resolve_char_png(key, facing)
    return _char_png_cache[ck]


def _fit_png_char(png):
    """Scale a character PNG to fit a person-sized canvas, feet at the bottom so
    it stands on its shadow. Returns (canvas, B, cyc) like _render_char."""
    s = C.TILE
    B = int(s * 1.8)
    canvas = pygame.Surface((B, B), pygame.SRCALPHA)
    iw, ih = png.get_width(), png.get_height()
    scale = min(B / iw, B / ih) if iw and ih else 1.0
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    scaled = pygame.transform.scale(png, (nw, nh))
    canvas.blit(scaled, ((B - nw) // 2, B - nh))   # bottom-centre
    return canvas, B, int(s * 1.48)


def _render_char(palette, facing, frame, key=None, role=None):
    """A GBA-overworld-style person: large expressive head with real hair, a
    shirt with sleeves + collar, pants and shoes, shaded and outlined, with a
    two-frame walk. palette = (shirt, skin, hair, trim)."""
    png = _char_png_for(key, facing) or _char_png_for(role, facing)
    if png is not None:
        # dedicated sprite (NPC-id first, then role); procedural path is fallback
        return _fit_png_char(png)
    shirt, skin, hair, trim = palette[0], palette[1], palette[2], palette[3]
    acc = palette[4] if len(palette) > 4 else None
    s = C.TILE
    B = int(s * 1.8)
    art = pygame.Surface((B, B), pygame.SRCALPHA)
    cx = B / 2.0
    cy = B * 0.46

    shirt_hi, shirt_lo = _lighten(shirt, 0.22), _darken(shirt, 0.30)
    skin_hi, skin_lo = _lighten(skin, 0.10), _darken(skin, 0.16)
    hair_hi, hair_lo = _lighten(hair, 0.24), _darken(hair, 0.32)
    pants, pants_lo = _darken(shirt, 0.58), _darken(shirt, 0.70)
    shoe = (38, 36, 48)
    line = (26, 23, 34)

    def rr(col, x, y, w, h, r=2):
        pygame.draw.rect(art, col, (int(round(x)), int(round(y)),
                                    int(round(max(1, w))), int(round(max(1, h)))),
                         border_radius=int(r))

    # walk: alternate stepping foot + a 1px body bob
    step = 0 if frame == 0 else 1
    bob = -1 if frame == 1 else 0

    hr = s * 0.235                      # head radius
    hcx, hcy = cx, cy - s * 0.26 + bob  # head center
    tw, th = s * 0.38, s * 0.37         # torso (taller than wide, rounded)
    tx, ty = cx - tw / 2, cy - s * 0.02 + bob
    legw, legh = s * 0.14, s * 0.16
    legy = ty + th - s * 0.04
    gap = s * 0.04

    # ---------------- legs + shoes ----------------
    if facing in ("left", "right"):
        f = 1 if facing == "right" else -1
        # back leg then front leg, front swings in the facing direction
        sw = (s * 0.07) * (1 if step == 0 else -1)
        rr(pants_lo, cx - legw / 2 - f * s * 0.04 - sw, legy, legw, legh, 3)
        rr(shoe, cx - legw / 2 - f * s * 0.04 - sw + (f * s * 0.02 if f > 0 else 0),
           legy + legh - s * 0.05, legw + s * 0.04, s * 0.07, 2)
        rr(pants, cx - legw / 2 + f * s * 0.05 + sw, legy, legw, legh, 3)
        rr(shoe, cx - legw / 2 + f * s * 0.05 + sw, legy + legh - s * 0.05,
           legw + s * 0.04, s * 0.07, 2)
    else:
        # two legs side by side; the stepping one reaches a touch lower
        lL = legh + (s * 0.04 if step == 0 else 0)
        lR = legh + (s * 0.04 if step == 1 else 0)
        rr(pants, cx - gap - legw, legy, legw, lL, 3)
        rr(pants, cx + gap, legy, legw, lR, 3)
        rr(shoe, cx - gap - legw - s * 0.01, legy + lL - s * 0.05, legw + s * 0.03, s * 0.07, 2)
        rr(shoe, cx + gap - s * 0.01, legy + lR - s * 0.05, legw + s * 0.03, s * 0.07, 2)

    # ---------------- torso (shirt) ----------------
    rad = max(3, int(tw * 0.45))
    rr(shirt, tx, ty, tw, th, rad)
    rr(shirt_hi, tx, ty, tw * 0.32, th, rad)              # left highlight
    rr(shirt_lo, tx + tw * 0.70, ty, tw * 0.30, th, rad)  # right shadow

    # arms / short sleeves swing opposite the legs
    asw = (s * 0.03) * (1 if step == 0 else -1)
    if facing in ("left", "right"):
        f = 1 if facing == "right" else -1
        # near arm only, in front of torso
        rr(shirt_lo, cx - s * 0.05 + f * s * 0.10, ty + s * 0.02, s * 0.11, s * 0.16, 4)
        _circle(art, skin, (cx + f * s * 0.16, ty + s * 0.19), s * 0.05)  # hand
    else:
        rr(shirt_lo, tx - s * 0.02, ty + s * 0.03 + asw, s * 0.10, s * 0.18, 4)
        rr(shirt_lo, tx + tw - s * 0.08, ty + s * 0.03 - asw, s * 0.10, s * 0.18, 4)
        _circle(art, skin, (tx + s * 0.03, ty + s * 0.20 + asw), s * 0.045)
        _circle(art, skin, (tx + tw - s * 0.03, ty + s * 0.20 - asw), s * 0.045)
        # collar
        pygame.draw.polygon(art, trim, [(cx - s * 0.08, ty), (cx + s * 0.08, ty),
                                        (cx, ty + s * 0.09)])

    # ---------------- head ----------------
    _circle(art, skin, (hcx, hcy), hr)
    _circle(art, skin_hi, (hcx - hr * 0.30, hcy - hr * 0.30), hr * 0.55)

    if facing == "down":
        # hair cap over the top, with a center fringe and sideburns
        pygame.draw.polygon(art, hair, [
            (hcx - hr * 1.02, hcy + hr * 0.12), (hcx - hr * 0.95, hcy - hr * 0.7),
            (hcx - hr * 0.4, hcy - hr * 1.05), (hcx + hr * 0.4, hcy - hr * 1.05),
            (hcx + hr * 0.95, hcy - hr * 0.7), (hcx + hr * 1.02, hcy + hr * 0.12),
            (hcx + hr * 0.66, hcy - hr * 0.05), (hcx + hr * 0.3, hcy - hr * 0.42),
            (hcx, hcy - hr * 0.18), (hcx - hr * 0.3, hcy - hr * 0.42),
            (hcx - hr * 0.66, hcy - hr * 0.05)])
        pygame.draw.polygon(art, hair_hi, [
            (hcx - hr * 0.4, hcy - hr * 1.05), (hcx + hr * 0.1, hcy - hr * 1.02),
            (hcx - hr * 0.2, hcy - hr * 0.5), (hcx - hr * 0.55, hcy - hr * 0.55)])
        _eyes(art, hcx, hcy + hr * 0.18, s * 0.52, face=0, r=hr * 0.17)
        _mouth(art, hcx, hcy + hr * 0.62, s * 0.5)
    elif facing == "up":
        # back of the head: hair fills it, with a slight parting + nape
        _circle(art, hair, (hcx, hcy - hr * 0.04), hr * 1.0)
        _circle(art, hair_hi, (hcx - hr * 0.28, hcy - hr * 0.32), hr * 0.5)
        pygame.draw.line(art, hair_lo, (int(hcx), int(hcy - hr * 0.9)),
                         (int(hcx), int(hcy + hr * 0.2)), 2)
    else:
        f = 1 if facing == "right" else -1
        # ear toward the back, hair sweeping over the crown and down the back
        _circle(art, skin_lo, (hcx - f * hr * 0.5, hcy + hr * 0.05), hr * 0.22)
        pygame.draw.polygon(art, hair, [
            (hcx - f * hr * 1.05, hcy + hr * 0.5), (hcx - f * hr * 1.02, hcy - hr * 0.7),
            (hcx - f * hr * 0.3, hcy - hr * 1.05), (hcx + f * hr * 0.7, hcy - hr * 0.85),
            (hcx + f * hr * 0.95, hcy - hr * 0.25), (hcx + f * hr * 0.5, hcy - hr * 0.4),
            (hcx - f * hr * 0.1, hcy - hr * 0.65), (hcx - f * hr * 0.55, hcy - hr * 0.5)])
        # nose + one eye on the facing side
        pygame.draw.polygon(art, skin_lo, [
            (hcx + f * hr * 0.92, hcy + hr * 0.05), (hcx + f * hr * 1.06, hcy + hr * 0.2),
            (hcx + f * hr * 0.9, hcy + hr * 0.3)])
        _circle(art, (250, 250, 255), (hcx + f * hr * 0.5, hcy + hr * 0.12), hr * 0.2)
        _circle(art, (32, 30, 42), (hcx + f * hr * 0.58, hcy + hr * 0.12), hr * 0.11)

    _accessory(art, acc, facing, hcx, hcy, hr, tx, ty, tw, th, cx, cy, s, shirt, trim)
    return _outline(art, line, 2), B, cy


def _draw_char(surf, cx, cy, palette, facing, step, key=None, role=None):
    frame = (step // 7) % 2
    ckey = (key, role, palette, facing, frame)
    if ckey not in _char_cache:
        _char_cache[ckey] = _render_char(palette, facing, frame, key, role)
    spr, B, cyc = _char_cache[ckey]
    s = C.TILE
    sh = pygame.Surface((int(s * 0.62), int(s * 0.2)), pygame.SRCALPHA)
    _ellipse(sh, (0, 0, 0, 90), (0, 0, int(s * 0.62), int(s * 0.2)))
    surf.blit(sh, (int(cx - s * 0.31), int(cy + s * 0.32)))
    surf.blit(spr, (int(cx - B / 2), int(cy - cyc)))


def draw_trainer(surf, palette, cx, cy, S, face=-1):
    """A larger battle-scale trainer, built from the baked character art so it
    stays consistent with the overworld NPC. (cx, cy) is where the feet stand."""
    facing = "left" if face < 0 else "right"
    spr, B, cyc = _render_char(palette, facing, 0)
    scale = max(1.0, (S * 2.4) / B)
    bw, bh = int(B * scale), int(B * scale)
    big = pygame.transform.scale(spr, (bw, bh))
    foot = (cyc + 0.32 * C.TILE) * scale          # figure's feet in scaled coords
    sw = int(bw * 0.42)
    sh = pygame.Surface((sw, max(6, sw // 4)), pygame.SRCALPHA)
    _ellipse(sh, (0, 0, 0, 85), (0, 0, sw, max(6, sw // 4)))
    surf.blit(sh, (int(cx - sw / 2), int(cy - max(6, sw // 4) // 2)))
    surf.blit(big, (int(cx - bw / 2), int(cy - foot)))


PLAYER_PALETTE = ((58, 104, 168), (228, 196, 160), (74, 52, 40), C.ACCENT)


def draw_player(surf, cx, cy, facing, step):
    _draw_char(surf, cx, cy, PLAYER_PALETTE, facing, step, key="player", role="player")


def draw_npc(surf, cx, cy, facing, palette, step=0, key=None, role=None):
    _draw_char(surf, cx, cy, palette, facing, step,
               key=_slug(key) if key else None,
               role=_slug(role) if role else None)


# Named NPC palettes (shirt, skin, hair, trim, accessory)
NPC_PALETTES = {
    "mentor":   ((104, 92, 156), (224, 196, 168), (214, 214, 224), C.GOLD, "mentor"),
    "shop":     ((156, 126, 74), (228, 196, 160), (46, 38, 32), (214, 184, 96), "shop"),
    "rival":    ((164, 74, 74), (228, 196, 160), (32, 32, 38), (236, 96, 96), "rival"),
    "villager": ((92, 138, 96), (228, 196, 160), (74, 52, 38), (158, 198, 158)),
    "elder":    ((116, 116, 138), (224, 200, 176), (236, 236, 240), (176, 176, 198), "elder"),
    "hiker":    ((150, 120, 70), (226, 194, 158), (60, 44, 34), (120, 150, 90), "hiker"),
    "ranger":   ((70, 120, 80), (224, 196, 168), (70, 50, 36), (150, 200, 150), "ranger"),
    "kid":      ((214, 120, 90), (232, 200, 172), (80, 56, 40), (244, 184, 120), "kid"),
    "fisher":   ((80, 110, 150), (228, 196, 160), (60, 46, 36), (150, 180, 220), "fisher"),
    "nurse":    ((220, 150, 170), (232, 204, 180), (188, 124, 144), (246, 212, 226), "nurse"),
    "scholar":  ((110, 100, 150), (224, 200, 176), (122, 112, 150), (182, 172, 212), "scholar"),
}


# ---------------------------------------------------------------------------
# Textbox
# ---------------------------------------------------------------------------
class Textbox:
    LINES_PER_PAGE = 3

    def __init__(self, text, speaker=None):
        self.speaker = speaker
        inner_w = C.SCREEN_W - 72
        lines = wrap_text(text, 22, inner_w)
        self.pages = [lines[i:i + self.LINES_PER_PAGE]
                      for i in range(0, len(lines), self.LINES_PER_PAGE)] or [[""]]
        self.page = 0
        self.shown = 0.0
        self.speed = 60.0
        self.blink = 0.0

    def _full(self):
        return "\n".join(self.pages[self.page])

    def revealed(self):
        return self.shown >= len(self._full())

    def update(self, dt):
        self.shown = min(self.shown + self.speed * dt, len(self._full()))
        self.blink += dt

    def confirm(self):
        """Returns 'reveal', 'more', or 'done'."""
        if not self.revealed():
            self.shown = len(self._full())
            return "reveal"
        if self.page < len(self.pages) - 1:
            self.page += 1
            self.shown = 0.0
            return "more"
        return "done"

    def draw(self, surf):
        h = 116
        rect = pygame.Rect(16, C.SCREEN_H - h - 12, C.SCREEN_W - 32, h)
        draw_panel(surf, rect, fill=C.NEAR_BLACK, border=C.ACCENT, width=2, radius=10)
        if self.speaker:
            tag = pygame.Rect(rect.x + 18, rect.y - 14, get_font(18).size(self.speaker)[0] + 20, 24)
            draw_panel(surf, tag, fill=C.PANEL, border=C.ACCENT, width=2, radius=8)
            draw_text(surf, self.speaker, tag.x + 10, tag.y + 4, 18, C.ACCENT)
        shown_text = self._full()[:int(self.shown)]
        y = rect.y + 16
        for line in shown_text.split("\n"):
            draw_text(surf, line, rect.x + 20, y, 22, C.WHITE)
            y += 30
        if self.revealed() and math.sin(self.blink * 6) > 0:
            tip = "next" if self.page < len(self.pages) - 1 else "ok"
            draw_text(surf, "\u25BC " + tip, rect.right - 60, rect.bottom - 26, 16, C.ACCENT)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
class MenuItem:
    def __init__(self, label, value, right=None, color=None, enabled=True, badge=None):
        self.label = label
        self.value = value
        self.right = right
        self.color = color
        self.enabled = enabled
        self.badge = badge   # optional (text, color) pill drawn before the label


class Menu:
    BOTTOM_MARGIN = 12   # keep the panel this many px clear of the screen bottom

    def __init__(self, items, x, y, width=220, visible=6, size=22, title=None):
        self.items = [it if isinstance(it, MenuItem) else MenuItem(it, it) for it in items]
        self.x, self.y = x, y
        self.width = width
        self.visible = visible
        self.size = size
        self.title = title
        self.index = 0
        self.scroll = 0
        self._home_to_enabled()
        self._clamp_to_screen()

    def _clamp_to_screen(self):
        """Pull the panel up so it never spills past the bottom of the screen.
        Call sites anchor menus at a fixed `SCREEN_H - n` offset, but the panel
        height grows with the row count/title, so a tall menu would otherwise
        clip its last rows and the scroll-hint arrow off-screen."""
        max_y = C.SCREEN_H - self.height() - self.BOTTOM_MARGIN
        if self.y > max_y:
            self.y = max(self.BOTTOM_MARGIN, max_y)

    def _home_to_enabled(self):
        for i, it in enumerate(self.items):
            if it.enabled:
                self.index = i
                return

    def move(self, direction):
        if not self.items:
            return
        step = -1 if direction == "up" else 1 if direction == "down" else 0
        if step == 0:
            return
        n = len(self.items)
        i = self.index
        for _ in range(n):
            i = (i + step) % n
            if self.items[i].enabled:
                self.index = i
                break
        # adjust scroll
        if self.index < self.scroll:
            self.scroll = self.index
        elif self.index >= self.scroll + self.visible:
            self.scroll = self.index - self.visible + 1

    def selected(self):
        if not self.items:
            return None
        return self.items[self.index].value

    def height(self):
        rows = min(len(self.items), self.visible)
        return rows * (self.size + 8) + 16 + (26 if self.title else 0)

    def draw(self, surf):
        rect = pygame.Rect(self.x, self.y, self.width, self.height())
        draw_panel(surf, rect, fill=C.PANEL, border=C.BORDER, width=2, radius=8)
        yy = rect.y + 10
        if self.title:
            draw_text(surf, self.title, rect.x + 14, yy, 18, C.ACCENT)
            yy += 26
        end = min(self.scroll + self.visible, len(self.items))
        row_h = self.size + 8
        for i in range(self.scroll, end):
            it = self.items[i]
            sel = (i == self.index)
            ry = yy + (i - self.scroll) * row_h
            if sel:
                hl = pygame.Rect(rect.x + 6, ry - 2, self.width - 12, row_h)
                pygame.draw.rect(surf, C.PANEL_HI, hl, border_radius=6)
                pygame.draw.rect(surf, C.ACCENT, hl, width=2, border_radius=6)
                ay = ry + row_h // 2
                pygame.draw.polygon(surf, C.ACCENT,
                                    [(rect.x + 13, ay - 5), (rect.x + 13, ay + 5),
                                     (rect.x + 21, ay)])
            col = it.color or (C.WHITE if it.enabled else C.DIM)
            label_x = rect.x + 28
            if it.badge is not None:
                btext, bcol = it.badge
                if not it.enabled:
                    bcol = _darken(bcol, 0.5)
                bw = draw_pill(surf, label_x, ry + 4, btext, bcol, size=self.size - 8)
                label_x += bw + 8
            draw_text(surf, it.label, label_x, ry + 2, self.size, col)
            if it.right is not None:
                draw_text(surf, str(it.right), rect.right - 14, ry + 2, self.size - 2,
                          C.GREY, right=True)
        # scroll hints (drawn, not font glyphs)
        ax = rect.right - 16
        if self.scroll > 0:
            pygame.draw.polygon(surf, C.ACCENT, [(ax, rect.y + 8), (ax + 10, rect.y + 8),
                                                 (ax + 5, rect.y + 2)])
        if end < len(self.items):
            by = rect.bottom - 12
            pygame.draw.polygon(surf, C.ACCENT, [(ax, by), (ax + 10, by), (ax + 5, by + 6)])
