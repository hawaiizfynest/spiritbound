"""
Spiritbound - endings.

Picks which closing the player earns once Nullith is soothed, from the way they
played: how widely they bonded, how much they freed, how much they helped the
folk of Aetheria, and how far their own bond-rank grew. Pure helpers (no
pygame) reading GameData, so the choice is fully unit-testable; the EndingState
in menus.py renders the chosen ending's lines.

Buckets (one is always chosen - `choose` is total):
  guardian   - a beloved keeper: broad bonds AND high kindness
  collector  - a devoted tamer: bonded most of the roster, kept rather than freed
  liberator  - a gentle wanderer: freed many of the Aethers they met
  restorer   - the canonical close: you mended the Spring (the fallback)

Written by LJ "HawaiizFynest" Eblacas
"""

from . import dex


def _ending(id, title, subtitle, lines):
    return {"id": id, "title": title, "subtitle": subtitle, "lines": lines}


ENDINGS = {
    "guardian": _ending(
        "guardian", "Keeper of Aetheria", "a beloved warden of wild and folk alike",
        ["The Spring sings, and from every hollow and hill the spirits answer it.",
         "You bonded widely, yet never closed your hand - and the valley learned",
         "to trust a human heart again.",
         "Long after the water stills, your name stays inside the song."]),
    "collector": _ending(
        "collector", "The Devoted Tamer", "keeper of the longest roster Aetheria has known",
        ["Card by card, you gathered nearly every wild heart in Aetheria.",
         "Your iDentifi hangs heavy with names, and each was a patience you earned -",
         "no trail unwalked, no spark left unanswered.",
         "The Spring runs whole, and the great roster is yours alone."]),
    "liberator": _ending(
        "liberator", "The Gentle Wanderer", "the one who let the wild stay wild",
        ["You met so many, and held so few.",
         "Card after card you opened, and set the wild loose again.",
         "The forests keep your kindness the way they keep the rain.",
         "The Spring runs clear, and somewhere a freed Aether turns for home."]),
    "restorer": _ending(
        "restorer", "The Spring-Mender", "who reminded a guardian how to bond",
        ["As the last spark gutters, Nullith stills - and remembers being loved.",
         "You did not break the guardian. You reminded it how to bond.",
         "Light wells up through the water, and the whole valley breathes again.",
         "Aetheria remembers how to sing, and the song begins with you."]),
}

DEFAULT_ENDING = "restorer"

# Per-ending visual identity for EndingState (plain data; no pygame here).
# sky = (top_rgb, bottom_rgb) gradient; accent = title colour;
# motif = how the closing scene animates: gather | parade | freedom | spring.
VISUALS = {
    "guardian":  {"accent": (236, 206, 120), "glow": (255, 226, 150),
                  "sky": ((44, 30, 26), (190, 132, 70)),  "motif": "gather"},
    "collector": {"accent": (168, 170, 240), "glow": (150, 150, 240),
                  "sky": ((20, 20, 48), (78, 64, 132)),   "motif": "parade"},
    "liberator": {"accent": (158, 230, 200), "glow": (200, 244, 230),
                  "sky": ((34, 78, 86), (150, 214, 206)), "motif": "freedom"},
    "restorer":  {"accent": (120, 224, 232), "glow": (150, 235, 245),
                  "sky": ((14, 26, 46), (44, 126, 156)),  "motif": "spring"},
}


def choose(save):
    """Pick the ending id for this playthrough. Total - always returns a valid
    id, defaulting to the canonical 'restorer'."""
    bonded = dex.bonded_count(save)
    bondable = max(1, dex.bondable_total())
    bonded_frac = bonded / bondable
    kindness = getattr(save, "kindness", 0)
    freed = getattr(save, "creatures_freed", 0)

    # Liberator: let many go (compassion over collection)
    if freed >= 5 and freed >= bonded:
        return "liberator"
    # Guardian: a broad bond AND a generous hand toward people
    if bonded_frac >= 0.5 and kindness >= 5:
        return "guardian"
    # Collector: nearly filled iDentifi, kept rather than freed
    if bonded_frac >= 0.7:
        return "collector"
    # Canonical close
    return DEFAULT_ENDING


def lines_for(ending_id):
    return ENDINGS.get(ending_id, ENDINGS[DEFAULT_ENDING])["lines"]


def title_for(ending_id):
    return ENDINGS.get(ending_id, ENDINGS[DEFAULT_ENDING])["title"]


def subtitle_for(ending_id):
    return ENDINGS.get(ending_id, ENDINGS[DEFAULT_ENDING])["subtitle"]


def visual_for(ending_id):
    return VISUALS.get(ending_id, VISUALS[DEFAULT_ENDING])
