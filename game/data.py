"""
Spiritbound - data tables.

Defines the six elements and their effectiveness chart, the move list, the
Aether species roster, and the item list. Pure data + a few rule helpers; no
pygame imports so it can be unit-tested in isolation.

Written by LJ "HawaiizFynest" Eblacas
"""

import math
import random

# ---------------------------------------------------------------------------
# Elements and the type-effectiveness chart
#
# Two intuitive triangles:
#   Ember > Verdant > Tide > Ember        (fire > nature > water > fire)
#   Bolt  > Gale    > Terra > Bolt        (storm > wind > earth > storm)
# Super-effective = 2.0, resisted = 0.5, everything else 1.0.
# ---------------------------------------------------------------------------
ELEMENTS = ["Ember", "Verdant", "Tide", "Bolt", "Gale", "Terra"]

_SUPER = {
    ("Ember", "Verdant"), ("Verdant", "Tide"), ("Tide", "Ember"),
    ("Bolt", "Gale"), ("Gale", "Terra"), ("Terra", "Bolt"),
}
_WEAK = {(d, a) for (a, d) in _SUPER}


def type_multiplier(attack_type, defend_type):
    if attack_type is None or defend_type is None:
        return 1.0
    if (attack_type, defend_type) in _SUPER:
        return 2.0
    if (attack_type, defend_type) in _WEAK:
        return 0.5
    return 1.0


def weaknesses(defend_type):
    """Element types that hit this type for super-effective (2.0) damage."""
    if defend_type is None:
        return []
    return [a for a in ELEMENTS if type_multiplier(a, defend_type) == 2.0]


def resistances(defend_type):
    """Element types this type resists (0.5 damage)."""
    if defend_type is None:
        return []
    return [a for a in ELEMENTS if type_multiplier(a, defend_type) == 0.5]


def matchup_score(cand_type, foe_types):
    """How a candidate of `cand_type` fares against the foe type(s).

    Pure: takes element-name strings only (no creatures), so it's trivially
    testable and stays pygame-free. `foe_types` is one type or an iterable of
    them (multi-enemy battles aggregate across every living foe).

    Combines two dimensions per foe:
      offense  - the candidate's STAB hitting the foe  (2.0 good / 0.5 bad)
      defense  - the foe's STAB hitting the candidate   (2.0 bad  / 0.5 good)
    Returns a net float: > 0 favors the candidate, < 0 favors the foe(s).
    """
    if isinstance(foe_types, str) or foe_types is None:
        foe_types = [foe_types]
    net = 0.0
    for ft in foe_types:
        if ft is None:
            continue
        # offense: +1 super-effective, -1 resisted, 0 neutral
        off = type_multiplier(cand_type, ft)
        net += 1.0 if off > 1.0 else -1.0 if off < 1.0 else 0.0
        # defense: foe hitting us is bad, so the sign is flipped
        dfn = type_multiplier(ft, cand_type)
        net += -1.0 if dfn > 1.0 else 1.0 if dfn < 1.0 else 0.0
    return net


def matchup_verdict(cand_type, foe_types):
    """A `+` / `-` / `''` recommendation tag from `matchup_score`."""
    s = matchup_score(cand_type, foe_types)
    if s > 0:
        return "+"
    if s < 0:
        return "-"
    return ""


# ---------------------------------------------------------------------------
# Stat-stage multipliers (for in-battle buffs/debuffs, range -6..+6)
# ---------------------------------------------------------------------------
def stage_mult(stage):
    stage = max(-6, min(6, stage))
    if stage >= 0:
        return (2 + stage) / 2.0
    return 2.0 / (2 - stage)


# ---------------------------------------------------------------------------
# Status conditions (one major status at a time, like the classics)
#   abbr / color  - HUD badge
#   tick          - fraction of max HP lost at end of each turn (0 = none)
#   skip_chance   - chance the afflicted can't act this turn (paralysis)
#   sleep         - True if it skips turns until it wakes (uses status_turns)
#   phys_cut      - multiplier on the afflicted's *physical* damage dealt (burn)
#   catch_mult    - catch-rate bonus while afflicted (poison's old 1.5)
#   inflict / cure / wake - flavor text
# ---------------------------------------------------------------------------
def _st(abbr, color, verb, **kw):
    d = {"abbr": abbr, "color": color, "verb": verb,
         "tick": 0.0, "skip_chance": 0.0, "sleep": False,
         "phys_cut": 1.0, "catch_mult": 1.0}
    d.update(kw)
    return d


STATUSES = {
    "poison":    _st("PSN", (196, 138, 226), "was poisoned",
                     tick=1.0 / 8, catch_mult=1.5),
    "burn":      _st("BRN", (244, 134, 86), "was burned",
                     tick=1.0 / 8, phys_cut=0.5),
    "paralysis": _st("PAR", (236, 214, 92), "was paralyzed",
                     skip_chance=0.25, catch_mult=1.5),
    "sleep":     _st("SLP", (150, 168, 220), "fell asleep",
                     sleep=True, catch_mult=2.0),
}

# How long sleep lasts, in turns (inclusive range), rolled on infliction.
SLEEP_MIN, SLEEP_MAX = 1, 3


# ---------------------------------------------------------------------------
# Weather (a battle-wide modifier)
#   boost / weaken - element types whose damage is scaled (1.5x / 0.5x)
#   chip           - fraction of max HP non-immune combatants lose each turn
#   immune         - element types that ignore the chip (e.g. Terra in sand)
# ---------------------------------------------------------------------------
def _w(name, blurb, boost=(), weaken=(), chip=0.0, immune=()):
    return {"name": name, "blurb": blurb, "boost": set(boost),
            "weaken": set(weaken), "chip": chip, "immune": set(immune)}


WEATHER = {
    "rain":      _w("Rain", "Rain pours down!",
                    boost=("Tide",), weaken=("Ember",)),
    "sun":       _w("Harsh Sun", "The sunlight turns harsh!",
                    boost=("Ember",), weaken=("Tide",)),
    "sandstorm": _w("Sandstorm", "A sandstorm kicks up!",
                    boost=("Terra",), chip=1.0 / 16,
                    immune=("Terra",)),
    "storm":     _w("Gale Storm", "A roaring gale storm builds!",
                    boost=("Bolt", "Gale"), weaken=("Terra",)),
}


def weather_mult(weather_id, attack_type):
    """Damage multiplier weather applies to a move of the given element."""
    if not weather_id:
        return 1.0
    w = WEATHER.get(weather_id)
    if not w or attack_type is None:
        return 1.0
    if attack_type in w["boost"]:
        return 1.5
    if attack_type in w["weaken"]:
        return 0.5
    return 1.0


# ---------------------------------------------------------------------------
# Experience curve
# ---------------------------------------------------------------------------
def xp_for_level(level):
    """Total XP required to *be* the given level."""
    if level <= 1:
        return 0
    return int(0.8 * level ** 3)


def xp_yield_for(defeated_species_id, defeated_level):
    base = SPECIES[defeated_species_id]["xp_yield"]
    return int(base * defeated_level / 7) + 1


# ---------------------------------------------------------------------------
# Moves
#   cat: "phys" | "spec" | "status"   (damage uses ATK vs DEF either way)
#   effect kinds: heal / heal_mp / buff / debuff / poison / status / weather
#     - "status" carries {"status": <id>, "target", optional "chance"}
#     - "weather" carries {"weather": <id>}
#   target: "self" | "enemy" | "ally"
#     - "ally" routes a heal/heal_mp/cure to a party member the player picks
#       (active OR benched); the battle opens an ally-pick step for it.
# ---------------------------------------------------------------------------
def _m(name, type, power, acc, mp, cat, effect=None):
    return {"name": name, "type": type, "power": power, "acc": acc,
            "mp": mp, "cat": cat, "effect": effect}


MOVES = {
    "strike":     _m("Strike", None, 35, 100, 0, "phys"),

    # Ember
    "ember":      _m("Ember", "Ember", 40, 100, 3, "spec"),
    "flamefang":  _m("Flame Fang", "Ember", 65, 95, 7, "phys"),
    "inferno":    _m("Inferno", "Ember", 92, 85, 15, "spec"),

    # Verdant
    "vinewhip":   _m("Vine Whip", "Verdant", 40, 100, 3, "phys"),
    "leafblade":  _m("Leaf Blade", "Verdant", 65, 95, 7, "phys"),
    "toxicspore": _m("Toxic Spore", "Verdant", 0, 90, 6, "status",
                     {"kind": "poison", "target": "enemy"}),
    "bloom":      _m("Bloom", "Verdant", 0, 100, 9, "status",
                     {"kind": "heal", "pct": 0.5, "target": "self"}),
    "solbeam":    _m("Sol Beam", "Verdant", 95, 85, 15, "spec"),

    # Tide
    "bubble":     _m("Bubble", "Tide", 40, 100, 3, "spec"),
    "aquajet":    _m("Aqua Jet", "Tide", 55, 100, 6, "phys"),
    "torrent":    _m("Torrent", "Tide", 90, 85, 14, "spec"),
    "mist":       _m("Mist", "Tide", 0, 100, 6, "status",
                     {"kind": "buff", "stat": "def", "stage": 1, "target": "self"}),

    # Bolt
    "spark":      _m("Spark", "Bolt", 40, 100, 3, "spec"),
    "voltlash":   _m("Volt Lash", "Bolt", 65, 95, 7, "phys"),
    "thunder":    _m("Thunderclap", "Bolt", 95, 80, 15, "spec"),
    "charge":     _m("Charge", "Bolt", 0, 100, 5, "status",
                     {"kind": "buff", "stat": "atk", "stage": 1, "target": "self"}),

    # Gale
    "gust":       _m("Gust", "Gale", 40, 100, 3, "spec"),
    "airslash":   _m("Air Slash", "Gale", 65, 95, 7, "spec"),
    "cyclone":    _m("Cyclone", "Gale", 90, 85, 14, "spec"),
    "tailwind":   _m("Tailwind", "Gale", 0, 100, 5, "status",
                     {"kind": "buff", "stat": "spd", "stage": 2, "target": "self"}),

    # Terra
    "pebble":     _m("Pebble Toss", "Terra", 40, 100, 3, "phys"),
    "rockfall":   _m("Rock Fall", "Terra", 65, 90, 7, "phys"),
    "quake":      _m("Quake", "Terra", 95, 80, 15, "phys"),
    "harden":     _m("Harden", "Terra", 0, 100, 4, "status",
                     {"kind": "buff", "stat": "def", "stage": 1, "target": "self"}),

    # Neutral utility
    "screech":    _m("Screech", None, 0, 90, 5, "status",
                     {"kind": "debuff", "stat": "def", "stage": -1, "target": "enemy"}),
    "growl":      _m("Growl", None, 0, 90, 3, "status",
                     {"kind": "debuff", "stat": "atk", "stage": -1, "target": "enemy"}),
    "recover":    _m("Recover", None, 0, 100, 10, "status",
                     {"kind": "heal", "pct": 0.5, "target": "self"}),

    # Added variety
    "bite":       _m("Bite", None, 55, 100, 6, "phys"),
    "crunch":     _m("Crunch", None, 82, 95, 13, "phys"),
    "emberlash":  _m("Ember Lash", "Ember", 55, 100, 6, "phys"),
    "venomfang":  _m("Venom Fang", "Verdant", 52, 95, 8, "phys",
                     {"kind": "poison", "target": "enemy"}),
    "aquaheal":   _m("Aqua Heal", "Tide", 0, 100, 9, "status",
                     {"kind": "heal", "pct": 0.5, "target": "self"}),
    "shock":      _m("Shock", "Bolt", 55, 100, 6, "phys"),
    "sandblast":  _m("Sand Blast", "Terra", 55, 95, 7, "spec"),
    "gustcut":    _m("Gust Cut", "Gale", 55, 100, 6, "phys"),
    "meditate":   _m("Meditate", None, 0, 100, 0, "status",
                     {"kind": "heal_mp", "pct": 0.45, "target": "self"}),

    # ---- ally-target support (the player picks which party member) ----
    "mend":       _m("Mend", "Tide", 0, 100, 9, "status",
                     {"kind": "heal", "pct": 0.5, "target": "ally"}),
    "lifechime":  _m("Life Chime", "Verdant", 0, 100, 12, "status",
                     {"kind": "heal", "pct": 0.65, "target": "ally"}),
    "sharemind":  _m("Share Mind", None, 0, 100, 0, "status",
                     {"kind": "heal_mp", "pct": 0.4, "target": "ally"}),
    "cleanse":    _m("Cleanse", "Tide", 0, 100, 7, "status",
                     {"kind": "cure", "target": "ally"}),

    # ---- status & weather moves ----
    "scorch":     _m("Scorch", "Ember", 50, 100, 7, "spec",
                     {"kind": "status", "status": "burn", "target": "enemy", "chance": 0.30}),
    "emberveil":  _m("Ember Veil", "Ember", 0, 100, 6, "status",
                     {"kind": "status", "status": "burn", "target": "enemy", "chance": 1.0}),
    "staticbolt": _m("Static Bolt", "Bolt", 50, 100, 7, "spec",
                     {"kind": "status", "status": "paralysis", "target": "enemy", "chance": 0.30}),
    "stunsnare":  _m("Stun Snare", "Bolt", 0, 90, 6, "status",
                     {"kind": "status", "status": "paralysis", "target": "enemy", "chance": 1.0}),
    "lullaby":    _m("Lullaby", "Gale", 0, 75, 7, "status",
                     {"kind": "status", "status": "sleep", "target": "enemy", "chance": 1.0}),
    "spore":      _m("Sleep Spore", "Verdant", 0, 80, 7, "status",
                     {"kind": "status", "status": "sleep", "target": "enemy", "chance": 1.0}),
    "raindance":  _m("Rain Dance", "Tide", 0, 100, 8, "status",
                     {"kind": "weather", "weather": "rain", "target": "self"}),
    "sunflare":   _m("Sun Flare", "Ember", 0, 100, 8, "status",
                     {"kind": "weather", "weather": "sun", "target": "self"}),
    "sandveil":   _m("Sand Veil", "Terra", 0, 100, 8, "status",
                     {"kind": "weather", "weather": "sandstorm", "target": "self"}),
}


# Display names for the move-stat card (shared by the fight menu #21 and the
# move-learn screen #18). Pure data + a pure formatter, so they stay testable.
CATEGORY_NAMES = {"phys": "Physical", "spec": "Special", "status": "Status"}
STAT_NAMES = {"atk": "Attack", "def": "Defense", "spd": "Speed"}

_BLURB_TARGET = {"self": "the user", "ally": "an ally", "enemy": "the foe"}
_STATUS_VERB = {"burn": "Burns", "paralysis": "Paralyzes", "poison": "Poisons"}
_STATUS_INF = {"burn": "burn", "paralysis": "paralyze", "poison": "poison"}


def move_effect_blurb(move):
    """A short, human-readable description of a move's effect for the stat card.

    Pure (no pygame): takes a MOVES entry and returns one sentence describing
    its rider effect, or a one-line summary for a plain damaging / no-effect
    move. Reused by the fight-menu move window and the move-learn screen.
    """
    eff = move.get("effect")
    if not eff:
        return "No additional effect." if move.get("cat") == "status" else "Deals damage."

    kind = eff.get("kind")
    who = _BLURB_TARGET.get(eff.get("target", "enemy"), "the foe")

    if kind in ("heal", "heal_mp"):
        pct = int(round(eff.get("pct", 0) * 100))
        pool = "HP" if kind == "heal" else "MP"
        whose = "the user's" if eff.get("target") == "self" else f"{who}'s"
        return f"Restores {pct}% of {whose} {pool}."
    if kind == "buff":
        stat = STAT_NAMES.get(eff.get("stat"), eff.get("stat"))
        word = "Sharply raises" if eff.get("stage", 1) >= 2 else "Raises"
        return f"{word} the user's {stat}."
    if kind == "debuff":
        stat = STAT_NAMES.get(eff.get("stat"), eff.get("stat"))
        word = "Sharply lowers" if eff.get("stage", -1) <= -2 else "Lowers"
        return f"{word} {who}'s {stat}."
    if kind == "poison":
        return f"Poisons {who}."
    if kind == "status":
        sid = eff.get("status", "")
        chance = eff.get("chance", 1.0)
        if sid == "sleep":
            if chance >= 1.0:
                return f"Puts {who} to sleep."
            return f"{int(round(chance * 100))}% chance to put {who} to sleep."
        if chance >= 1.0:
            verb = _STATUS_VERB.get(sid, f"Inflicts {sid} on")
            return f"{verb} {who}."
        pct = int(round(chance * 100))
        return f"{pct}% chance to {_STATUS_INF.get(sid, sid)} {who}."
    if kind == "cure":
        return f"Cures {who}'s status condition."
    if kind == "weather":
        wid = eff.get("weather", "")
        wname = WEATHER.get(wid, {}).get("name", wid.capitalize())
        return f"Summons {wname.lower()}."
    return ""


# ---------------------------------------------------------------------------
# Species roster
#   base: [hp, atk, def, spd]
#   catch: 1..255 higher = easier to bond
#   shape: drawing style in ui.draw_creature
#   pal: [body, accent, dark] colors
# ---------------------------------------------------------------------------
def _s(name, type, base, catch, yield_, learnset, evolve, shape, pal, desc):
    return {"name": name, "type": type, "base": base, "catch": catch,
            "xp_yield": yield_, "learnset": learnset, "evolve": evolve,
            "shape": shape, "pal": pal, "desc": desc}


SPECIES = {
    # ---- Starters (evolve at 16) ----
    "cindle": _s("Cindle", "Ember", [45, 60, 40, 65], 45, 64,
                 [(1, "strike"), (1, "ember"), (6, "flamefang"),
                  (12, "screech"), (18, "inferno")],
                 (16, "pyrachs"), "blob",
                 [(236, 120, 64), (255, 196, 96), (140, 54, 30)],
                 "A restless ember-pup whose pelt smoulders when it is excited."),
    "sprigit": _s("Sprigit", "Verdant", [50, 50, 52, 48], 45, 64,
                  [(1, "strike"), (1, "vinewhip"), (6, "leafblade"),
                   (10, "toxicspore"), (14, "bloom"), (20, "solbeam")],
                  (16, "floravine"), "blob",
                  [(96, 196, 96), (196, 240, 150), (40, 110, 56)],
                  "A sprout-spirit that turns its leaf toward any source of warmth."),
    "driblet": _s("Driblet", "Tide", [48, 48, 50, 58], 45, 64,
                  [(1, "strike"), (1, "bubble"), (6, "aquajet"),
                   (12, "mist"), (18, "torrent")],
                  (16, "tidewyrm"), "blob",
                  [(78, 150, 230), (170, 220, 255), (36, 80, 150)],
                  "A droplet given will. It mimics the moods of nearby water."),

    # ---- Evolutions ----
    "pyrachs": _s("Pyrachs", "Ember", [75, 100, 68, 95], 45, 160,
                  [(18, "inferno"), (22, "scorch"), (24, "screech")],
                  None, "quad",
                  [(220, 84, 52), (255, 168, 72), (110, 30, 24)],
                  "Cindle grown fierce; cinders trail from its stride."),
    "floravine": _s("Floravine", "Verdant", [80, 78, 88, 66], 45, 160,
                    [(20, "solbeam"), (24, "spore"), (26, "toxicspore")],
                    None, "quad",
                    [(72, 170, 90), (180, 230, 130), (30, 96, 50)],
                    "A coiling guardian of bramble and bloom."),
    "tidewyrm": _s("Tidewyrm", "Tide", [78, 80, 82, 92], 45, 160,
                   [(18, "torrent"), (22, "raindance"), (24, "mist")],
                   None, "serpent",
                   [(72, 140, 220), (150, 210, 255), (32, 72, 140)],
                   "A river-serpent that rides its own current."),

    # ---- Wild ----
    "magmaw": _s("Magmaw", "Ember", [55, 65, 55, 40], 90, 70,
                 [(1, "strike"), (1, "ember"), (8, "flamefang"), (15, "inferno")],
                 None, "rock",
                 [(180, 70, 50), (255, 150, 60), (90, 28, 24)],
                 "A slow furnace-beast that hoards heat in its stony hide."),
    "thornkin": _s("Thornkin", "Verdant", [52, 58, 60, 44], 120, 60,
                   [(1, "strike"), (1, "vinewhip"), (7, "leafblade"), (13, "toxicspore")],
                   None, "blob",
                   [(110, 160, 80), (200, 220, 120), (54, 90, 44)],
                   "A bramble-imp that bristles when cornered."),
    "coralisk": _s("Coralisk", "Tide", [58, 55, 66, 50], 100, 66,
                   [(1, "strike"), (1, "bubble"), (8, "aquajet"), (14, "torrent")],
                   None, "serpent",
                   [(96, 170, 200), (180, 230, 220), (40, 96, 130)],
                   "A reef-dweller armoured in living coral."),
    "sparrk": _s("Sparrk", "Bolt", [40, 55, 40, 75], 130, 60,
                 [(1, "strike"), (1, "spark"), (7, "voltlash"), (13, "charge")],
                 (18, "voltagon"), "wisp",
                 [(240, 206, 80), (255, 240, 150), (150, 120, 30)],
                 "A jittery spark-mote that never holds still."),
    "voltagon": _s("Voltagon", "Bolt", [70, 92, 62, 105], 60, 160,
                   [(18, "thunder"), (20, "staticbolt"), (22, "charge")],
                   None, "quad",
                   [(236, 196, 64), (255, 230, 120), (130, 100, 24)],
                   "A storm coiled into muscle and crackling fur."),
    "zephlit": _s("Zephlit", "Gale", [44, 52, 44, 80], 130, 60,
                  [(1, "strike"), (1, "gust"), (7, "airslash"), (10, "meditate"), (13, "tailwind")],
                  (18, "galecrest"), "wisp",
                  [(160, 220, 220), (220, 250, 250), (80, 150, 160)],
                  "A wind-wisp that drifts wherever the breeze leads."),
    "galecrest": _s("Galecrest", "Gale", [66, 84, 60, 112], 60, 160,
                    [(18, "cyclone"), (20, "lullaby"), (22, "tailwind")],
                    None, "bird",
                    [(140, 210, 220), (210, 245, 250), (64, 130, 150)],
                    "A crested raptor that nests in the eye of storms."),
    "plumage": _s("Plumage", "Gale", [50, 60, 50, 72], 110, 64,
                  [(1, "strike"), (1, "gust"), (8, "airslash"), (15, "cyclone")],
                  None, "bird",
                  [(180, 200, 230), (230, 240, 250), (90, 110, 150)],
                  "A plume-tailed flyer fond of high, lonely cliffs."),
    "pebblit": _s("Pebblit", "Terra", [55, 58, 72, 34], 130, 60,
                  [(1, "strike"), (1, "pebble"), (7, "rockfall"), (13, "harden")],
                  (18, "boulderon"), "rock",
                  [(180, 140, 86), (220, 190, 130), (110, 80, 46)],
                  "A pebble-shelled critter that plays dead when startled."),
    "boulderon": _s("Boulderon", "Terra", [95, 88, 110, 40], 50, 170,
                    [(18, "quake"), (24, "harden")],
                    None, "rock",
                    [(150, 120, 80), (200, 170, 120), (90, 66, 40)],
                    "A mountain in miniature; the ground trembles at its step."),
    "tunneler": _s("Tunneler", "Terra", [60, 66, 60, 54], 110, 66,
                   [(1, "strike"), (1, "pebble"), (8, "rockfall"), (15, "quake")],
                   None, "blob",
                   [(170, 130, 90), (210, 180, 130), (100, 72, 44)],
                   "A burrower that surfaces only to feed and to fight."),

    # ---- Added roster ----
    "finnow": _s("Finnow", "Tide", [42, 48, 40, 62], 130, 60,
                 [(1, "strike"), (1, "bubble"), (7, "aquajet"), (13, "bite"), (20, "torrent")],
                 (20, "marlance"), "fish",
                 [(72, 150, 225), (180, 225, 255), (34, 80, 150)],
                 "A darting stream-fish that leaps at glints of light."),
    "marlance": _s("Marlance", "Tide", [80, 94, 66, 102], 55, 168,
                   [(20, "torrent"), (24, "aquaheal"), (26, "meditate"), (28, "mend")],
                   None, "fish",
                   [(58, 120, 210), (190, 235, 255), (26, 64, 132)],
                   "Finnow grown into a lance of muscle that spears the current."),
    "mawbug": _s("Mawbug", "Verdant", [46, 56, 52, 50], 120, 60,
                 [(1, "strike"), (1, "vinewhip"), (6, "bite"), (12, "venomfang")],
                 (18, "mantiscar"), "bug",
                 [(120, 170, 70), (210, 230, 130), (60, 96, 40)],
                 "A leaf-mimic grub with a surprising bite."),
    "mantiscar": _s("Mantiscar", "Verdant", [76, 98, 72, 86], 55, 168,
                    [(18, "leafblade"), (22, "venomfang"), (28, "crunch")],
                    None, "bug",
                    [(80, 150, 110), (190, 235, 180), (36, 90, 64)],
                    "Bladed forelimbs and a hunter's patience."),
    "cinderbat": _s("Cinderbat", "Ember", [48, 58, 46, 78], 120, 62,
                    [(1, "strike"), (1, "ember"), (7, "bite"), (14, "airslash")],
                    None, "bird",
                    [(200, 90, 70), (255, 170, 110), (96, 34, 30)],
                    "A cave-flyer that warms its wings on volcanic vents."),
    "duneworm": _s("Duneworm", "Terra", [64, 64, 66, 46], 110, 64,
                   [(1, "strike"), (1, "pebble"), (8, "sandblast"), (15, "quake")],
                   None, "serpent",
                   [(196, 168, 110), (230, 210, 150), (120, 96, 56)],
                   "It swims through loose sand as easily as water."),
    "glimmer": _s("Glimmer", "Bolt", [42, 50, 42, 74], 130, 60,
                  [(1, "strike"), (1, "spark"), (7, "shock"), (10, "meditate"), (13, "sharemind")],
                  None, "wisp",
                  [(245, 225, 120), (255, 250, 200), (150, 128, 40)],
                  "A mote of captured lightning that hums faintly."),
    "puffcap": _s("Puffcap", "Verdant", [60, 46, 54, 40], 120, 60,
                  [(1, "strike"), (1, "vinewhip"), (6, "toxicspore"), (12, "bloom")],
                  None, "blob",
                  [(210, 90, 96), (245, 230, 200), (120, 46, 52)],
                  "A cap-spirit that puffs spores when poked."),
    "craghorn": _s("Craghorn", "Terra", [72, 78, 82, 42], 90, 70,
                   [(1, "strike"), (1, "pebble"), (8, "rockfall"), (15, "quake")],
                   None, "quad",
                   [(150, 140, 130), (200, 190, 176), (86, 78, 70)],
                   "A sure-footed ridge-beast with granite horns."),
    "saltoad": _s("Saltoad", "Tide", [66, 56, 58, 46], 110, 62,
                  [(1, "strike"), (1, "bubble"), (8, "aquajet"), (12, "cleanse"), (16, "mend")],
                  None, "blob",
                  [(96, 170, 150), (190, 235, 210), (44, 96, 84)],
                  "A tide-pool toad that croaks with the surf."),
    "breezel": _s("Breezel", "Gale", [48, 54, 46, 76], 120, 60,
                  [(1, "strike"), (1, "gust"), (7, "gustcut"), (13, "tailwind")],
                  None, "bug",
                  [(170, 220, 225), (225, 250, 250), (90, 150, 158)],
                  "A dragonfly-spirit that races the wind for sport."),
    "voltkit": _s("Voltkit", "Bolt", [46, 58, 44, 70], 120, 60,
                  [(1, "strike"), (1, "spark"), (7, "shock"), (13, "charge")],
                  None, "blob",
                  [(236, 200, 80), (255, 236, 140), (132, 102, 28)],
                  "A static-furred kit that sticks to anything it touches."),

    # ---- Boss ----
    "nullith": _s("Nullith", "Bolt", [140, 96, 78, 88], 3, 400,
                  [(1, "strike"), (1, "voltlash"), (1, "thunder"),
                   (1, "screech"), (1, "charge")],
                  None, "hollow",
                  [(150, 90, 210), (230, 180, 255), (60, 30, 90)],
                  "The Hollow Guardian. Its bond with the Spring has curdled into static."),
}


# ---------------------------------------------------------------------------
# Items
#   kind: heal_hp | heal_mp | revive | cure | catch | key
# ---------------------------------------------------------------------------
def _i(name, kind, value, price, battle, field, desc, catch_mult=1.0):
    return {"name": name, "kind": kind, "value": value, "price": price,
            "battle": battle, "field": field, "desc": desc, "catch_mult": catch_mult}


ITEMS = {
    "salve":         _i("Salve", "heal_hp", 35, 50, True, True,
                        "Restores 35 HP to one Aether."),
    "greater_salve": _i("Greater Salve", "heal_hp", 90, 140, True, True,
                        "Restores 90 HP to one Aether."),
    "ether":         _i("Ether", "heal_mp", 20, 80, True, True,
                        "Restores 20 MP to one Aether."),
    "revive":        _i("Revive", "revive", 0, 200, True, True,
                        "Revives a fainted Aether to half HP."),
    "antidote":      _i("Antidote", "cure", 0, 40, True, True,
                        "Cures poison from one Aether."),
    # Catch items are "bond cards" you play on a weakened wild Aether. The dict
    # keys stay as the legacy *_crystal ids so existing saves keep working; only
    # the player-facing names/descriptions are cards.
    "bond_crystal":  _i("Bond Card", "catch", 0, 60, True, False,
                        "Played on a weakened wild Aether to bind it to a card.", 1.0),
    "prime_crystal": _i("Prime Card", "catch", 0, 180, True, False,
                        "A refined card whose sigil forms a far stronger bond.", 2.0),
    "full_restore":  _i("Full Restore", "full_restore", 0, 900, True, True,
                        "Fully restores one Aether's HP and MP and cures status."),
    "max_revive":    _i("Max Revive", "max_revive", 0, 1300, True, True,
                        "Revives a fainted Aether to full HP."),
    "aether_crystal": _i("Aether Card", "catch", 0, 1600, True, False,
                         "A flawless card - the surest bond there is.", 4.0),
    "spring_key":    _i("Spring Key", "key", 0, 0, False, False,
                        "An old key humming with Aether. It fits the Spring's seal."),
}

# Items offered by the shop, in order
SHOP_STOCK = ["salve", "greater_salve", "ether", "antidote", "revive",
              "bond_crystal", "prime_crystal"]

# Premium goods: pricey, and only stocked once you've earned some renown.
RARE_STOCK = ["full_restore", "max_revive", "aether_crystal"]
RARE_STOCK_RANK = 5     # trainer level the shop requires to carry these


def roll_field_find(luck, rng=None):
    """Item id found after a wild win, or None. Luck raises both the chance of
    finding something and the odds that it's a rare item."""
    rng = rng or random
    if rng.random() >= 0.05 + 0.02 * luck:        # luck 3 -> 11%, luck 10 -> 25%
        return None
    roll = rng.random()
    if roll < min(0.30, 0.03 * luck):             # rare slice grows with luck
        return rng.choice(RARE_STOCK)
    if roll < 0.55:
        return "ether"
    if roll < 0.85:
        return "salve"
    return "greater_salve"
