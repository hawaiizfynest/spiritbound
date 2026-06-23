"""
Spiritbound - iDentifi.

A Pokedex-style catalog over the species roster. Pure helpers (no pygame) that
read the player's `dex_seen` / `dex_bonded` sets on GameData and the static
SPECIES table to answer "what's the dex order", "is this seen/bonded", and the
completion tallies the iDentifi view shows.

Status per species:
  unknown  - not yet encountered (shown as a silhouette / "?" entry)
  seen     - met in battle but not bonded
  bonded   - caught or owned at some point

Completion counts only *bondable* species, so 100% is actually reachable - the
boss (Nullith) can be seen but never bonded, so it's excluded from the bonded
denominator (it still counts toward "seen").

Written by LJ "HawaiizFynest" Eblacas
"""

from .data import SPECIES, weaknesses, resistances

# Species that can be encountered but never bonded (kept out of the bonded
# completion denominator so the dex can reach 100%). The boss guardian only.
UNBONDABLE = frozenset({"nullith"})

UNKNOWN = "unknown"
SEEN = "seen"
BONDED = "bonded"


def order():
    """Stable display order for the dex - the curated SPECIES insertion order
    (starters, evolutions, wild roster, boss)."""
    return list(SPECIES.keys())


def total_species():
    return len(SPECIES)


def bondable_species():
    """Species that count toward bonded completion (excludes the boss)."""
    return [sid for sid in SPECIES if sid not in UNBONDABLE]


def entry_status(save, species_id):
    if species_id in save.dex_bonded:
        return BONDED
    if species_id in save.dex_seen:
        return SEEN
    return UNKNOWN


def is_known(save, species_id):
    """Has the player at least seen this species?"""
    return species_id in save.dex_seen


def seen_count(save):
    return sum(1 for sid in SPECIES if sid in save.dex_seen)


def bonded_count(save):
    return sum(1 for sid in bondable_species() if sid in save.dex_bonded)


def bondable_total():
    return len(bondable_species())


def seen_pct(save):
    t = total_species()
    return 0.0 if t == 0 else seen_count(save) / t


def bonded_pct(save):
    t = bondable_total()
    return 0.0 if t == 0 else bonded_count(save) / t


def is_complete(save):
    """All bondable species bonded (the boss need only be seen)."""
    return bonded_count(save) >= bondable_total()


def entry_view(save, species_id):
    """A view-model for one dex entry. Hides details until the species is seen,
    so the UI can render unknown entries as silhouettes."""
    sp = SPECIES[species_id]
    st = entry_status(save, species_id)
    if st == UNKNOWN:
        return {"id": species_id, "status": st, "known": False,
                "name": "?????", "type": None, "desc": "",
                "weak": [], "resist": []}
    return {
        "id": species_id,
        "status": st,
        "known": True,
        "name": sp["name"],
        "type": sp["type"],
        "shape": sp["shape"],
        "desc": sp["desc"],
        "weak": weaknesses(sp["type"]),
        "resist": resistances(sp["type"]),
        "bondable": species_id not in UNBONDABLE,
    }
