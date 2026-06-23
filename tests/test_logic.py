"""
Spiritbound - headless logic tests.

Pure game-logic checks that run without a display or audio device. Run either
with pytest:

    pytest tests/

or directly:

    python tests/test_logic.py

Written by LJ "HawaiizFynest" Eblacas
"""

import os
import sys
import random
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402
pygame.init()
pygame.font.init()

from game import config as C  # noqa: E402
from game.data import (ELEMENTS, MOVES, SPECIES, ITEMS, SHOP_STOCK,  # noqa: E402
                       type_multiplier, stage_mult, xp_for_level, xp_yield_for,
                       weaknesses, resistances, RARE_STOCK, RARE_STOCK_RANK,
                       roll_field_find, STATUSES, WEATHER, weather_mult,
                       matchup_score, matchup_verdict,
                       move_effect_blurb, CATEGORY_NAMES,
                       SLEEP_MIN, SLEEP_MAX)
from game.entities import (Aether, Party, Inventory, GameData,  # noqa: E402
                           make_wild, make_starter, MAX_LEVEL, MAX_MOVES,
                           apply_move_choice,
                           base_agility, base_spatk, base_spdef,
                           char_xp_for_level, CHAR_MAX_LEVEL)
from game import maps as M  # noqa: E402
from game.battle import BattleState  # noqa: E402
from game import quests as Q  # noqa: E402
from game import dex as D  # noqa: E402
from game import endings as E  # noqa: E402
from game import ai as AI  # noqa: E402
from game.ui import Menu, MenuItem  # noqa: E402


# ---------------------------------------------------------------------------
# Type chart & helpers
# ---------------------------------------------------------------------------
def test_type_chart():
    assert type_multiplier("Ember", "Verdant") == 2.0
    assert type_multiplier("Verdant", "Tide") == 2.0
    assert type_multiplier("Tide", "Ember") == 2.0
    assert type_multiplier("Bolt", "Gale") == 2.0
    assert type_multiplier("Gale", "Terra") == 2.0
    assert type_multiplier("Terra", "Bolt") == 2.0
    # resisted (reverse direction)
    assert type_multiplier("Verdant", "Ember") == 0.5
    assert type_multiplier("Bolt", "Terra") == 0.5
    # neutral across triangles and None
    assert type_multiplier("Ember", "Bolt") == 1.0
    assert type_multiplier(None, "Ember") == 1.0


def test_weakness_resistance():
    # consistency with the chart, both directions
    assert weaknesses("Ember") == ["Tide"]
    assert resistances("Ember") == ["Verdant"]
    assert weaknesses("Bolt") == ["Terra"]
    assert resistances("Gale") == ["Terra"]
    assert weaknesses(None) == [] and resistances(None) == []
    for t in ELEMENTS:
        for a in weaknesses(t):
            assert type_multiplier(a, t) == 2.0
        for a in resistances(t):
            assert type_multiplier(a, t) == 0.5


def test_stage_mult():
    assert stage_mult(0) == 1.0
    assert stage_mult(2) > 1.0
    assert stage_mult(-2) < 1.0
    assert stage_mult(6) > stage_mult(2)
    assert stage_mult(-6) < stage_mult(-2)


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------
def test_species_table():
    assert len(SPECIES) >= 18
    for sid, sp in SPECIES.items():
        assert set(("name", "type", "base", "catch", "xp_yield",
                    "learnset", "evolve", "shape", "pal", "desc")).issubset(sp)
        assert sp["type"] in ELEMENTS
        assert 4 <= len(sp["base"]) <= 5
        assert len(sp["pal"]) == 3
        assert 1 <= sp["catch"] <= 255
        # agility is exposed for every creature (derived or explicit)
        assert Aether(sid, 10).raw_stat("agi") >= 1
        for lvl, mv in sp["learnset"]:
            assert 1 <= lvl <= MAX_LEVEL
            assert mv in MOVES, f"{sid} learns unknown move {mv}"
        if sp["evolve"] is not None:
            lvl, target = sp["evolve"]
            assert target in SPECIES, f"{sid} evolves into unknown {target}"
            assert 1 <= lvl <= MAX_LEVEL


def test_moves_table():
    assert len(MOVES) >= 28
    for mid, mv in MOVES.items():
        for key in ("name", "type", "power", "acc", "mp", "cat"):
            assert key in mv, f"{mid} missing {key}"
        assert mv["type"] is None or mv["type"] in ELEMENTS
        assert 0 <= mv["acc"] <= 100
        assert mv["mp"] >= 0
        eff = mv.get("effect")
        if eff:
            assert eff["kind"] in ("heal", "heal_mp", "cure", "buff", "debuff",
                                   "poison", "status", "weather")
            assert eff.get("target") in ("self", "enemy", "ally")
            if eff["kind"] == "status":
                assert eff["status"] in STATUSES
            if eff["kind"] == "weather":
                assert eff["weather"] in WEATHER


def test_move_effect_blurb_covers_every_move():
    # every real move yields a non-empty sentence and never falls through to
    # the empty-string default (i.e. every effect kind is handled)
    for mid, mv in MOVES.items():
        blurb = move_effect_blurb(mv)
        assert blurb and blurb.endswith("."), f"{mid}: {blurb!r}"
        assert CATEGORY_NAMES[mv["cat"]] in ("Physical", "Special", "Status")


def test_move_effect_blurb_damage_and_status_defaults():
    assert move_effect_blurb(MOVES["strike"]) == "Deals damage."
    assert move_effect_blurb(MOVES["ember"]) == "Deals damage."
    # a status move with no rider effect describes itself sensibly
    bare = {"name": "Focus", "type": None, "power": 0, "acc": 100,
            "mp": 3, "cat": "status", "effect": None}
    assert move_effect_blurb(bare) == "No additional effect."


def test_move_effect_blurb_heal_and_buff_phrasing():
    assert move_effect_blurb(MOVES["bloom"]) == "Restores 50% of the user's HP."
    assert move_effect_blurb(MOVES["mend"]) == "Restores 50% of an ally's HP."
    assert move_effect_blurb(MOVES["meditate"]) == "Restores 45% of the user's MP."
    assert move_effect_blurb(MOVES["charge"]) == "Raises the user's Attack."
    # stage >= 2 reads as "Sharply"
    assert move_effect_blurb(MOVES["tailwind"]) == "Sharply raises the user's Speed."
    assert move_effect_blurb(MOVES["growl"]) == "Lowers the foe's Attack."


def test_move_effect_blurb_status_and_weather_phrasing():
    assert move_effect_blurb(MOVES["scorch"]) == "30% chance to burn the foe."
    assert move_effect_blurb(MOVES["emberveil"]) == "Burns the foe."
    assert move_effect_blurb(MOVES["staticbolt"]) == "30% chance to paralyze the foe."
    # sleep gets its own natural phrasing for both guaranteed and chance forms
    assert move_effect_blurb(MOVES["lullaby"]) == "Puts the foe to sleep."
    assert move_effect_blurb(MOVES["toxicspore"]) == "Poisons the foe."
    assert move_effect_blurb(MOVES["cleanse"]) == "Cures an ally's status condition."
    assert move_effect_blurb(MOVES["raindance"]) == "Summons rain."


def test_items_table():
    assert len(ITEMS) >= 8
    for iid, it in ITEMS.items():
        for key in ("name", "kind", "price", "desc"):
            assert key in it, f"{iid} missing {key}"
        assert it["kind"] in ("heal_hp", "heal_mp", "revive", "cure", "catch", "key",
                              "full_restore", "max_revive")
    for iid in SHOP_STOCK:
        assert iid in ITEMS
    assert "spring_key" not in SHOP_STOCK  # key item is never sold


def test_catch_items_are_cards_not_crystals():
    # #26: catch items read as "cards" to the player, never "crystal" (the dict
    # ids stay *_crystal for save compatibility, which is fine — players never see them)
    catch = [iid for iid in ITEMS if ITEMS[iid]["kind"] == "catch"]
    assert catch, "no catch items found"
    for iid in catch:
        name, desc = ITEMS[iid]["name"], ITEMS[iid]["desc"]
        assert "Card" in name, f"{iid} should be a card, got name {name!r}"
        assert "crystal" not in name.lower(), f"{iid} name still says crystal: {name!r}"
        assert "crystal" not in desc.lower(), f"{iid} desc still says crystal: {desc!r}"


def test_fatal_hit_still_plays_its_fx():
    # regression: the killing blow must not skip its hit animation. The foe's FX
    # state is dropped only when its "fell!" line shows (deferred), so the move's
    # _reveal still fires the shake/flash/damage-pop on the lethal hit.
    from game.data import MOVES
    g = _save_with([("pyrachs", 40)])
    foe = make_wild("thornkin", 4)
    foe.hp = 1
    b = BattleState(_StubApp(g), [foe], kind="wild")
    _drain(b)                                    # run the intro to the menu
    active = b.active
    move = next((m for m in active.moves
                 if MOVES[m].get("power") and MOVES[m]["acc"] >= 100), active.moves[0])
    b.shake = 0.0
    b._use_move(active, foe, move, "player")     # lethal hit lands
    assert foe.fainted
    assert id(foe) in b._fx, "foe FX dropped before the hit could animate"
    b._post_round()                              # resolve + present the 'used X!' line
    assert b.shake > 0, "fatal hit skipped its hit FX (reveal found no foe)"
    _drain(b)                                    # finish; foe leaves on its 'fell!' line
    assert b.outcome == "win"
    assert id(foe) not in b._fx


def test_creature_features_cover_all_species():
    # every species (except the bespoke hollow boss) gets a distinguishing crown,
    # and all of them render in both facings without error
    import pygame
    from game import ui
    from game.data import SPECIES
    missing = [s for s, sp in SPECIES.items()
               if sp.get("shape") != "hollow" and s not in ui._CREATURE_FEAT]
    assert not missing, f"species without distinguishing features: {missing}"
    pygame.init()
    for sid in SPECIES:
        for face in (1, -1):
            spr, B, cyc = ui._render_creature(sid, 28, face)
            assert spr.get_width() == B and B > 0


def test_creature_sprite_pipeline():
    # #27: a missing sprite -> None (procedural fallback); the fitter returns a
    # square canvas and flips horizontally to match facing.
    import pygame
    from game import ui
    pygame.init()
    assert ui._load_creature_png("not_a_real_species_xyz") is None
    img = pygame.Surface((10, 20), pygame.SRCALPHA)
    img.set_at((0, 0), (255, 0, 0, 255))      # mark one corner
    right = ui._fit_png_creature(img, 44, face=1)
    left = ui._fit_png_creature(img, 44, face=-1)
    assert right.get_size() == (44, 44) and left.get_size() == (44, 44)
    # flipping must change the pixels (the marked corner moves to the other side)
    assert pygame.image.tostring(right, "RGBA") != pygame.image.tostring(left, "RGBA")


def test_character_sprite_pipeline():
    # #28: name->slug, missing sprite -> None, fitter shape, and the id->role
    # ->procedural precedence the lookup is built on.
    import os
    import pygame
    from game import ui, assets, config as C
    pygame.init()
    assert ui._slug("Mentor Wren") == "mentor_wren"
    assert ui._slug("Tender Iris") == "tender_iris"
    assert ui._char_png_for("zz_absent_character", "down") is None
    canvas, B, cyc = ui._fit_png_char(pygame.Surface((20, 30), pygame.SRCALPHA))
    assert canvas.get_size() == (B, B) and B == int(C.TILE * 1.8)

    cdir = assets.path("sprites", "characters")
    os.makedirs(cdir, exist_ok=True)
    idp = os.path.join(cdir, "ztest_npc.png")
    rolep = os.path.join(cdir, "ztest_role.png")
    pal = ((0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0))
    try:
        red = pygame.Surface((4, 4), pygame.SRCALPHA); red.fill((255, 0, 0, 255))
        green = pygame.Surface((4, 4), pygame.SRCALPHA); green.fill((0, 255, 0, 255))
        pygame.image.save(red, idp)
        pygame.image.save(green, rolep)
        ui._char_png_cache.clear()
        # id present -> id wins over role
        spr, _, _ = ui._render_char(pal, "down", 0, key="ztest_npc", role="ztest_role")
        assert b"\xff\x00\x00\xff" in pygame.image.tostring(spr, "RGBA")
        # id absent -> falls back to role
        ui._char_png_cache.clear()
        spr2, _, _ = ui._render_char(pal, "down", 0, key="zz_absent_character", role="ztest_role")
        assert b"\x00\xff\x00\xff" in pygame.image.tostring(spr2, "RGBA")
    finally:
        for p in (idp, rolep):
            if os.path.exists(p):
                os.remove(p)
        ui._char_png_cache.clear()


def test_audio_is_safe_without_device_or_files():
    # #13: the audio plumbing never raises - no device, no track files, muted, etc.
    import game.audio as A
    A.set_volume(0.5); assert abs(A.get_volume() - 0.5) < 1e-6
    A.set_volume(9);   assert A.get_volume() == 1.0       # clamped high
    A.set_volume(-3);  assert A.get_volume() == 0.0       # clamped low
    A.set_muted(True); assert A.is_muted() is True
    assert A.toggle_muted() is False and A.is_muted() is False
    A.apply_settings(True, 0.3)
    assert A.is_muted() is True and abs(A.get_volume() - 0.3) < 1e-6
    A.apply_settings(False, 0.6)
    A.init()                                  # guarded; safe with a dummy/no device
    A.play_music("overworld"); A.play_music("overworld"); A.play_music("battle")
    A.sfx("hit"); A.sfx("levelup"); A.sfx("nope_missing")
    A.play_music(None); A.sfx(None)           # tolerate empty names
    A.stop_music()


def test_audio_settings_round_trip():
    # #13: mute/volume persist through save/load and default safely on old saves
    g = GameData()
    assert g.audio_muted is False and abs(g.audio_volume - 0.6) < 1e-6
    g.audio_muted, g.audio_volume = True, 0.25
    g2 = GameData.from_dict(g.serialize())
    assert g2.audio_muted is True and abs(g2.audio_volume - 0.25) < 1e-6
    d = g.serialize(); d.pop("audio_muted"); d.pop("audio_volume")
    g3 = GameData.from_dict(d)
    assert g3.audio_muted is False and abs(g3.audio_volume - 0.6) < 1e-6


# ---------------------------------------------------------------------------
# XP / leveling / evolution
# ---------------------------------------------------------------------------
def test_xp_curve_monotonic():
    prev = -1
    for lvl in range(1, MAX_LEVEL + 1):
        cur = xp_for_level(lvl)
        assert cur >= prev
        prev = cur


def test_xp_into_level_boundaries():
    # the animated EXP bar (#19) reads this 0..1 fraction; lock its contract
    a = make_wild("sparrk", 10)
    assert a.xp_into_level() == 0.0                 # fresh at a level start = empty
    cur, nxt = xp_for_level(10), xp_for_level(11)
    a.xp = int(cur + 0.5 * (nxt - cur))
    assert 0.45 < a.xp_into_level() < 0.55          # ~half full
    # monotonic within a level, and never reaches/exceeds 1.0 before level-up
    a.xp = cur + 1
    lo = a.xp_into_level()
    a.xp = nxt - 1
    hi = a.xp_into_level()
    assert lo < hi < 1.0
    # at max level the fraction is defined (the bar special-cases it to full)
    mx = make_wild("sparrk", MAX_LEVEL)
    assert mx.xp_into_level() == 0.0


def test_agility_stat():
    # derived from speed + shape: birds/fish are nimbler, rocks slower
    assert base_agility(SPECIES["plumage"]) > SPECIES["plumage"]["base"][3]   # bird
    assert base_agility(SPECIES["finnow"]) > SPECIES["finnow"]["base"][3]     # fish
    assert base_agility(SPECIES["pebblit"]) < SPECIES["pebblit"]["base"][3]   # rock
    # blobs default to their speed value
    assert base_agility(SPECIES["cindle"]) == SPECIES["cindle"]["base"][3]
    # leveled agility scales and is always >= 1
    a = Aether("plumage", 30)
    assert a.raw_stat("agi") >= 1
    assert Aether("plumage", 40).raw_stat("agi") > Aether("plumage", 5).raw_stat("agi")


def test_special_stats():
    # casters lean special, bruisers lean physical
    assert base_spatk(SPECIES["glimmer"]) >= SPECIES["glimmer"]["base"][1]   # wisp
    assert base_spatk(SPECIES["pebblit"]) < SPECIES["pebblit"]["base"][1]    # rock
    assert base_spdef(SPECIES["coralisk"]) >= 1
    a = Aether("glimmer", 20)
    for k in ("spatk", "spdef"):
        assert a.raw_stat(k) >= 1
    # higher-level special stats scale up
    assert Aether("glimmer", 40).raw_stat("spatk") > Aether("glimmer", 5).raw_stat("spatk")


def test_character_stats_round_trip():
    g = GameData()
    assert g.charisma == 3 and g.luck == 3 and g.insight == 3 and g.vitality == 3
    g.charisma, g.luck, g.insight, g.vitality = 7, 5, 6, 4
    g2 = GameData.from_dict(g.serialize())
    assert (g2.charisma, g2.luck, g2.insight, g2.vitality) == (7, 5, 6, 4)
    # old saves without the fields fall back to defaults
    g3 = GameData.from_dict({"party": {}, "inventory": {}})
    assert (g3.charisma, g3.luck, g3.insight, g3.vitality) == (3, 3, 3, 3)


def test_rare_items_and_finds():
    import random
    from game.menus import apply_field_item
    # rare items exist, are pricey, and are in the premium stock list
    for iid in ("full_restore", "max_revive", "aether_crystal"):
        assert iid in ITEMS and ITEMS[iid]["price"] >= 800
    assert set(RARE_STOCK) <= set(ITEMS) and RARE_STOCK_RANK >= 1
    # field finds: only valid ids or None; Luck raises the hit rate
    rng = random.Random(1)
    lo = sum(roll_field_find(0, rng) is not None for _ in range(5000))
    rng = random.Random(1)
    hi = sum(roll_field_find(10, rng) is not None for _ in range(5000))
    assert hi > lo and lo > 0
    rng = random.Random(5)
    for _ in range(1000):
        f = roll_field_find(8, rng)
        assert f is None or f in ITEMS
    # Full Restore heals HP + MP and cures status
    a = Aether("cindle", 25)
    a.hp = 1
    a.mp = 0
    a.status = "poison"
    g = GameData()
    g.inventory.add("full_restore", 1)
    msg = apply_field_item(g, "full_restore", a)
    assert msg and a.hp == a.max_hp and a.mp == a.max_mp and a.status is None
    assert g.inventory.count("full_restore") == 0
    # Max Revive brings a fainted Aether back to full
    b = Aether("driblet", 25)
    b.hp = 0
    g.inventory.add("max_revive", 1)
    assert apply_field_item(g, "max_revive", b) and b.hp == b.max_hp


def test_character_leveling():
    g = GameData()
    assert g.char_level == 1 and g.char_xp == 0
    # curve grows with level
    assert char_xp_for_level(2) > char_xp_for_level(1)
    base_cha = g.charisma
    ev = g.gain_char_xp(char_xp_for_level(1))   # exactly one level
    assert g.char_level == 2 and len(ev) == 1 and ev[0][0] == "level"
    # first level-up raises Charisma (first in the cycle)
    assert g.charisma == base_cha + 1
    # a big dump multi-levels and stays within cap
    g.gain_char_xp(100000)
    assert g.char_level == CHAR_MAX_LEVEL
    # round-trips
    g2 = GameData.from_dict(g.serialize())
    assert g2.char_level == g.char_level and g2.char_xp == g.char_xp


def test_catch_rank_gate():
    g = GameData()
    g.char_level = 1
    g.party.add(Aether("cindle", 8))
    g.inventory.add("bond_crystal", 2)
    app = _StubApp(g)
    foe = Aether("magmaw", 30)            # far above rank 1
    b = BattleState(app, [foe], kind="wild", can_catch=True)
    while b.phase == "msg":
        b._advance_message()
    consumed = b.take_item("bond_crystal")
    assert consumed is False                       # gate blocked the throw
    assert g.inventory.count("bond_crystal") == 2  # crystal not spent
    assert b.outcome is None                        # battle continues


def test_gain_xp_levels_and_evolves():
    a = Aether("cindle", 5)
    assert a.species_id == "cindle"
    # dump enough XP to blow past the evolution level (16)
    need = xp_for_level(20)
    events = a.gain_xp(need)
    kinds = [e[0] for e in events]
    assert "level" in kinds
    assert "evolve" in kinds
    assert a.species_id == "pyrachs"
    assert a.level >= 16


def test_move_cap():
    a = Aether("pyrachs", MAX_LEVEL)
    assert len(a.moves) <= 4


# ---------------------------------------------------------------------------
# Move-learning: 4-move cap replace/skip (#18)
# ---------------------------------------------------------------------------
def test_apply_move_choice_under_cap_appends():
    moves = ["strike", "ember"]
    out = apply_move_choice(moves, "flamefang", slot=None)
    assert out == ["strike", "ember", "flamefang"]   # room -> just added
    assert moves == ["strike", "ember"]              # input not mutated


def test_apply_move_choice_replaces_chosen_slot_at_cap():
    moves = ["strike", "ember", "flamefang", "screech"]
    out = apply_move_choice(moves, "inferno", slot=1)
    assert out == ["strike", "inferno", "flamefang", "screech"]  # slot 1 replaced
    assert "ember" not in out and out.count("inferno") == 1


def test_apply_move_choice_skip_leaves_moves_untouched():
    moves = ["strike", "ember", "flamefang", "screech"]
    assert apply_move_choice(moves, "inferno", slot=None) == moves


def test_apply_move_choice_known_move_is_noop():
    moves = ["strike", "ember", "flamefang", "screech"]
    assert apply_move_choice(moves, "ember", slot=2) == moves   # already known


def test_apply_move_choice_bad_slot_raises():
    moves = ["strike", "ember", "flamefang", "screech"]
    raised = False
    try:
        apply_move_choice(moves, "inferno", slot=9)
    except ValueError:
        raised = True
    assert raised


def test_gain_xp_emits_learn_at_cap_without_dropping():
    a = Aether("zephlit", 12)                 # [strike, gust, airslash, meditate]
    assert len(a.moves) == MAX_MOVES
    before = list(a.moves)
    events = a.gain_xp(xp_for_level(13) - a.xp)   # level 13 -> learns tailwind
    assert ("learn", "tailwind") in events
    assert ("move", "Tailwind") not in [(e[0], e[1] if len(e) > 1 else None) for e in events]
    assert a.moves == before                  # nothing silently dropped


def test_learn_or_replace_applies_decision():
    a = Aether("zephlit", 12)
    a.gain_xp(xp_for_level(13) - a.xp)
    # replace slot 0 (strike) with tailwind
    assert a.learn_or_replace("tailwind", 0) is True
    assert a.moves[0] == "tailwind" and "strike" not in a.moves
    # skipping a fresh candidate changes nothing
    assert a.learn_or_replace("cyclone", None) is False
    assert "cyclone" not in a.moves


def test_battle_take_learn_replace_and_skip():
    # the battle queues a cap-learn and resolves it via take_learn
    random.seed(0)
    g = GameData(); g.char_level = 30
    a = Aether("zephlit", 12)
    g.party.add(a)
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    _drain(b)
    # simulate the level-13 learn arriving from an XP award
    b._pending_learns.append((a, "tailwind"))
    b.take_learn(1)                            # replace airslash (slot 1)
    _drain(b)
    assert a.moves[1] == "tailwind" and len(a.moves) == MAX_MOVES
    assert not b._pending_learns
    # a second offer, skipped, leaves the set alone
    keep = list(a.moves)
    b._pending_learns.append((a, "cyclone"))
    b.take_learn(None)
    _drain(b)
    assert a.moves == keep and "cyclone" not in a.moves


def test_evolution_defers_cap_learn_instead_of_dropping():
    # an evolved creature at the move cap must OFFER its new move, not silently
    # drop one. cindle (->pyrachs at 16) is full at lv15, learns inferno at 18.
    a = Aether("cindle", 15)
    assert a.moves == ["strike", "ember", "flamefang", "screech"]
    before = list(a.moves)
    events = a.gain_xp(xp_for_level(19) - a.xp)
    assert ("evolve", "Cindle", "Pyrachs") in events
    assert ("learn", "inferno") in events       # deferred, not auto-applied
    assert a.moves == before                     # nothing dropped on its own
    # the player's choice still applies normally
    assert a.learn_or_replace("inferno", 3) is True
    assert a.moves == ["strike", "ember", "flamefang", "inferno"]


# ---------------------------------------------------------------------------
# Reorder a creature's moves (#20)
# ---------------------------------------------------------------------------
def test_move_to_reorders():
    a = Aether("zephlit", 12)                 # [strike, gust, airslash, meditate]
    base = list(a.moves)
    assert a.move_to(0, 2) is True            # pull strike to index 2
    assert a.moves == ["gust", "airslash", "strike", "meditate"]
    # the set of moves is preserved, only the order changed
    assert sorted(a.moves) == sorted(base)


def test_move_to_edge_cases():
    a = Aether("zephlit", 12)
    keep = list(a.moves)
    assert a.move_to(1, 1) is False           # same slot -> no-op
    assert a.move_to(0, 9) is False           # out of range -> no-op
    assert a.move_to(-1, 0) is False
    assert a.moves == keep


def test_swap_moves():
    a = Aether("zephlit", 12)
    assert a.swap_moves(0, 3) is True
    assert a.moves == ["meditate", "gust", "airslash", "strike"]
    assert a.swap_moves(2, 2) is False        # same index
    assert a.swap_moves(0, 7) is False        # out of range


def test_move_order_round_trips_through_save():
    a = Aether("zephlit", 12)
    a.move_to(3, 0)                            # meditate -> front
    order = list(a.moves)
    restored = Aether.from_dict(a.serialize())
    assert restored.moves == order             # order preserved across save/load


def test_pause_move_reorder_grab_move_drop():
    # the pause-menu reorder UI (#20): C enters reorder, A grabs, up/down slides
    # the grabbed move via swap_moves, A drops it.
    from game.menus import PauseMenuState

    class _In:
        def __init__(self, frames): self.frames, self.i = frames, -1
        def step(self): self.i += 1
        def pressed(self, a): return a in self.frames[self.i].get("press", ())
        def dir_repeat(self): return self.frames[self.i].get("dir")

    def _one(frame):
        x = _In([frame]); x.step(); return x

    g = GameData()
    a = Aether("zephlit", 12)                  # 4 moves at the cap
    g.party.add(a)
    g.party.add(make_wild("tidewyrm", 10))
    before = list(a.moves)
    ps = PauseMenuState(_StubApp(g))
    ps._build_party()

    # C enters reorder mode
    ps._update_party(_one({"press": ("menu",)}))
    assert ps.mode == "reorder"

    # grab move 0, slide it down twice (-> index 2), drop
    script = _In([
        {"press": ("confirm",)},               # grab slot 0
        {"dir": "down"},                        # -> swaps 0,1
        {"dir": "down"},                        # -> swaps 1,2
        {"press": ("confirm",)},                # drop
    ])
    for _ in range(4):
        script.step(); ps._update_reorder(script)
    assert ps._reorder_held is None
    assert a.moves[2] == before[0]             # the grabbed move moved two down
    assert a.moves[:2] == before[1:3]          # the two it passed shifted up
    assert sorted(a.moves) == sorted(before)   # nothing gained or lost

    # B exits reorder back to the party screen
    ps._update_reorder(_one({"press": ("cancel",)}))
    assert ps.mode == "party"


def test_level_cap():
    a = Aether("magmaw", 5)
    a.gain_xp(xp_for_level(MAX_LEVEL) * 4)
    assert a.level == MAX_LEVEL


# ---------------------------------------------------------------------------
# Party / inventory / save round-trip
# ---------------------------------------------------------------------------
def test_party_overflow_to_reserve():
    p = Party()
    for _ in range(Party.MAX_ACTIVE):
        assert p.add(Aether("sprigit", 4)) == "party"
    assert p.add(Aether("sprigit", 4)) == "reserve"
    assert len(p.members) == Party.MAX_ACTIVE
    assert len(p.reserve) == 1


def test_inventory_basic():
    inv = Inventory()
    inv.add("salve", 3)
    assert inv.count("salve") == 3
    assert inv.has("salve")
    inv.remove("salve")
    assert inv.count("salve") == 2
    inv.remove("salve", 5)
    assert inv.count("salve") == 0
    assert not inv.has("salve")


def test_save_round_trip():
    g = GameData()
    g.party.add(Aether("cindle", 8))
    g.party.add(make_starter("driblet"))
    g.inventory.add("bond_crystal", 4)
    g.money = 1234
    g.set_flag("got_starter_kit")
    g.map_id, g.px, g.py, g.facing = "grove", 12, 7, "left"
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "aether_test_save.json")
    g.save_to_file(path)
    h = GameData.load_from_file(path)
    assert h.money == 1234
    assert h.has_flag("got_starter_kit")
    assert (h.map_id, h.px, h.py, h.facing) == ("grove", 12, 7, "left")
    assert len(h.party.members) == 2
    assert h.party.members[0].species_id == "cindle"
    assert h.party.members[0].level == 8
    assert h.inventory.count("bond_crystal") == 4
    os.remove(path)


# ---------------------------------------------------------------------------
# Maps: shape, validation, connectivity
# ---------------------------------------------------------------------------
def test_maps_rectangular_and_valid():
    core = {"vale", "whisper", "grove", "spring"}
    assert core <= set(M.ALL_MAP_IDS), "core story maps missing"
    assert len(M.ALL_MAP_IDS) >= 4
    for mid in M.ALL_MAP_IDS:
        m = M.get_map(mid)
        widths = {len(row) for row in m.grid}
        assert len(widths) == 1, f"{mid} rows are not equal length"
        assert m.validate(opened_flags=set()) == [], f"{mid} failed validate()"


def _arrival_tiles(map_id):
    """Every tile the player can spawn on in this map (warp targets + start)."""
    tiles = []
    for src in M.ALL_MAP_IDS:
        m = M.get_map(src)
        for w in m.warps.values():
            if w["to"] == map_id:
                tiles.append((w["tx"], w["ty"]))
    if map_id == "vale":
        tiles.append((8, 8))
        tiles.append((19, 8))
    return tiles


def _flood(m, starts):
    seen = set()
    q = deque()
    for s in starts:
        if m.tile_walkable(*s):
            seen.add(s)
            q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and m.tile_walkable(*n):
                seen.add(n)
                q.append(n)
    return seen


def test_map_connectivity():
    for mid in M.ALL_MAP_IDS:
        m = M.get_map(mid)
        reach = _flood(m, _arrival_tiles(mid))
        assert reach, f"{mid}: no reachable tiles from arrivals"
        for (wx, wy) in m.warps:
            assert (wx, wy) in reach, f"{mid}: warp ({wx},{wy}) unreachable"

        def neighbour_reachable(x, y):
            return any((x + dx, y + dy) in reach
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        for n in m.npcs:
            assert neighbour_reachable(n["x"], n["y"]), \
                f"{mid}: npc {n.get('name')} unreachable"
        for ch in m.chests:
            assert neighbour_reachable(ch["x"], ch["y"]), \
                f"{mid}: chest {ch.get('item')} unreachable"


def test_warp_targets_walkable():
    for mid in M.ALL_MAP_IDS:
        m = M.get_map(mid)
        for (sx, sy), w in m.warps.items():
            dest = M.get_map(w["to"])
            assert dest.tile_walkable(w["tx"], w["ty"]), \
                f"{mid} warp -> {w['to']} lands on a wall"
            assert m.tile_walkable(sx, sy), \
                f"{mid} warp source ({sx},{sy}) is not walkable"


# ---------------------------------------------------------------------------
# Battle logic
# ---------------------------------------------------------------------------
class _StubApp:
    def __init__(self, save):
        self.save = save
        self.stack = ["overworld"]
        self.popped = False

    def pop(self):
        self.popped = True
        self.stack.pop()


def _save_with(team, **items):
    g = GameData()
    for sid, lvl in team:
        g.party.add(Aether(sid, lvl))
    for iid, n in items.items():
        g.inventory.add(iid, n)
    return g


def _best_damage_move(a):
    affordable = [m for m in a.moves
                  if MOVES[m]["mp"] <= a.mp and MOVES[m]["power"] > 0]
    if not affordable:
        return a.moves[0]
    return max(affordable, key=lambda m: MOVES[m]["power"])


def _drain(b):
    while b.phase == "msg" and not getattr(b, "_done", False):
        b._advance_message()


def _autoplay(b, cap=800):
    guard = 0
    while b.outcome is None and guard < cap and not getattr(b, "_done", False):
        guard += 1
        if b.phase == "msg":
            b._advance_message()
        elif b.phase == "menu":
            b.take_fight(_best_damage_move(b.active))
        elif b.phase == "force_swap":
            picked = False
            for i, a in enumerate(b.party.members):
                if not a.fainted:
                    b.take_swap(i, forced=True)
                    picked = True
                    break
            if not picked:
                break
        elif b.phase == "learn":
            b.take_learn(None)            # autoplay declines new moves at the cap
        elif b.phase == "swap":
            b._open_action_menu()         # decline a cancelable swap, keep fighting
        else:
            b._advance_message()
    _drain(b)
    return b.outcome


def test_battle_wild_ko_wins():
    random.seed(1)
    g = _save_with([("pyrachs", 30)], bond_crystal=10)
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    assert _autoplay(b) == "win"


def test_battle_catch_weak_foe():
    random.seed(7)
    g = _save_with([("pyrachs", 40)], bond_crystal=20)
    foe = make_wild("sparrk", 5)
    foe.hp = 1
    b = BattleState(_StubApp(g), [foe], kind="wild")
    _drain(b)
    for _ in range(10):
        if b.phase == "menu":
            b.take_item("bond_crystal")
        _drain(b)
        if b.outcome == "caught":
            break
    assert b.outcome == "caught"
    assert len(g.party.members) == 2


def test_battle_trainer_reward_and_no_flee():
    random.seed(3)
    g = _save_with([("tidewyrm", 45), ("boulderon", 45)])
    start = g.money
    app = _StubApp(g)
    b = BattleState(app, [make_wild("zephlit", 6), make_wild("magmaw", 7)],
                    kind="trainer", opponent_name="Rival Kade", reward=240,
                    on_win=lambda o: None)
    assert b.can_run is False and b.can_catch is False
    assert _autoplay(b) == "win"
    assert g.money - start == 240
    assert app.popped is True


def test_battle_loss_invokes_callback():
    random.seed(5)
    g = _save_with([("cindle", 2)])
    flag = {"lost": False}
    b = BattleState(_StubApp(g), [make_wild("nullith", 45)], kind="boss",
                    on_lose=lambda: flag.__setitem__("lost", True))
    assert _autoplay(b) == "lose"
    assert flag["lost"] is True


# ---------------------------------------------------------------------------
# Robbery + recovery (#7)
# ---------------------------------------------------------------------------
def test_rob_takes_items_and_all_but_one_creature():
    g = _save_with([("pyrachs", 10), ("boulderon", 10), ("finnow", 10)],
                   salve=3, bond_crystal=2)
    g.rob("masked_bandit")
    # bag emptied into the stash
    assert g.inventory.items == {}
    assert g.stashes["masked_bandit"]["items"] == {"salve": 3, "bond_crystal": 2}
    # exactly one creature kept, the other two stashed
    assert len(g.party.members) == 1
    assert len(g.stashes["masked_bandit"]["creatures"]) == 2
    assert g.has_stash("masked_bandit")


def test_rob_keeps_a_healthy_creature():
    g = _save_with([("pyrachs", 10), ("boulderon", 10)])
    g.party.members[0].hp = 0          # first creature is fainted
    g.rob("masked_bandit")
    assert len(g.party.members) == 1
    assert not g.party.members[0].fainted   # kept the healthy one, not the KO'd one


def test_rob_with_lone_creature_keeps_it():
    g = _save_with([("pyrachs", 10)], salve=2)
    g.rob("masked_bandit")
    assert len(g.party.members) == 1                 # never left creatureless
    assert g.stashes["masked_bandit"]["creatures"] == []
    assert g.inventory.items == {}                    # items still taken


def test_recover_stash_restores_exactly():
    g = _save_with([("pyrachs", 10), ("boulderon", 10), ("finnow", 10)],
                   salve=3, ether=1)
    before_species = sorted(a.species_id for a in g.party.members)
    g.rob("masked_bandit")
    assert g.recover_stash("masked_bandit") is True
    # bag and party are whole again
    assert g.inventory.items == {"salve": 3, "ether": 1}
    assert sorted(a.species_id for a in g.party.members) == before_species
    assert not g.has_stash("masked_bandit")
    # recovering an empty stash is a no-op
    assert g.recover_stash("masked_bandit") is False


def test_stash_round_trips_through_save():
    g = _save_with([("pyrachs", 10), ("boulderon", 10)], salve=2)
    g.rob("masked_bandit")
    g2 = GameData.from_dict(g.serialize())
    assert g2.has_stash("masked_bandit")
    assert g2.stashes["masked_bandit"]["items"] == {"salve": 2}
    assert len(g2.stashes["masked_bandit"]["creatures"]) == 1
    # and it recovers correctly after a load
    assert g2.recover_stash("masked_bandit") is True
    assert g2.inventory.items == {"salve": 2}
    assert len(g2.party.members) == 2


def test_stash_defaults_empty_and_old_save_safe():
    g = GameData()
    assert g.stashes == {} and not g.has_stash("masked_bandit")
    g3 = GameData.from_dict({"party": {}, "inventory": {}})
    assert g3.stashes == {}


def test_robber_npc_is_wired():
    # the Masked Bandit on Whisper Route is flagged as a robber with a real team
    bandit = None
    for npc in M.get_map("whisper").npcs:
        if npc.get("robber"):
            bandit = npc
            break
    assert bandit is not None, "no robber NPC found on whisper route"
    assert bandit["robber"] == "masked_bandit"
    assert bandit.get("defeat_flag")
    for sid, lvl in bandit["battle"]:
        assert sid in SPECIES


# ---------------------------------------------------------------------------
# Active-hunting trainers: sight + pursuit math (#8)
# ---------------------------------------------------------------------------
def test_sight_cone_sees_player_straight_ahead():
    # NPC at (5,5) facing down sees a player directly below within range
    assert AI.in_sight_cone(5, 5, "down", 5, 7, sight=4) is True
    assert AI.in_sight_cone(5, 5, "down", 5, 9, sight=4) is True    # depth 4 == range
    assert AI.in_sight_cone(5, 5, "down", 5, 10, sight=4) is False  # depth 5 too far
    assert AI.in_sight_cone(5, 5, "down", 5, 3, sight=4) is False   # behind


def test_sight_cone_widens_with_distance():
    # one tile ahead: must be nearly dead-ahead (lateral <= 1)
    assert AI.in_sight_cone(5, 5, "down", 6, 6, sight=4) is True    # depth1 lat1
    assert AI.in_sight_cone(5, 5, "down", 7, 6, sight=4) is False   # depth1 lat2
    # three tiles ahead: cone is wider (lateral up to 3 allowed)
    assert AI.in_sight_cone(5, 5, "down", 8, 8, sight=4) is True    # depth3 lat3
    assert AI.in_sight_cone(5, 5, "down", 9, 8, sight=4) is False   # depth3 lat4


def test_sight_cone_respects_facing():
    # facing right only sees to the right
    assert AI.in_sight_cone(5, 5, "right", 8, 5, sight=4) is True
    assert AI.in_sight_cone(5, 5, "left", 8, 5, sight=4) is False
    # the player's own tile is never a "sighting" (depth 0)
    assert AI.in_sight_cone(5, 5, "down", 5, 5, sight=4) is False


def test_step_toward_closes_larger_axis_first():
    assert AI.step_toward(0, 0, 5, 2) == (1, 0)     # x gap bigger -> step x
    assert AI.step_toward(0, 0, 2, 5) == (0, 1)     # y gap bigger -> step y
    assert AI.step_toward(0, 0, -3, 1) == (-1, 0)
    assert AI.step_toward(3, 3, 3, 3) == (0, 0)     # already there


def test_facing_toward_matches_step():
    assert AI.facing_toward(0, 0, 5, 0) == "right"
    assert AI.facing_toward(0, 0, -5, 0) == "left"
    assert AI.facing_toward(0, 0, 0, 5) == "down"
    assert AI.facing_toward(0, 0, 0, -5) == "up"


def test_hunter_npc_is_wired():
    # at least one hunting trainer exists with a sane sight range + a real team
    found = False
    for mid in M.ALL_MAP_IDS:
        for npc in M.get_map(mid).npcs:
            if npc.get("hunt"):
                found = True
                assert npc.get("battle"), f"{npc.get('name')} hunts but has no team"
                assert npc.get("defeat_flag")
                assert npc["hunt"].get("sight", 4) >= 1
    assert found, "no active-hunting trainer found on any map"


def test_hunter_spot_raises_alert_then_speaks():
    # spotting the player starts a "!" beat (turn to face them, no dialogue yet);
    # the alert dialogue fires only once the beat elapses (#8)
    from game.overworld import OverworldState

    class _App:
        def __init__(self, save): self.save, self.pushed = save, []
        def push(self, st): self.pushed.append(st)
        def pop(self): pass

    g = GameData()
    g.map_id = "whisper"            # Hiker Bem hunts here at (24, 14) facing down
    g.px, g.py, g.facing = 24, 17, "up"   # standing in his downward sight cone
    g.party.add(make_wild("sparrk", 8))
    ow = OverworldState(_App(g))
    hib = next(h for h in ow._hunters.values() if h["npc"]["name"] == "Hiker Bem")
    assert not hib["chasing"] and hib["exclaim"] == 0.0

    # the spot frame: beat starts, trainer faces the player, nothing said yet
    assert ow._update_hunters(0.0) is True
    assert hib["chasing"] and hib["exclaim"] > 0.0
    assert hib["facing"] == "down"
    assert ow.app.pushed == []

    # let the beat elapse -> exactly one alert dialogue is pushed
    for _ in range(120):
        ow._update_hunters(1 / 60)
        if ow.app.pushed:
            break
    assert hib["exclaim"] == 0.0
    assert len(ow.app.pushed) == 1


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------
def test_quest_table_integrity():
    assert Q.MAIN_QUEST_ID in Q.QUESTS
    assert Q.QUESTS[Q.MAIN_QUEST_ID]["main"] is True
    valid = ("talk", "defeat", "bond", "collect", "reach", "flag")
    for qid, q in Q.QUESTS.items():
        for key in ("title", "desc", "giver", "objectives", "rewards"):
            assert key in q, f"{qid} missing {key}"
        assert q["objectives"], f"{qid} has no objectives"
        for obj in q["objectives"]:
            assert obj["kind"] in valid, f"{qid} bad objective kind {obj['kind']}"
            assert obj.get("text")
            if obj["kind"] == "collect":
                assert obj["item"] in ITEMS
            if obj["kind"] == "bond" and obj.get("species"):
                assert obj["species"] in SPECIES
            if obj["kind"] == "reach":
                assert obj["map"] in M.ALL_MAP_IDS
        # reward items must be real
        for iid, n in q["rewards"].get("items", []):
            assert iid in ITEMS and n >= 1


def test_quest_state_defaults_and_round_trip():
    g = GameData()
    assert g.quests == {} and g.quest_step == {}
    assert Q.status(g, "main") == Q.NOT_STARTED
    Q.start(g, "main")
    assert Q.is_active(g, "main")
    g2 = GameData.from_dict(g.serialize())
    assert Q.status(g2, "main") == Q.ACTIVE
    assert Q.step_index(g2, "main") == Q.step_index(g, "main")
    # old saves without quest fields fall back cleanly
    g3 = GameData.from_dict({"party": {}, "inventory": {}})
    assert g3.quests == {} and g3.quest_step == {}


def test_quest_start_is_idempotent():
    g = GameData()
    first = Q.start(g, "pell_salves")
    assert first  # got a start message
    assert Q.start(g, "pell_salves") is None  # already active -> no-op
    assert Q.start(g, "not_a_real_quest") is None


def test_collect_quest_advances_and_rewards():
    g = GameData()
    start_coin = g.money
    Q.start(g, "pell_salves")          # collect 3 salves
    assert Q.is_active(g, "pell_salves")
    g.inventory.add("salve", 2)
    assert Q.notify(g, "collect", item="salve") == []   # not enough yet
    assert Q.is_active(g, "pell_salves")
    g.inventory.add("salve", 1)        # now at 3
    msgs = Q.notify(g, "collect", item="salve")
    assert any("complete" in m.lower() for m in msgs)
    assert Q.is_done(g, "pell_salves")
    assert g.money == start_coin + Q.QUESTS["pell_salves"]["rewards"]["coin"]


def test_bond_quest_species_specific():
    g = GameData()
    Q.start(g, "edda_finnow")          # bond a Finnow
    # bonding a non-Finnow does nothing
    g.party.add(Aether("cindle", 5))
    assert Q.notify(g, "bond", species="cindle") == []
    assert Q.is_active(g, "edda_finnow")
    # bonding a Finnow completes it
    g.party.add(Aether("finnow", 6))
    msgs = Q.notify(g, "bond", species="finnow")
    assert Q.is_done(g, "edda_finnow")
    assert g.inventory.count("greater_salve") >= 2   # reward granted


def test_main_quest_full_walkthrough():
    g = GameData()
    Q.start(g, "main")
    obj = Q.current_objective(g, "main")
    assert obj["kind"] == "flag" and obj["flag"] == "got_starter_kit"
    # step 0: got starter
    g.set_flag("got_starter_kit")
    Q.notify(g, "flag", flag="got_starter_kit")
    assert Q.current_objective(g, "main")["kind"] == "reach"
    # walk the rest of the line in order
    g.set_flag("rival1_beaten")        # set ahead; reach gates it
    Q.notify(g, "reach", map="whisper")
    Q.notify(g, "defeat", flag="rival1_beaten")
    Q.notify(g, "reach", map="grove")
    g.set_flag("ranger1_beaten")
    Q.notify(g, "defeat", flag="ranger1_beaten")
    g.inventory.add("spring_key", 1)
    Q.notify(g, "collect", item="spring_key")
    Q.notify(g, "reach", map="spring")
    g.set_flag("nullith_beaten")
    msgs = Q.notify(g, "defeat", flag="nullith_beaten")
    assert Q.is_done(g, "main")
    assert any("complete" in m.lower() for m in msgs)
    # final reward landed
    assert g.inventory.count("aether_crystal") >= 1


def test_reach_only_advances_one_step_per_event():
    # two consecutive reach objectives must not both clear on a single warp
    g = GameData()
    Q.start(g, "main")
    g.set_flag("got_starter_kit")
    Q.notify(g, "flag", flag="got_starter_kit")   # now on "reach whisper"
    before = Q.step_index(g, "main")
    Q.notify(g, "reach", map="grove")             # wrong map: no advance
    assert Q.step_index(g, "main") == before


# ---------------------------------------------------------------------------
# iDentifi
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Status conditions & weather
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Multi-creature battles (2v1, 3v1)
# ---------------------------------------------------------------------------
def test_multi_enemy_field_setup():
    g = _save_with([("pyrachs", 40)])
    b = BattleState(_StubApp(g),
                    [make_wild("thornkin", 8), make_wild("sparrk", 8)],
                    kind="wild", active_on_field=2)
    # both foes are on the field at once, none held in reserve
    assert len(b.enemies) == 2 and b.enemy_reserve == []
    # the primary-target property points at a living foe
    assert b.enemy in b.enemies and not b.enemy.fainted
    # each foe has its own animation state
    assert all(id(f) in b._fx for f in b.enemies)


def test_multi_enemy_reserve_sends_out():
    g = _save_with([("pyrachs", 45)])
    team = [make_wild("thornkin", 6), make_wild("sparrk", 6), make_wild("magmaw", 6)]
    b = BattleState(_StubApp(g), team, kind="wild", active_on_field=2)
    assert len(b.enemies) == 2 and len(b.enemy_reserve) == 1
    # everything in the encounter is seen immediately (dex), reserve included
    for f in team:
        assert f.species_id in g.dex_seen


def test_multi_enemy_target_index_redirects_when_target_faints():
    g = _save_with([("pyrachs", 45)])
    a, b_foe = make_wild("thornkin", 5), make_wild("sparrk", 5)
    bt = BattleState(_StubApp(g), [a, b_foe], kind="wild", active_on_field=2)
    _drain(bt)
    # aim at foe 1, then kill it directly; the primary-target property redirects
    bt.target_index = 1
    b_foe.hp = 0
    assert bt.enemy is a and not bt.enemy.fainted


def test_multi_enemy_autoplay_wins():
    random.seed(11)
    g = _save_with([("pyrachs", 40), ("boulderon", 40)])
    b = BattleState(_StubApp(g),
                    [make_wild("thornkin", 6), make_wild("sparrk", 6)],
                    kind="wild", active_on_field=2)
    assert _autoplay(b) == "win"
    # both foes ended up fainted/removed
    assert all(f.fainted for f in b.enemy_team)


def test_multi_enemy_catch_one_continues_battle():
    random.seed(3)
    g = _save_with([("pyrachs", 45)], bond_crystal=30)
    weak = make_wild("sparrk", 5); weak.hp = 1
    strong = make_wild("magmaw", 8)
    b = BattleState(_StubApp(g), [weak, strong], kind="wild", active_on_field=2)
    _drain(b)
    # throw crystals at the weak primary target until it's bonded
    caught = False
    for _ in range(12):
        if b.phase == "menu":
            b.target_index = b.enemies.index(weak) if weak in b.enemies else 0
            b.take_item("bond_crystal")
        _drain(b)
        if weak not in b.enemies:
            caught = True
            break
    assert caught                                  # the weak foe was bonded
    assert weak.species_id in g.dex_bonded
    assert b.outcome is None                        # the other foe keeps fighting
    assert strong in b.enemies


def test_multi_enemy_all_foes_act_in_a_round():
    # with two foes, a single fight exchange lets BOTH foes act on the player
    random.seed(2)
    g = _save_with([("boulderon", 30)])
    foes = [make_wild("voltagon", 18), make_wild("galecrest", 18)]
    b = BattleState(_StubApp(g), foes, kind="wild", active_on_field=2)
    _drain(b)
    before = b.active.hp
    # player uses a weak move; both foes should retaliate in the same round
    b.take_fight("strike", target_index=0)
    _drain(b)
    assert b.active.hp < before     # took damage from (up to) two foes


def test_single_enemy_path_unchanged():
    # the classic 1v1 still behaves exactly as before
    random.seed(1)
    g = _save_with([("pyrachs", 30)], bond_crystal=10)
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    assert len(b.enemies) == 1 and b.enemy_reserve == []
    assert _autoplay(b) == "win"


# ---------------------------------------------------------------------------
# Ally-target healing / support (player picks which party member to aid)
# ---------------------------------------------------------------------------
def test_ally_move_detection():
    # only effects whose target is "ally" route to the ally-pick step
    assert BattleState._move_targets_ally("mend")        # heal -> ally
    assert BattleState._move_targets_ally("sharemind")   # heal_mp -> ally
    assert BattleState._move_targets_ally("cleanse")     # cure -> ally
    assert not BattleState._move_targets_ally("aquaheal")  # heal -> self
    assert not BattleState._move_targets_ally("ember")     # plain damage


def _battle_with_healer(active_sid, *bench, heal_move="mend"):
    """A party whose active has the healing move; the rest sit on the bench."""
    g = GameData()
    g.char_level = 30          # high rank so the level-30 healer always obeys
    healer = Aether(active_sid, 30)
    if heal_move not in healer.moves:
        healer.moves.append(heal_move)
    g.party.add(healer)
    for sid, lvl in bench:
        g.party.add(Aether(sid, lvl))
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    _drain(b)
    return g, b


def test_ally_heal_restores_selected_benched_ally_only():
    random.seed(0)
    g, b = _battle_with_healer("marlance", ("boulderon", 30), ("pyrachs", 30),
                               heal_move="mend")
    hurt = g.party.members[1]      # the benched Boulderon
    other = g.party.members[2]
    hurt.hp = 5
    other.hp = 7
    before_other = other.hp
    b.take_fight("mend", ally_index=1)   # aim Mend at the hurt benched ally
    _drain(b)
    assert hurt.hp > 5                    # the chosen ally was healed
    assert other.hp == before_other       # the wrong ally was never touched


def test_ally_heal_can_target_the_active_creature():
    random.seed(0)
    g, b = _battle_with_healer("marlance", ("boulderon", 30), heal_move="mend")
    active = b.active
    active.hp = max(1, active.max_hp // 4)
    before = active.hp
    b.take_fight("mend", ally_index=0)   # the active creature is index 0
    _drain(b)
    assert active.hp > before


def test_ally_mp_restore_targets_chosen_ally():
    random.seed(0)
    g, b = _battle_with_healer("glimmer", ("boulderon", 30), heal_move="sharemind")
    ally = g.party.members[1]
    ally.mp = 0
    b.take_fight("sharemind", ally_index=1)
    _drain(b)
    assert ally.mp > 0


def test_ally_cleanse_cures_chosen_ally_status():
    random.seed(0)
    g, b = _battle_with_healer("saltoad", ("boulderon", 30), heal_move="cleanse")
    ally = g.party.members[1]
    ally.status = "poison"
    b.take_fight("cleanse", ally_index=1)
    _drain(b)
    assert ally.status is None


def test_ally_heal_no_op_on_fainted_target():
    # take_fight must never resurrect a fainted ally with a heal
    random.seed(0)
    g, b = _battle_with_healer("marlance", ("boulderon", 30), heal_move="mend")
    downed = g.party.members[1]
    downed.hp = 0
    assert downed.fainted
    b.take_fight("mend", ally_index=1)
    _drain(b)
    assert downed.hp == 0 and downed.fainted


# ---------------------------------------------------------------------------
# Out-of-MP auto-offer swap (#25)
# ---------------------------------------------------------------------------
def test_active_out_of_mp_predicate():
    random.seed(0)
    g = GameData(); g.char_level = 30
    a = Aether("pyrachs", 20)         # has MP-costing moves
    g.party.add(a)
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    _drain(b)
    assert any(MOVES[m]["mp"] > 0 for m in a.moves)   # sanity: it has costed moves
    a.mp = a.max_mp
    assert b._active_out_of_mp() is False              # full MP -> fine
    a.mp = 0
    assert b._active_out_of_mp() is True               # drained -> out of gas


def test_out_of_mp_predicate_false_for_free_only_movesets():
    # a creature whose only move is the 0-MP fallback is never "out of MP"
    random.seed(0)
    g = GameData(); g.char_level = 30
    a = Aether("pyrachs", 20)
    a.moves = ["strike"]              # Strike costs 0 MP
    g.party.add(a)
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    _drain(b)
    a.mp = 0
    assert b._active_out_of_mp() is False


def test_out_of_mp_offers_swap_once_with_healthy_bench():
    random.seed(0)
    g = GameData(); g.char_level = 30
    a = Aether("pyrachs", 20)
    g.party.add(a)
    g.party.add(Aether("boulderon", 20))   # healthy bench to swap to
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    _drain(b)
    a.mp = 0
    b._post_round()
    assert b.after_phase == "offer_swap"
    _drain(b)
    assert b.phase == "swap"                # opened a cancelable swap menu
    assert b._low_mp_offered is True
    # it must not nag again on the next round while still empty
    a.mp = 0
    b._post_round()
    assert b.after_phase != "offer_swap"


def test_out_of_mp_no_offer_without_a_bench():
    random.seed(0)
    g = GameData(); g.char_level = 30
    a = Aether("pyrachs", 20)
    g.party.add(a)                          # lone creature: nothing to swap to
    b = BattleState(_StubApp(g), [make_wild("thornkin", 4)], kind="wild")
    _drain(b)
    a.mp = 0
    b._post_round()
    assert b.after_phase != "offer_swap"


# ---------------------------------------------------------------------------
# Bottom-of-screen layout: menus must never spill past the screen (#22)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Switch-out recommendation scorer (#24)
# ---------------------------------------------------------------------------
def test_matchup_score_offense_and_defense():
    # Ember beats Verdant on offense AND resists it on defense -> strongly favored
    assert matchup_score("Ember", "Verdant") > 0
    assert matchup_verdict("Ember", "Verdant") == "+"
    # the mirror is strongly against
    assert matchup_score("Verdant", "Ember") < 0
    assert matchup_verdict("Verdant", "Ember") == "-"


def test_matchup_score_neutral_pair_is_blank():
    # unrelated elements (no super/weak relation either way) net to zero
    assert matchup_score("Ember", "Bolt") == 0.0
    assert matchup_verdict("Ember", "Bolt") == ""


def test_matchup_score_aggregates_multiple_foes():
    # strong vs one foe, weak vs another -> they cancel to neutral
    assert matchup_score("Ember", ["Verdant", "Tide"]) == 0.0
    assert matchup_verdict("Ember", ["Verdant", "Tide"]) == ""
    # but two favorable foes stack
    assert matchup_score("Ember", ["Verdant", "Verdant"]) > 0
    assert matchup_verdict("Ember", ["Verdant", "Verdant"]) == "+"


def test_matchup_score_handles_none_and_string():
    assert matchup_score("Ember", None) == 0.0
    assert matchup_verdict("Ember", None) == ""
    # a single string foe-type works the same as a one-element list
    assert matchup_score("Ember", "Verdant") == matchup_score("Ember", ["Verdant"])


def test_swap_verdict_reflects_current_foe():
    # With levels matched and full HP, the verdict isolates the TYPE matchup:
    # vs a Verdant foe an Ember ally is + and a Verdant ally is neutral.
    random.seed(0)
    g = GameData(); g.char_level = 30
    g.party.add(Aether("boulderon", 6))        # active (Terra)
    g.party.add(Aether("cindle", 6))           # Ember  -> good into Verdant
    g.party.add(Aether("mawbug", 6))           # Verdant -> neutral into Verdant
    b = BattleState(_StubApp(g), [make_wild("thornkin", 6)], kind="wild")
    _drain(b)
    assert b.enemy.type == "Verdant"
    assert b._swap_verdict(0) == ""                      # the active gets no tag
    assert b._swap_verdict(1) == "+"                     # Ember favored vs Verdant
    assert b._swap_verdict(2) == ""                      # Verdant mirror: neutral
    # a fainted candidate gets no tag
    g.party.members[2].hp = 0
    assert b._swap_verdict(2) == ""


def test_swap_score_rewards_a_level_edge():
    # a neutral-type candidate that badly outlevels the foe still reads as a
    # good send-in; the reverse (badly underleveled) reads as a bad one.
    random.seed(0)
    g = GameData(); g.char_level = 30
    g.party.add(Aether("boulderon", 20))       # active
    g.party.add(Aether("mawbug", 35))          # Verdant, way above a Verdant foe
    g.party.add(Aether("puffcap", 5))          # Verdant, way below
    b = BattleState(_StubApp(g), [make_wild("thornkin", 20)], kind="wild")
    _drain(b)
    assert b._swap_verdict(1) == "+"           # neutral type but big level edge
    assert b._swap_verdict(2) == "-"           # neutral type but far underleveled


def test_swap_score_penalizes_low_health():
    # a type-favored candidate that's nearly fainted should NOT read as a
    # confident send-in (the HP penalty cancels the type edge).
    random.seed(0)
    g = GameData(); g.char_level = 30
    g.party.add(Aether("boulderon", 12))       # active
    g.party.add(Aether("cindle", 12))          # Ember, favored vs Verdant foe
    b = BattleState(_StubApp(g), [make_wild("thornkin", 12)], kind="wild")
    _drain(b)
    ally = g.party.members[1]
    ally.hp = ally.max_hp                        # healthy -> the type edge shows
    assert b._swap_verdict(1) == "+"
    ally.hp = 1                                  # near-fainted -> no longer "+"
    assert b._swap_verdict(1) != "+"


def test_menus_never_overflow_bottom_of_screen():
    # mirror the tallest battle menu anchors; all must clamp on-screen
    anchors = [
        (C.SCREEN_H - 132, 5, 22, False, 5),   # action menu
        (C.SCREEN_H - 150, 4, 22, True, 4),    # move / bond menu
        (C.SCREEN_H - 170, 5, 22, True, 5),    # item menu
        (C.SCREEN_H - 200, 6, 22, True, 6),    # foe / ally / item target
        (C.SCREEN_H - 210, 6, 22, True, 6),    # swap menu
    ]
    for y, vis, size, title, n in anchors:
        items = [MenuItem(f"Row {i}", i) for i in range(n)]
        m = Menu(items, 24, y, width=360, visible=vis, size=size,
                 title="T" if title else None)
        assert m.y + m.height() <= C.SCREEN_H, \
            f"menu at anchor {y} overflows: bottom={m.y + m.height()}"
        assert m.y >= 0


def test_status_table_integrity():
    for sid, st in STATUSES.items():
        for key in ("abbr", "color", "verb", "tick", "skip_chance",
                    "sleep", "phys_cut", "catch_mult"):
            assert key in st, f"{sid} missing {key}"
        assert len(st["color"]) == 3
        assert 0.0 <= st["tick"] <= 1.0
        assert 0.0 <= st["skip_chance"] <= 1.0
    # the classics are present
    assert {"poison", "burn", "paralysis", "sleep"} <= set(STATUSES)
    assert STATUSES["burn"]["phys_cut"] < 1.0          # burn weakens physical
    assert STATUSES["poison"]["tick"] > 0              # poison ticks
    assert STATUSES["sleep"]["sleep"] is True
    assert 1 <= SLEEP_MIN <= SLEEP_MAX


def test_weather_table_and_mult():
    for wid, w in WEATHER.items():
        for key in ("name", "blurb", "boost", "weaken", "chip", "immune"):
            assert key in w
    # rain boosts Tide, weakens Ember; neutral otherwise and for None
    assert weather_mult("rain", "Tide") == 1.5
    assert weather_mult("rain", "Ember") == 0.5
    assert weather_mult("rain", "Bolt") == 1.0
    assert weather_mult(None, "Tide") == 1.0
    assert weather_mult("sandstorm", None) == 1.0


def test_status_inflict_and_immune_to_second():
    random.seed(1)
    g = _save_with([("pyrachs", 30)])
    b = BattleState(_StubApp(g), [make_wild("thornkin", 10)], kind="wild")
    _drain(b)
    foe = b.enemy
    b._inflict_status(foe, "burn")
    assert foe.status == "burn"
    # a second status can't overwrite the first
    b._inflict_status(foe, "poison")
    assert foe.status == "burn"


def test_sleep_sets_turns_and_wakes():
    random.seed(2)
    g = _save_with([("pyrachs", 30)])
    b = BattleState(_StubApp(g), [make_wild("thornkin", 10)], kind="wild")
    _drain(b)
    foe = b.enemy
    b._inflict_status(foe, "sleep")
    assert foe.status == "sleep" and foe.status_turns >= SLEEP_MIN
    # _can_act ticks the sleep counter down and eventually wakes
    woke = False
    for _ in range(SLEEP_MAX + 2):
        acted = b._can_act(foe)
        if foe.status is None:        # woke up this call
            woke = True
            assert acted is True
            break
        assert acted is False         # still asleep -> lost the turn
    assert woke


def test_paralysis_can_skip_turn():
    random.seed(0)
    g = _save_with([("pyrachs", 30)])
    b = BattleState(_StubApp(g), [make_wild("thornkin", 10)], kind="wild")
    _drain(b)
    foe = b.enemy
    foe.status = "paralysis"
    # over many rolls, at least one turn is skipped (skip_chance > 0)
    skips = sum(0 if b._can_act(foe) else 1 for _ in range(200))
    assert skips > 0


def test_burn_reduces_physical_damage():
    random.seed(3)
    g = _save_with([("boulderon", 40)])    # uses physical Terra moves
    b = BattleState(_StubApp(g), [make_wild("thornkin", 30)], kind="wild")
    _drain(b)
    user, target = b.active, b.enemy
    pebble = MOVES["pebble"]               # a physical move
    # average a batch of rolls with and without burn to beat RNG variance
    def avg_dmg():
        random.seed(99)
        return sum(b._calc_damage(user, target, pebble)[0] for _ in range(80))
    user.status = None
    clean = avg_dmg()
    user.status = "burn"
    burned = avg_dmg()
    assert burned < clean


def test_weather_scales_damage_in_battle():
    random.seed(4)
    g = _save_with([("tidewyrm", 40)])     # Tide attacker
    target = make_wild("thornkin", 30)
    torrent = MOVES["torrent"]             # a Tide move
    def avg(weather):
        b = BattleState(_StubApp(g), [make_wild("thornkin", 30)], kind="wild",
                        weather=weather)
        _drain(b)
        random.seed(7)
        return sum(b._calc_damage(b.active, b.enemy, torrent)[0] for _ in range(80))
    assert avg("rain") > avg(None) > avg("sun")   # rain boosts Tide, sun weakens it


def test_status_tick_damages_in_post_round():
    random.seed(5)
    g = _save_with([("pyrachs", 40)])
    b = BattleState(_StubApp(g), [make_wild("boulderon", 40)], kind="wild")
    _drain(b)
    b.enemy.status = "poison"
    before = b.enemy.hp
    b._post_round()
    assert b.enemy.hp < before            # poison ticked


def test_status_catch_bonus_from_table():
    random.seed(6)
    g = _save_with([("pyrachs", 40)], bond_crystal=5)
    foe = make_wild("sparrk", 5)
    foe.hp = max(1, foe.max_hp // 2)
    b = BattleState(_StubApp(g), [foe], kind="wild")
    _drain(b)
    # sleep gives the biggest catch bonus in the table
    assert STATUSES["sleep"]["catch_mult"] >= STATUSES["poison"]["catch_mult"]
    foe.status = "sleep"
    random.seed(6)
    _, shakes_sleep = b._attempt_catch("bond_crystal")
    foe.status = None
    random.seed(6)
    _, shakes_none = b._attempt_catch("bond_crystal")
    assert shakes_sleep >= shakes_none


def test_weather_clears_outside_battle():
    # weather lives on the battle only; it never touches GameData/save
    g = _save_with([("pyrachs", 20)])
    assert not hasattr(g, "weather")
    b = BattleState(_StubApp(g), [make_wild("thornkin", 6)], kind="wild",
                    weather="rain")
    assert b.weather == "rain"


def test_pause_party_pick_swap_reorders():
    # #30: from the party list, A picks a creature, move the cursor, A again
    # swaps the two -> the lead order changes
    from game.menus import PauseMenuState

    class _In:
        def __init__(self, frames): self.frames, self.i = frames, -1
        def step(self): self.i += 1
        def pressed(self, a): return a in self.frames[self.i].get("press", ())
        def dir_repeat(self): return self.frames[self.i].get("dir")

    def _one(frame):
        x = _In([frame]); x.step(); return x

    class _App:
        def __init__(self, save): self.save = save
        def pop(self): pass

    g = GameData()
    for sid, lv in [("sparrk", 10), ("tidewyrm", 12), ("cindle", 8)]:
        g.party.add(make_wild(sid, lv))
    before = [m.species_id for m in g.party.members]
    ps = PauseMenuState(_App(g))
    ps._build_party()

    ps._update_party(_one({"press": ("confirm",)}))   # pick member 0
    assert ps.swap_sel == 0
    ps.menu.index = 2                                   # move cursor to member 2
    ps._update_party(_one({"press": ("confirm",)}))    # swap 0 <-> 2
    after = [m.species_id for m in g.party.members]
    assert ps.swap_sel is None
    assert after[0] == before[2] and after[2] == before[0] and after[1] == before[1]


def test_dex_defaults_empty():
    g = GameData()
    assert g.dex_seen == set() and g.dex_bonded == set()
    assert D.seen_count(g) == 0 and D.bonded_count(g) == 0
    assert D.entry_status(g, "cindle") == D.UNKNOWN


def test_identifi_label_in_ui():
    # #31: the creature log is "iDentifi" in the UI, never "Aetherdex"
    from game.menus import PauseMenuState

    class _App:
        def __init__(self, save): self.save = save
        def pop(self): pass

    g = GameData()
    g.party.add(make_wild("sparrk", 5))
    ps = PauseMenuState(_App(g))
    labels = [it.label for it in ps.menu.items]
    assert "iDentifi" in labels
    assert "Aetherdex" not in labels
    ps._build_dex()
    assert ps.menu.title == "iDentifi"


def test_dex_see_and_bond():
    g = GameData()
    assert g.dex_see("magmaw") is True          # first sighting
    assert g.dex_see("magmaw") is False         # already seen
    assert D.entry_status(g, "magmaw") == D.SEEN
    # bonding marks it bonded AND seen, and is idempotent
    assert g.dex_bond("sparrk") is True
    assert g.dex_bond("sparrk") is False
    assert "sparrk" in g.dex_seen and "sparrk" in g.dex_bonded
    assert D.entry_status(g, "sparrk") == D.BONDED


def test_dex_bonded_implies_seen():
    g = GameData()
    g.dex_bond("driblet")
    assert D.is_known(g, "driblet")
    # a bonded species can never be merely "seen" in the status
    assert D.entry_status(g, "driblet") == D.BONDED


def test_dex_completion_excludes_boss():
    g = GameData()
    # boss is bondable-excluded: it can be seen but never counts toward bonded total
    assert "nullith" in D.UNBONDABLE
    assert "nullith" not in D.bondable_species()
    assert D.bondable_total() == D.total_species() - len(D.UNBONDABLE)
    # bond every bondable species -> dex complete even though boss isn't bonded
    for sid in D.bondable_species():
        g.dex_bond(sid)
    g.dex_see("nullith")
    assert D.is_complete(g)
    assert D.bonded_pct(g) == 1.0
    assert D.seen_count(g) == D.total_species()   # boss seen too


def test_dex_entry_view_hides_unknown():
    g = GameData()
    unk = D.entry_view(g, "galecrest")
    assert unk["known"] is False and unk["name"] == "?????" and unk["type"] is None
    g.dex_see("galecrest")
    known = D.entry_view(g, "galecrest")
    assert known["known"] is True
    assert known["name"] == SPECIES["galecrest"]["name"]
    assert known["type"] == SPECIES["galecrest"]["type"]
    # weak/resist mirror the type chart helpers
    assert known["weak"] == weaknesses(known["type"])
    assert known["resist"] == resistances(known["type"])


def test_dex_save_round_trip_and_party_backfill():
    g = GameData()
    g.dex_see("magmaw")
    g.dex_bond("cindle")
    h = GameData.from_dict(g.serialize())
    assert h.dex_seen == g.dex_seen and h.dex_bonded == g.dex_bonded
    # legacy save: a party member with no dex entry is backfilled as bonded+seen
    legacy = {"party": {"members": [Aether("thornkin", 6).serialize()]},
              "inventory": {}}
    h2 = GameData.from_dict(legacy)
    assert "thornkin" in h2.dex_bonded and "thornkin" in h2.dex_seen
    assert D.entry_status(h2, "thornkin") == D.BONDED


def test_dex_order_covers_all_species():
    order = D.order()
    assert set(order) == set(SPECIES)
    assert len(order) == len(SPECIES)


def test_quest_start_returns_announcement_even_when_first_step_auto_clears():
    # The main quest's first objective is a flag already set at grant time; start()
    # must still return the "New quest" announcement (regression: it was dropped).
    g = GameData()
    g.set_flag("got_starter_kit")
    lines = Q.start(g, "main")
    assert lines and any("new quest" in m.lower() for m in lines)
    # and it advanced past the satisfied flag step on start
    assert Q.current_objective(g, "main")["kind"] == "reach"


def test_quest_giver_offers_resolve():
    # every qid referenced by an NPC "offers" list must be a real quest
    for mid in M.ALL_MAP_IDS:
        for npc in M.get_map(mid).npcs:
            for qid in npc.get("offers", []):
                assert qid in Q.QUESTS, f"{npc.get('name')} offers unknown quest {qid}"


# ---------------------------------------------------------------------------
# Branching endings
# ---------------------------------------------------------------------------
def test_endings_table_integrity():
    assert E.DEFAULT_ENDING in E.ENDINGS
    for eid, e in E.ENDINGS.items():
        assert e["id"] == eid
        assert e["title"] and e["lines"]
        assert all(isinstance(ln, str) and ln for ln in e["lines"])


def test_endings_choose_is_total_and_defaults():
    # a fresh save (nothing done) gets the canonical restorer ending
    g = GameData()
    assert E.choose(g) == "restorer"
    assert E.choose(g) in E.ENDINGS


def _bond_fraction(g, frac):
    """Bond roughly `frac` of the bondable roster on the dex."""
    bondable = D.bondable_species()
    n = int(round(frac * len(bondable)))
    for sid in bondable[:n]:
        g.dex_bond(sid)


def test_ending_liberator_from_freeing():
    g = GameData()
    g.creatures_freed = 6      # freed more than kept
    _bond_fraction(g, 0.1)
    assert E.choose(g) == "liberator"


def test_ending_guardian_from_bonds_and_kindness():
    g = GameData()
    _bond_fraction(g, 0.6)     # broad bond
    g.kindness = 6             # and generous
    assert E.choose(g) == "guardian"


def test_ending_collector_from_full_dex():
    g = GameData()
    _bond_fraction(g, 0.8)     # nearly the whole roster
    g.kindness = 0             # but not especially kind
    assert E.choose(g) == "collector"


def test_ending_restorer_is_fallback():
    g = GameData()
    _bond_fraction(g, 0.3)     # modest bond, no strong signal either way
    g.kindness = 1
    g.creatures_freed = 0
    assert E.choose(g) == "restorer"


def test_kindness_counter_round_trip_and_quest_bump():
    g = GameData()
    assert g.kindness == 0 and g.creatures_freed == 0
    # finishing a quest bumps kindness (helping the folk of Aetheria)
    Q.start(g, "pell_salves")
    g.inventory.add("salve", 3)
    Q.notify(g, "collect", item="salve")
    assert Q.is_done(g, "pell_salves")
    assert g.kindness == 1
    # round-trips, with old-save defaults
    g.creatures_freed = 4
    h = GameData.from_dict(g.serialize())
    assert h.kindness == 1 and h.creatures_freed == 4
    h2 = GameData.from_dict({"party": {}, "inventory": {}})
    assert h2.kindness == 0 and h2.creatures_freed == 0


# ---------------------------------------------------------------------------
# Direct runner
# ---------------------------------------------------------------------------
def _run_all():
    funcs = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in funcs:
        fn()
        passed += 1
        print(f"  PASS  {fn.__name__}")
    print(f"\n{passed}/{len(funcs)} tests passed.")
    return passed == len(funcs)


if __name__ == "__main__":
    ok = _run_all()
    sys.exit(0 if ok else 1)
