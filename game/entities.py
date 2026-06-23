"""
Spiritbound - entities and save state.

Aether        a single creature instance (stats, level, xp, moves, status)
Party         active team (max 6) plus an overflow reserve box
Inventory     item bag
GameData      the whole save state (party, bag, money, flags, position)

No pygame imports here - pure logic, fully unit-testable.

Written by LJ "HawaiizFynest" Eblacas
"""

import json
import random

from .data import (SPECIES, MOVES, xp_for_level, stage_mult)

MAX_LEVEL = 50
MAX_MOVES = 4
_STAT_IDX = {"hp": 0, "atk": 1, "def": 2, "spd": 3}


def apply_move_choice(moves, candidate, slot):
    """Pure replace/skip resolver for learning a move at the 4-move cap.

    `moves`     the creature's current ordered move list
    `candidate` the move id being offered
    `slot`      None to skip (learn nothing), else the index in `moves` to
                replace with `candidate`

    Returns a NEW move list (never mutates the input). Rules:
      - already knows the candidate            -> unchanged
      - room under the cap                      -> candidate appended (slot ignored)
      - at the cap, skip (slot is None)         -> unchanged
      - at the cap, valid slot                  -> that slot replaced
      - at the cap, slot out of range           -> ValueError
    """
    result = list(moves)
    if candidate in result:
        return result
    if len(result) < MAX_MOVES:
        result.append(candidate)
        return result
    if slot is None:
        return result
    if not (0 <= slot < len(result)):
        raise ValueError(f"replace slot {slot} out of range for {len(result)} moves")
    result[slot] = candidate
    return result

# Agility is derived from a creature's speed and body shape (nimble shapes are
# quicker on their feet, heavy ones less so) unless a species supplies an
# explicit 5th base value to override it. Special Attack / Special Defense are
# derived the same way from Attack / Defense (casters lean special, bruisers
# physical) unless explicit 6th / 7th base values are given.
_AGI_MULT = {"bird": 1.3, "fish": 1.2, "wisp": 1.2, "bug": 1.15, "serpent": 1.05,
             "blob": 1.0, "quad": 1.0, "rock": 0.7}
_SPA_MULT = {"wisp": 1.3, "serpent": 1.15, "fish": 1.1, "bug": 1.1, "bird": 1.05,
             "blob": 1.0, "quad": 0.85, "rock": 0.7}
_SPDEF_MULT = {"wisp": 1.15, "fish": 1.1, "bird": 1.05, "serpent": 1.05, "blob": 1.0,
               "bug": 0.95, "quad": 0.95, "rock": 0.9}


def base_agility(species):
    """A species' base agility (explicit 5th base value, else derived from speed/shape)."""
    base = species["base"]
    if len(base) > 4:
        return base[4]
    return int(round(base[3] * _AGI_MULT.get(species["shape"], 1.0)))


def base_spatk(species):
    base = species["base"]
    if len(base) > 5:
        return base[5]
    return int(round(base[1] * _SPA_MULT.get(species["shape"], 1.0)))


def base_spdef(species):
    base = species["base"]
    if len(base) > 6:
        return base[6]
    return int(round(base[2] * _SPDEF_MULT.get(species["shape"], 1.0)))


# ---- character (trainer) leveling ----
CHAR_MAX_LEVEL = 30
_CHAR_STAT_CYCLE = ("charisma", "luck", "insight", "vitality")


def char_xp_for_level(level):
    """XP needed to advance the trainer from `level` to `level` + 1."""
    return 30 + 25 * (level - 1)


# ---------------------------------------------------------------------------
# Aether
# ---------------------------------------------------------------------------
class Aether:
    def __init__(self, species_id, level, nickname=None, iv=None):
        assert species_id in SPECIES, "unknown species: %s" % species_id
        self.species_id = species_id
        self.level = max(1, min(MAX_LEVEL, level))
        self.nickname = nickname
        self.xp = xp_for_level(self.level)
        self.iv = iv or {k: random.randint(0, 3) for k in ("hp", "atk", "def", "spd")}
        self.moves = []
        self.status = None                       # None | "poison" | "burn" | "paralysis" | "sleep"
        self.status_turns = 0                     # battle only (sleep countdown); never saved
        self.stages = {"atk": 0, "def": 0, "spd": 0}   # battle only, never saved
        self._learn_initial_moves()
        self.hp = self.max_hp
        self.mp = self.max_mp

    # --- identity ---
    @property
    def species(self):
        return SPECIES[self.species_id]

    @property
    def name(self):
        return self.nickname or self.species["name"]

    @property
    def type(self):
        return self.species["type"]

    # --- stats ---
    def raw_stat(self, key):
        base = self.species["base"]
        shape = self.species["shape"]
        iv = self.iv.get(key, 0)
        if key == "agi":
            b = base[4] if len(base) > 4 else base[3] * _AGI_MULT.get(shape, 1.0)
        elif key == "spatk":
            b = base[5] if len(base) > 5 else base[1] * _SPA_MULT.get(shape, 1.0)
        elif key == "spdef":
            b = base[6] if len(base) > 6 else base[2] * _SPDEF_MULT.get(shape, 1.0)
        else:
            b = base[_STAT_IDX[key]]
        if key == "hp":
            return int(b * 2 * self.level / 100) + self.level + 10 + iv
        return int(b * 2 * self.level / 100) + 5 + iv

    @property
    def max_hp(self):
        return self.raw_stat("hp")

    @property
    def max_mp(self):
        return 10 + self.level * 2

    def battle_stat(self, key):
        return max(1, int(self.raw_stat(key) * stage_mult(self.stages.get(key, 0))))

    def battle_stat_as(self, raw_key, stage_key):
        """Raw value of one stat, scaled by another stat's battle stage
        (lets special attacks ride the ATK/DEF buffs)."""
        return max(1, int(self.raw_stat(raw_key) * stage_mult(self.stages.get(stage_key, 0))))

    # --- moves ---
    def _learn_initial_moves(self):
        for lvl, mid in self.species["learnset"]:
            if lvl <= self.level:
                self._add_move(mid)
        if not self.moves:
            self._add_move("strike")

    def _add_move(self, mid):
        """Learn a move, dropping the oldest if at the cap. Used by the setup
        and evolution backfill paths where there's no player to ask. The
        interactive level-up path (gain_xp) instead emits a ('learn', mid) event
        so the battle can offer a replace/skip choice - see apply_move_choice."""
        if mid in self.moves:
            return
        self.moves.append(mid)
        if len(self.moves) > MAX_MOVES:
            self.moves.pop(0)

    def learn_or_replace(self, mid, slot):
        """Apply a player's replace/skip decision for a pending level-up move.
        Returns True if the move was learned. See apply_move_choice for rules."""
        before = list(self.moves)
        self.moves = apply_move_choice(self.moves, mid, slot)
        return self.moves != before

    def move_to(self, from_index, to_index):
        """Reorder: pull the move at `from_index` out and reinsert it at
        `to_index` (the fight-menu order is just `self.moves`). No-op for an
        out-of-range index or a move that isn't actually relocating. Returns
        True if the order changed."""
        n = len(self.moves)
        if not (0 <= from_index < n) or not (0 <= to_index < n):
            return False
        if from_index == to_index:
            return False
        m = self.moves.pop(from_index)
        self.moves.insert(to_index, m)
        return True

    def swap_moves(self, i, j):
        """Swap two moves in place (the up/down primitive for a reorder UI).
        Returns True if both indices are valid and distinct."""
        n = len(self.moves)
        if not (0 <= i < n) or not (0 <= j < n) or i == j:
            return False
        self.moves[i], self.moves[j] = self.moves[j], self.moves[i]
        return True

    # --- hp / mp / status ---
    def take_damage(self, dmg):
        self.hp = max(0, self.hp - int(dmg))

    def heal_hp(self, amount):
        before = self.hp
        self.hp = min(self.max_hp, self.hp + int(amount))
        return self.hp - before

    def restore_mp(self, amount):
        before = self.mp
        self.mp = min(self.max_mp, self.mp + int(amount))
        return self.mp - before

    @property
    def fainted(self):
        return self.hp <= 0

    def reset_battle(self):
        self.stages = {"atk": 0, "def": 0, "spd": 0}
        self.status = None
        self.status_turns = 0

    def full_restore(self):
        self.reset_battle()
        self.hp = self.max_hp
        self.mp = self.max_mp

    # --- progression ---
    def gain_xp(self, amount):
        """Add XP, level up, learn moves and evolve. Returns event tuples."""
        events = []
        if self.level >= MAX_LEVEL:
            return events
        self.xp += int(amount)
        while self.level < MAX_LEVEL and self.xp >= xp_for_level(self.level + 1):
            self.level += 1
            events.append(("level", self.level))
            for lvl, mid in self.species["learnset"]:
                if lvl == self.level and mid not in self.moves:
                    if len(self.moves) < MAX_MOVES:
                        self._add_move(mid)
                        events.append(("move", MOVES[mid]["name"]))
                    else:
                        # at the cap: defer to a player replace/skip choice
                        events.append(("learn", mid))
            ev = self.species["evolve"]
            if ev and self.level >= ev[0]:
                old_name = self.name
                self.species_id = ev[1]
                events.append(("evolve", old_name, self.species["name"]))
                for lvl, mid in self.species["learnset"]:
                    if lvl <= self.level and mid not in self.moves:
                        if len(self.moves) < MAX_MOVES:
                            self._add_move(mid)
                            events.append(("move", MOVES[mid]["name"]))
                        else:
                            # at the cap: defer to a player replace/skip choice
                            events.append(("learn", mid))
        return events

    def xp_into_level(self):
        cur = xp_for_level(self.level)
        nxt = xp_for_level(self.level + 1)
        if nxt <= cur:
            return 0.0
        return (self.xp - cur) / (nxt - cur)

    # --- serialization ---
    def serialize(self):
        return {"species_id": self.species_id, "nickname": self.nickname,
                "level": self.level, "xp": self.xp, "iv": self.iv,
                "moves": list(self.moves), "hp": self.hp, "mp": self.mp,
                "status": self.status}

    @classmethod
    def from_dict(cls, d):
        a = cls(d["species_id"], d["level"], d.get("nickname"), d.get("iv"))
        a.xp = d.get("xp", a.xp)
        a.moves = d.get("moves", a.moves) or a.moves
        a.hp = d.get("hp", a.max_hp)
        a.mp = d.get("mp", a.max_mp)
        a.status = d.get("status")
        a.hp = min(a.hp, a.max_hp)
        a.mp = min(a.mp, a.max_mp)
        return a


# ---------------------------------------------------------------------------
# Party
# ---------------------------------------------------------------------------
class Party:
    MAX_ACTIVE = 6

    def __init__(self):
        self.members = []
        self.reserve = []

    def add(self, aether):
        """Add to the active team if there's room, else to reserve.
        Returns 'party' or 'reserve'."""
        if len(self.members) < self.MAX_ACTIVE:
            self.members.append(aether)
            return "party"
        self.reserve.append(aether)
        return "reserve"

    def first_healthy_index(self):
        for i, a in enumerate(self.members):
            if not a.fainted:
                return i
        return None

    def all_fainted(self):
        return all(a.fainted for a in self.members) if self.members else True

    def heal_all(self):
        for a in self.members:
            a.full_restore()
        for a in self.reserve:
            a.full_restore()

    def serialize(self):
        return {"members": [a.serialize() for a in self.members],
                "reserve": [a.serialize() for a in self.reserve]}

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.members = [Aether.from_dict(x) for x in d.get("members", [])]
        p.reserve = [Aether.from_dict(x) for x in d.get("reserve", [])]
        return p


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
class Inventory:
    def __init__(self):
        self.items = {}   # item_id -> count

    def add(self, item_id, n=1):
        self.items[item_id] = self.items.get(item_id, 0) + n

    def remove(self, item_id, n=1):
        if item_id in self.items:
            self.items[item_id] -= n
            if self.items[item_id] <= 0:
                del self.items[item_id]

    def count(self, item_id):
        return self.items.get(item_id, 0)

    def has(self, item_id):
        return self.count(item_id) > 0

    def serialize(self):
        return dict(self.items)

    @classmethod
    def from_dict(cls, d):
        inv = cls()
        inv.items = {k: int(v) for k, v in (d or {}).items()}
        return inv


# ---------------------------------------------------------------------------
# GameData (full save state)
# ---------------------------------------------------------------------------
class GameData:
    def __init__(self):
        self.party = Party()
        self.inventory = Inventory()
        self.money = 500
        self.flags = set()
        self.map_id = "vale"
        self.px = 8
        self.py = 8
        self.facing = "down"
        self.playtime = 0.0
        self.started = False    # has the player chosen a starter?
        # character stats (grow later via character leveling / items)
        self.charisma = 3       # better shop prices and negotiations
        self.luck = 3           # better odds on bonds and random finds
        self.insight = 3        # creatures earn more XP
        self.vitality = 3       # party recovers HP after winning a battle
        self.char_level = 1     # trainer level (gates bonding + obedience)
        self.char_xp = 0
        # quests: qid -> "active" | "done" (absence == not started)
        self.quests = {}
        # qid -> index of the objective currently in progress
        self.quest_step = {}
        # iDentifi: species the player has encountered / bonded (bonded subset of seen)
        self.dex_seen = set()
        self.dex_bonded = set()
        # ending-influencing choices (compassion vs. collection, helpfulness)
        self.kindness = 0          # helping townsfolk, healing, finishing quests
        self.creatures_freed = 0   # wild Aethers released rather than kept
        # robbery: robber_id -> {"items": {iid: n}, "creatures": [serialized...]}
        # a villain that beats you takes your bag + all-but-one creature here,
        # returned when you win the rematch. Empty == nothing stashed.
        self.stashes = {}
        # audio prefs (persisted so a mute sticks across sessions) - #13
        self.audio_muted = False
        self.audio_volume = 0.6

    def has_flag(self, f):
        return f in self.flags

    def set_flag(self, f):
        self.flags.add(f)

    def dex_see(self, species_id):
        """Record that the player has encountered this species. Returns True the
        first time it's seen."""
        if species_id in self.dex_seen:
            return False
        self.dex_seen.add(species_id)
        return True

    def dex_bond(self, species_id):
        """Record that the player has bonded/owned this species (also marks it
        seen). Returns True the first time it's bonded."""
        self.dex_seen.add(species_id)
        if species_id in self.dex_bonded:
            return False
        self.dex_bonded.add(species_id)
        return True

    def char_xp_to_next(self):
        return char_xp_for_level(self.char_level)

    # --- robbery / recovery ---
    def has_stash(self, robber_id):
        """True if `robber_id` is currently holding stolen goods."""
        s = self.stashes.get(robber_id)
        return bool(s and (s.get("items") or s.get("creatures")))

    def rob(self, robber_id):
        """A robber takes the player's bag items and all-but-one party creature
        into `robber_id`'s stash. The player always keeps at least one creature
        (the first healthy one, else the first) so the game can continue.
        Idempotent-safe: a second rob merges into the existing stash. Returns the
        stash dict that was taken."""
        stash = self.stashes.setdefault(robber_id, {"items": {}, "creatures": []})
        # take the whole bag
        for iid, n in self.inventory.items.items():
            stash["items"][iid] = stash["items"].get(iid, 0) + n
        self.inventory.items = {}
        # take all but one creature - keep a healthy one if possible
        members = self.party.members
        if len(members) > 1:
            keep_idx = self.party.first_healthy_index()
            if keep_idx is None:
                keep_idx = 0
            keep = members[keep_idx]
            for a in members:
                if a is not keep:
                    stash["creatures"].append(a.serialize())
            self.party.members = [keep]
        return stash

    def recover_stash(self, robber_id):
        """Return everything `robber_id` stole: items back to the bag, creatures
        back to the party (overflow to reserve). Clears the stash. Returns True
        if anything was recovered."""
        s = self.stashes.get(robber_id)
        if not s or not (s.get("items") or s.get("creatures")):
            return False
        for iid, n in s.get("items", {}).items():
            self.inventory.add(iid, n)
        for cd in s.get("creatures", []):
            self.party.add(Aether.from_dict(cd))
        self.stashes.pop(robber_id, None)
        return True

    def gain_char_xp(self, amount):
        """Add trainer XP. Returns a list of ('level', new_level, stat_raised) events."""
        events = []
        if self.char_level >= CHAR_MAX_LEVEL:
            return events
        self.char_xp += int(amount)
        while (self.char_level < CHAR_MAX_LEVEL
               and self.char_xp >= char_xp_for_level(self.char_level)):
            self.char_xp -= char_xp_for_level(self.char_level)
            self.char_level += 1
            stat = _CHAR_STAT_CYCLE[(self.char_level - 2) % len(_CHAR_STAT_CYCLE)]
            setattr(self, stat, getattr(self, stat) + 1)
            events.append(("level", self.char_level, stat))
        if self.char_level >= CHAR_MAX_LEVEL:
            self.char_xp = 0
        return events

    def serialize(self):
        return {
            "party": self.party.serialize(),
            "inventory": self.inventory.serialize(),
            "money": self.money,
            "flags": sorted(self.flags),
            "map_id": self.map_id,
            "px": self.px, "py": self.py, "facing": self.facing,
            "playtime": self.playtime,
            "started": self.started,
            "charisma": self.charisma,
            "luck": self.luck,
            "insight": self.insight,
            "vitality": self.vitality,
            "char_level": self.char_level,
            "char_xp": self.char_xp,
            "quests": dict(self.quests),
            "quest_step": dict(self.quest_step),
            "dex_seen": sorted(self.dex_seen),
            "dex_bonded": sorted(self.dex_bonded),
            "kindness": self.kindness,
            "creatures_freed": self.creatures_freed,
            "audio_muted": self.audio_muted,
            "audio_volume": self.audio_volume,
            "stashes": {rid: {"items": dict(s.get("items", {})),
                              "creatures": list(s.get("creatures", []))}
                        for rid, s in self.stashes.items()},
            "version": 1,
        }

    @classmethod
    def from_dict(cls, d):
        g = cls()
        g.party = Party.from_dict(d.get("party", {}))
        g.inventory = Inventory.from_dict(d.get("inventory", {}))
        g.money = int(d.get("money", 0))
        g.flags = set(d.get("flags", []))
        g.map_id = d.get("map_id", "vale")
        g.px = int(d.get("px", 8))
        g.py = int(d.get("py", 8))
        g.facing = d.get("facing", "down")
        g.playtime = float(d.get("playtime", 0.0))
        g.started = bool(d.get("started", True))
        g.charisma = int(d.get("charisma", 3))
        g.luck = int(d.get("luck", 3))
        g.insight = int(d.get("insight", 3))
        g.vitality = int(d.get("vitality", 3))
        g.char_level = int(d.get("char_level", 1))
        g.char_xp = int(d.get("char_xp", 0))
        g.quests = {k: str(v) for k, v in (d.get("quests") or {}).items()}
        g.quest_step = {k: int(v) for k, v in (d.get("quest_step") or {}).items()}
        g.dex_seen = set(d.get("dex_seen", []))
        g.dex_bonded = set(d.get("dex_bonded", []))
        g.kindness = int(d.get("kindness", 0))
        g.creatures_freed = int(d.get("creatures_freed", 0))
        g.audio_muted = bool(d.get("audio_muted", False))
        g.audio_volume = float(d.get("audio_volume", 0.6))
        g.stashes = {rid: {"items": {k: int(v) for k, v in (s.get("items") or {}).items()},
                           "creatures": list(s.get("creatures") or [])}
                     for rid, s in (d.get("stashes") or {}).items()}
        # creatures the player already owns are, by definition, bonded+seen -
        # backfills the dex for saves made before the iDentifi existed
        for a in g.party.members + g.party.reserve:
            g.dex_bonded.add(a.species_id)
        # bonded always implies seen
        g.dex_seen |= g.dex_bonded
        return g

    def save_to_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.serialize(), f, indent=2)

    @classmethod
    def load_from_file(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def make_wild(species_id, level):
    return Aether(species_id, level)


def make_starter(species_id):
    return Aether(species_id, 5)
