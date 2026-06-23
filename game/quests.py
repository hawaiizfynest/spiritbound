"""
Spiritbound - quests.

A small, pygame-free quest system: a data table of quests (one main story line
plus optional side quests) and the rule helpers that drive them. Quest state
lives on GameData (a per-quest status + current-objective index); the helpers
here read live save state to decide when an objective is met, advance the
quest, and grant rewards.

Kept import-light (no pygame, no entities) so it unit-tests headlessly. The
overworld / battle layers call `notify(save, event, **params)` from the places
those game events already happen (battle win, bond/catch, item pickup, map
enter, talk), and `start(save, qid)` when a giver hands a quest out.

Objective kinds:
  talk    {who}            - spoke to an NPC (event "talk" with who=name)
  defeat  {flag}           - a trainer/boss whose defeat_flag is now set
  bond    {species?, n?}   - bonded an Aether (optionally a species, n times)
  collect {item, n}        - hold at least n of an item in the bag
  reach   {map}            - entered a given map
  flag    {flag}           - a GameData flag has been set

Rewards: {coin, items: [(id, n)], char_xp}.

Written by LJ "HawaiizFynest" Eblacas
"""

NOT_STARTED = "not_started"
ACTIVE = "active"
DONE = "done"


def _q(id, title, desc, giver, objectives, rewards=None, main=False):
    return {"id": id, "title": title, "desc": desc, "giver": giver,
            "objectives": objectives, "rewards": rewards or {}, "main": main}


def _o(kind, text, **params):
    o = {"kind": kind, "text": text}
    o.update(params)
    return o


# ---------------------------------------------------------------------------
# Quest table
#   The main line stages the existing story; side quests hang off townsfolk.
# ---------------------------------------------------------------------------
QUESTS = {
    # ---- main story line -------------------------------------------------
    "main": _q(
        "main", "The Hollow Spring",
        "Aetheria's Spring has gone quiet and its guardian fallen hollow. "
        "Mend the bond.",
        "Mentor Wren", main=True,
        objectives=[
            _o("flag", "Choose your first Aether from Mentor Wren.",
               flag="got_starter_kit"),
            _o("reach", "Travel north to Whisper Route.", map="whisper"),
            _o("defeat", "Best Rival Kade on the route.", flag="rival1_beaten"),
            _o("reach", "Press on into the Hollow Grove.", map="grove"),
            _o("defeat", "Get past Ranger Sela at the grove.",
               flag="ranger1_beaten"),
            _o("collect", "Find the Spring Key, lost in the grove.",
               item="spring_key", n=1),
            _o("reach", "Climb through the sealed gate to the Aether Spring.",
               map="spring"),
            _o("defeat", "Soothe the hollow guardian, Nullith.",
               flag="nullith_beaten"),
        ],
        rewards={"coin": 1000, "char_xp": 80,
                 "items": [("aether_crystal", 1)]},
    ),

    # ---- side quests -----------------------------------------------------
    "kade_starter_lesson": _q(
        "kade_starter_lesson", "First Bonds",
        "Rival Kade dared you to bond a wild Aether of your own.",
        "Rival Kade",
        objectives=[
            _o("bond", "Bond any wild Aether.", n=1),
        ],
        rewards={"coin": 150, "items": [("prime_crystal", 1)]},
    ),

    "edda_finnow": _q(
        "edda_finnow", "A Catch for Gran",
        "Gran Edda misses the Finnow that once crowded the Vale pond. "
        "Bond one for her to admire.",
        "Gran Edda",
        objectives=[
            _o("bond", "Bond a Finnow.", species="finnow", n=1),
        ],
        rewards={"coin": 200, "items": [("greater_salve", 2)]},
    ),

    "pell_salves": _q(
        "pell_salves", "Stocking the Pack",
        "Fisher Pell says no bonder should head up the route empty-handed. "
        "Carry a few Salves.",
        "Fisher Pell",
        objectives=[
            _o("collect", "Hold 3 Salves.", item="salve", n=3),
        ],
        rewards={"coin": 120, "char_xp": 20},
    ),
}

MAIN_QUEST_ID = "main"


# ---------------------------------------------------------------------------
# State helpers (operate on GameData via its quest accessors)
# ---------------------------------------------------------------------------
def status(save, qid):
    return save.quests.get(qid, NOT_STARTED)


def is_active(save, qid):
    return status(save, qid) == ACTIVE


def is_done(save, qid):
    return status(save, qid) == DONE


def step_index(save, qid):
    return save.quest_step.get(qid, 0)


def current_objective(save, qid):
    """The objective dict the player is working on, or None if done/not started."""
    if status(save, qid) != ACTIVE:
        return None
    objs = QUESTS[qid]["objectives"]
    i = step_index(save, qid)
    return objs[i] if 0 <= i < len(objs) else None


def start(save, qid):
    """Begin a quest if it hasn't started. Returns the start message lines, or
    None if the quest is unknown or already started/done.

    After starting, immediately advances past any leading objective whose
    *live-state* condition is already satisfied (a `flag`/`collect`/`bond`/
    `defeat` first step). Event-only objectives (`reach`/`talk`) cannot clear on
    start - they need their own `notify(...)` from the matching game event.
    """
    if qid not in QUESTS or status(save, qid) != NOT_STARTED:
        return None
    save.quests[qid] = ACTIVE
    save.quest_step[qid] = 0
    msgs = [f"New quest: {QUESTS[qid]['title']}"]
    msgs += _advance_while_met(save, qid)
    return msgs


# ---------------------------------------------------------------------------
# Objective evaluation
# ---------------------------------------------------------------------------
def _bonded_count(save, species=None):
    n = 0
    for a in list(save.party.members) + list(save.party.reserve):
        if species is None or a.species_id == species:
            n += 1
    return n


def _objective_met(save, obj, event):
    """Is this objective satisfied, given live state and the latest event?"""
    kind = obj["kind"]
    if kind == "flag":
        return save.has_flag(obj["flag"])
    if kind == "defeat":
        return save.has_flag(obj["flag"])
    if kind == "collect":
        return save.inventory.count(obj["item"]) >= obj.get("n", 1)
    if kind == "bond":
        return _bonded_count(save, obj.get("species")) >= obj.get("n", 1)
    if kind == "reach":
        return event.get("event") == "reach" and event.get("map") == obj["map"]
    if kind == "talk":
        return event.get("event") == "talk" and event.get("who") == obj["who"]
    return False


def _advance_while_met(save, qid, event=None):
    """Advance a quest past every objective currently met; grant rewards if it
    finishes. Returns a list of message strings."""
    event = event or {}
    msgs = []
    objs = QUESTS[qid]["objectives"]
    while is_active(save, qid):
        i = step_index(save, qid)
        if i >= len(objs):
            break
        if not _objective_met(save, objs[i], event):
            break
        save.quest_step[qid] = i + 1
        # 'reach'/'talk' fire only on their own event; clear it so we don't
        # advance two such objectives on one trigger.
        if objs[i]["kind"] in ("reach", "talk"):
            event = {}
        if save.quest_step[qid] >= len(objs):
            save.quests[qid] = DONE
            msgs += _grant(save, qid)
    return msgs


def _grant(save, qid):
    """Apply a finished quest's rewards. Returns message strings."""
    from .data import ITEMS
    q = QUESTS[qid]
    r = q["rewards"]
    # finishing a quest is an act of helping the folk of Aetheria
    save.kindness = getattr(save, "kindness", 0) + 1
    msgs = [f"Quest complete: {q['title']}!"]
    got = []
    if r.get("coin"):
        save.money += r["coin"]
        got.append(f"{r['coin']} coin")
    for iid, n in r.get("items", []):
        save.inventory.add(iid, n)
        got.append(ITEMS[iid]["name"] + (f" x{n}" if n > 1 else ""))
    if r.get("char_xp"):
        # GameData.gain_char_xp returns level-up events; surface them simply.
        for _, lvl, stat in save.gain_char_xp(r["char_xp"]):
            msgs.append(f"You reached Trainer Lv {lvl}!")
        got.append(f"{r['char_xp']} Trainer EXP")
    if got:
        msgs.append("Reward: " + ", ".join(got) + ".")
    return msgs


def notify(save, event, **params):
    """Tell the quest system something happened, then advance any active quest
    whose current objective is now met. Returns a list of message strings (may
    be empty). `event` is a short kind string ('reach', 'talk', 'bond',
    'defeat', 'collect', 'flag'); params carry detail (map=, who=, ...)."""
    ev = {"event": event}
    ev.update(params)
    msgs = []
    for qid in QUESTS:
        if is_active(save, qid):
            msgs += _advance_while_met(save, qid, ev)
    return msgs


def active_quests(save):
    return [qid for qid in QUESTS if is_active(save, qid)]


def completed_quests(save):
    return [qid for qid in QUESTS if is_done(save, qid)]
