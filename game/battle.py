"""
Spiritbound - battle.

A turn-based encounter screen in the Final-Fantasy mould: pick Fight / Bond /
Item / Swap / Run, abilities cost MP, buffs and debuffs and poison matter, and
the party can be swapped. Wild battles can be fled or bonded (caught); trainer
and boss battles can be neither.

The turn *logic* (damage, status, catch, XP) lives in plain methods that mutate
state and append narration strings, so it can be unit-tested headlessly without
any input or rendering. The State wrapper drives those methods from menus.

Written by LJ "HawaiizFynest" Eblacas
"""

import math
import random
import pygame

from . import config as C
from . import audio
from .core import State, draw_text, draw_panel, draw_bar, get_font
from .ui import (draw_creature, hp_color, draw_type_badge, draw_move_card,
                 draw_xp_bar, Textbox, Menu, MenuItem, draw_trainer, NPC_PALETTES)
from .entities import MAX_LEVEL
from .data import (MOVES, ITEMS, SPECIES, type_multiplier, xp_yield_for, weaknesses,
                   roll_field_find, STATUSES, WEATHER, SLEEP_MIN, SLEEP_MAX, weather_mult,
                   matchup_score)

_STAT_LABEL = {"atk": "Attack", "def": "Defense", "spd": "Speed"}


class BattleState(State):
    opaque = True
    music = "battle"

    def __init__(self, app, enemy_team, kind="wild", opponent_name=None,
                 can_catch=None, can_run=None, reward=0,
                 on_win=None, on_lose=None, intro_lines=None, trainer=None,
                 weather=None, active_on_field=1):
        super().__init__(app)
        self.party = app.save.party
        self.inventory = app.save.inventory
        self.enemy_team = list(enemy_team)
        # Split the roster into foes on the field now and a reserve queue that is
        # sent out as active foes faint. active_on_field=1 reproduces the classic
        # one-at-a-time battle exactly.
        n_field = max(1, min(active_on_field, len(self.enemy_team)))
        self.enemies = self.enemy_team[:n_field]
        self.enemy_reserve = self.enemy_team[n_field:]
        for foe in self.enemies:
            foe.reset_battle()
        self.target_index = 0          # which active foe the player is aiming at
        self._ally_target = None        # party member an ally-target move is aimed at
        # iDentifi: every foe in this encounter is now "seen"
        for foe in self.enemy_team:
            app.save.dex_see(foe.species_id)
        self.kind = kind
        self.opponent_name = opponent_name or ("Foe" if kind != "trainer" else "Trainer")
        self.can_catch = (kind == "wild") if can_catch is None else can_catch
        self.can_run = (kind == "wild") if can_run is None else can_run
        self.reward = reward
        self.on_win = on_win
        self.on_lose = on_lose
        self.weather = weather if weather in WEATHER else None

        idx = self.party.first_healthy_index()
        self.active_index = idx if idx is not None else 0
        self.active = self.party.members[self.active_index]
        self.active.reset_battle()
        self.participants = {self.active_index}

        self.run_attempts = 0
        self.outcome = None          # None | win | lose | caught | ran
        self.need_swap = False
        self._low_mp_offered = False   # so the out-of-MP swap prompt fires once
        self._pending_learns = []      # (aether, move_id) move-learn choices to resolve
        self.bob_t = 0.0
        self.flash = 0.28

        # message system
        self.msg_queue = []
        self.msgbox = None
        self.after_phase = "menu"
        self.phase = "msg"

        # menus (built lazily per phase)
        self.menu = None

        # ---- presentation / animation state ----
        self.disp_p = float(self.active.hp)
        self.show_p = self.active.hp      # value the player HP bar animates toward
        self._id_p = id(self.active)
        # animated EXP bar (#19): disp eases toward show; on level-up the bar
        # fills to full, rolls over, and continues toward the new fraction
        self.disp_xp = self.active.xp_into_level()
        self.show_xp = self.active.xp_into_level()   # target fraction
        self._xp_level = self.active.level           # level the target belongs to
        self._xp_disp_level = self.active.level      # level the bar is filling within
        self._xp_id = id(self.active)
        # per-foe animation state, keyed by id(foe): disp/show HP + flash/lunge
        self._fx = {}
        for foe in self.enemies:
            self._init_fx(foe)
        self.shake = 0.0
        self.flash_p = 0.0
        self.lunge_p = 0.0
        self.dmg_pops = []
        self._scene = pygame.Surface((C.VIEW_W_PX, C.VIEW_H_PX))

        # trainer battle sprite: shown during the intro, then sends out its Aether
        self.trainer_pal = NPC_PALETTES.get(trainer) if (trainer and kind == "trainer") else None
        self.reveal = 0.0 if self.trainer_pal is not None else 1.0
        self._revealing = False

        if intro_lines is None:
            foe_desc = self._foe_phrase()
            if kind == "wild":
                intro_lines = [f"A wild {foe_desc} appeared!"]
            elif kind == "boss":
                intro_lines = [f"{foe_desc} looms before you!"]
            else:
                intro_lines = [f"{self.opponent_name} sent out {foe_desc}!"]
        if self.trainer_pal is not None:
            for ln in intro_lines[:-1]:
                self.msg(ln)
            self.msg(intro_lines[-1], on_show=self._send_out)   # last line reveals the Aether
        else:
            for ln in intro_lines:
                self.msg(ln)
        if self.weather:
            self.msg(WEATHER[self.weather]["blurb"])
        self.after_phase = "menu"
        self._start_drain()

    # ----- field / target helpers -----
    def _init_fx(self, foe):
        self._fx[id(foe)] = {"disp": float(foe.hp), "show": foe.hp,
                             "flash": 0.0, "lunge": 0.0}

    def _foe_phrase(self):
        """Name(s) of the foes on the field, for the intro line."""
        names = [f.name for f in self.enemies]
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return ", ".join(names[:-1]) + f", and {names[-1]}"

    @property
    def enemy(self):
        """The current primary target: the aimed-at foe if alive, else the first
        living foe. Keeps all single-enemy code and tests working unchanged."""
        live = [f for f in self.enemies if not f.fainted]
        if not live:
            return self.enemies[0] if self.enemies else None
        if 0 <= self.target_index < len(self.enemies):
            t = self.enemies[self.target_index]
            if not t.fainted:
                return t
        return live[0]

    def _living_enemies(self):
        return [f for f in self.enemies if not f.fainted]

    # ----- enter -----
    def enter(self):
        pass

    # =====================================================================
    # Messaging
    # =====================================================================
    def msg(self, text, on_show=None):
        self.msg_queue.append((text, on_show))

    def _present_front(self):
        text, cb = self.msg_queue[0]
        self.msgbox = Textbox(text)
        if cb:
            cb()

    def _start_drain(self):
        if self.msg_queue:
            self.phase = "msg"
            self._present_front()
        else:
            self._enter_after()

    def _advance_message(self):
        if self.msg_queue:
            self.msg_queue.pop(0)
        if self.msg_queue:
            self._present_front()
        else:
            self.msgbox = None
            self._enter_after()

    def _enter_after(self):
        # resolve any queued move-learn choices first - they must happen before
        # the battle ends or hands control back to the action menu
        if self._pending_learns:
            self._open_learn_menu(*self._pending_learns[0])
            return
        ph = self.after_phase
        if ph == "end":
            self._finish()
        elif ph == "force_swap":
            self._open_swap(forced=True)
        elif ph == "offer_swap":
            # out-of-MP courtesy prompt: a cancelable swap (decline -> fight on)
            self._open_swap(forced=False)
        else:
            self._open_action_menu()

    # =====================================================================
    # Combat logic (pure-ish; appends to msg_queue, mutates state)
    # =====================================================================
    def _calc_damage(self, user, target, mv):
        level = user.level
        if mv.get("cat") == "spec":
            atk = user.battle_stat_as("spatk", "atk")
            dfn = max(1, target.battle_stat_as("spdef", "def"))
        else:
            atk = user.battle_stat("atk")
            dfn = max(1, target.battle_stat("def"))
        power = mv["power"]
        base = (((2 * level / 5 + 2) * power * atk / dfn) / 50) + 2
        stab = 1.5 if (mv["type"] is not None and mv["type"] == user.type) else 1.0
        eff = type_multiplier(mv["type"], target.type)
        wx = weather_mult(self.weather, mv["type"])
        # burn saps the strength of physical attacks
        burn = STATUSES["burn"]["phys_cut"] if (
            user.status == "burn" and mv.get("cat") != "spec") else 1.0
        crit_chance = 1 / 16 + min(0.10, user.battle_stat("agi") / 900.0)
        crit = random.random() < crit_chance
        critm = 1.5 if crit else 1.0
        rnd = random.uniform(0.85, 1.0)
        dmg = int(base * stab * eff * wx * burn * critm * rnd)
        return max(1, dmg), eff, crit

    def _stage(self, who, stat, delta, up):
        before = who.stages.get(stat, 0)
        after = max(-6, min(6, before + delta))
        who.stages[stat] = after
        if after == before:
            self.msg(f"{who.name}'s {_STAT_LABEL[stat]} won't go {'higher' if up else 'lower'}!")
        else:
            mag = "sharply " if abs(delta) >= 2 else ""
            word = "rose" if up else "fell"
            self.msg(f"{who.name}'s {_STAT_LABEL[stat]} {mag}{word}!")

    def _inflict_status(self, tgt, status_id):
        """Apply a major status if the target has none. Emits the right line."""
        if status_id not in STATUSES:
            return
        if tgt.status is not None:
            if tgt.status == status_id:
                self.msg(f"{tgt.name} is already {STATUSES[status_id]['verb'].split()[-1]}.")
            else:
                self.msg(f"It had no effect on {tgt.name}.")
            return
        tgt.status = status_id
        if STATUSES[status_id]["sleep"]:
            tgt.status_turns = random.randint(SLEEP_MIN, SLEEP_MAX)
        self.msg(f"{tgt.name} {STATUSES[status_id]['verb']}!")

    def _apply_effect(self, user, target, eff):
        kind = eff["kind"]
        where = eff.get("target")
        if where == "self":
            tgt = user
        elif where == "ally":
            # routed to the party member the player picked (active or benched);
            # falls back to the user if no ally was chosen (e.g. enemy use)
            tgt = self._ally_target if self._ally_target is not None else user
        else:
            tgt = target
        if kind == "heal":
            if tgt.fainted:
                self.msg(f"It had no effect on {tgt.name}.")
                return
            healed = tgt.heal_hp(int(tgt.max_hp * eff["pct"]))
            self.msg(f"{tgt.name} recovered {healed} HP!")
        elif kind == "heal_mp":
            amt = eff.get("value")
            if amt is None:
                amt = int(tgt.max_mp * eff.get("pct", 0.4))
            got = tgt.restore_mp(max(1, amt))
            self.msg(f"{tgt.name} channelled {got} MP!")
        elif kind == "cure":
            if tgt.status is None:
                self.msg(f"{tgt.name} has no ailment to cleanse.")
            else:
                tgt.status = None
                tgt.status_turns = 0
                self.msg(f"{tgt.name} was cleansed of its ailment!")
        elif kind == "buff":
            self._stage(tgt, eff["stat"], eff["stage"], up=True)
        elif kind == "debuff":
            self._stage(tgt, eff["stat"], eff["stage"], up=False)
        elif kind == "poison":
            # legacy effect kind, kept working: poison the target
            self._inflict_status(tgt, "poison")
        elif kind == "status":
            if random.random() <= eff.get("chance", 1.0):
                self._inflict_status(tgt, eff["status"])
        elif kind == "weather":
            wid = eff["weather"]
            if self.weather == wid:
                self.msg(f"The {WEATHER[wid]['name'].lower()} is already raging.")
            else:
                self.weather = wid
                self.msg(WEATHER[wid]["blurb"])

    def _can_act(self, user):
        """Resolve sleep/paralysis before a move. Returns False (and emits a
        line) if the user loses this turn."""
        st = user.status
        if st == "sleep":
            if user.status_turns > 0:
                user.status_turns -= 1
            if user.status_turns <= 0:
                user.status = None
                self.msg(f"{user.name} woke up!")
                return True
            self.msg(f"{user.name} is fast asleep.")
            return False
        if st == "paralysis" and random.random() < STATUSES["paralysis"]["skip_chance"]:
            self.msg(f"{user.name} is paralyzed! It can't move!")
            return False
        return True

    def _use_move(self, user, target, move_id, side):
        if not self._can_act(user):
            return
        mv = MOVES[move_id]
        user.mp = max(0, user.mp - mv["mp"])
        tside = "enemy" if side == "player" else "player"
        if random.random() > mv["acc"] / 100.0:
            self.msg(f"{user.name} used {mv['name']}!")
            self.msg(f"{user.name}'s attack missed!")
            return
        if mv["power"] and mv["power"] > 0:
            dmg, eff, crit = self._calc_damage(user, target, mv)
            target.take_damage(dmg)
            audio.sfx("hit")
            # the hit (bar drain + shake + number) lands as this line appears.
            # carry the foe identity so the FX hits the right target/striker.
            foe = target if tside == "enemy" else user
            self.msg(f"{user.name} used {mv['name']}!",
                     on_show=lambda s=tside, f=foe: self._reveal(s, f))
            if crit:
                self.msg("A critical hit!")
            if eff > 1.0:
                self.msg("It's super effective!")
            elif 0 < eff < 1.0:
                self.msg("It's not very effective...")
        else:
            self.msg(f"{user.name} used {mv['name']}!")
        if mv.get("effect"):
            self._apply_effect(user, target, mv["effect"])

    def _enemy_choose_move(self, enemy, target):
        affordable = [m for m in enemy.moves if MOVES[m]["mp"] <= enemy.mp]
        if not affordable:
            return "strike"
        best, best_score = "strike", -1.0
        for m in affordable:
            mv = MOVES[m]
            if mv["power"] and mv["power"] > 0:
                eff = type_multiplier(mv["type"], target.type)
                score = mv["power"] * eff
                if mv["type"] is not None and mv["type"] == enemy.type:
                    score *= 1.5
            else:
                score = 22.0
            score *= random.uniform(0.85, 1.15)
            if score > best_score:
                best, best_score = m, score
        return best

    def _active_out_of_mp(self):
        """True when the active creature has MP-costing moves but can no longer
        afford ANY of them - it's reduced to its free fallback (e.g. Strike).
        Pure: a creature with only 0-MP moves is never 'out of MP'."""
        a = self.active
        if a is None or a.fainted:
            return False
        costed = [m for m in a.moves if MOVES[m]["mp"] > 0]
        if not costed:
            return False
        return all(MOVES[m]["mp"] > a.mp for m in costed)

    def _has_swap_option(self):
        """A healthy benched creature the player could switch to."""
        for i, a in enumerate(self.party.members):
            if i != self.active_index and not a.fainted:
                return True
        return False

    def _fight_exchange(self, player_move, target=None):
        # obedience: a creature far above your trainer rank may not listen
        disobey = False
        over = self.active.level - (getattr(self.app.save, "char_level", 1) + 5)
        if over > 0 and random.random() < min(0.25, 0.05 * over):
            disobey = True

        # build the turn order across the player's active + every living foe,
        # sorted fastest-first with a small jitter to break ties fairly.
        combatants = []
        if not disobey:
            combatants.append(("p", self.active, player_move))
        for foe in self._living_enemies():
            combatants.append(("e", foe, None))   # foe picks its move when it acts
        combatants.sort(key=lambda c: c[1].battle_stat("spd") + random.uniform(0, 0.5),
                        reverse=True)

        if disobey:
            self.msg(f"{self.active.name} won't listen - it outranks your bond!")

        chosen_target = target if (target is not None and not target.fainted) else None
        for who, who_obj, mid in combatants:
            if self.outcome or self.active.fainted:
                break
            if who == "p":
                # the aimed-at foe may have already fallen this round; redirect
                tgt = chosen_target
                if tgt is None or tgt.fainted:
                    live = self._living_enemies()
                    if not live:
                        break
                    tgt = live[0]
                self._use_move(self.active, tgt, mid, "player")
            else:
                if who_obj.fainted:
                    continue
                en_move = self._enemy_choose_move(who_obj, self.active)
                self._use_move(who_obj, self.active, en_move, "enemy")

    def _enemy_turn_only(self):
        """Every living foe acts once (used after run-fail, item use, swap)."""
        for foe in self._living_enemies():
            if self.outcome or self.active.fainted:
                return
            en_move = self._enemy_choose_move(foe, self.active)
            self._use_move(foe, self.active, en_move, "enemy")

    def _try_run(self):
        self.run_attempts += 1
        p = self.active.battle_stat("spd")
        e = max(1, self.enemy.battle_stat("spd"))
        if p > e:
            chance = 0.95
        else:
            chance = min(0.9, 0.45 + 0.15 * self.run_attempts)
        return random.random() < chance

    def _attempt_catch(self, item_id):
        e = self.enemy
        rate = e.species["catch"]
        cm = ITEMS[item_id].get("catch_mult", 1.0)
        sm = STATUSES[e.status]["catch_mult"] if e.status in STATUSES else 1.0
        hp_term = (3 * e.max_hp - 2 * e.hp) / (3 * e.max_hp)
        luck = getattr(self.app.save, "luck", 0)
        lm = 1.0 + 0.03 * luck          # lucky bonders land cards more often
        score = min(1.0, (rate / 255.0) * hp_term * cm * sm * lm)
        shakes = 0
        for _ in range(4):
            if random.random() < score ** 0.25:
                shakes += 1
            else:
                break
        return shakes >= 4, shakes

    def _award_xp(self, foe=None):
        foe = foe if foe is not None else self.enemy
        base = xp_yield_for(foe.species_id, foe.level)
        insight = getattr(self.app.save, "insight", 0)
        amount = int(round(base * (1 + 0.02 * insight)))
        for idx in sorted(self.participants):
            if idx >= len(self.party.members):
                continue
            a = self.party.members[idx]
            if a.fainted:
                continue
            events = a.gain_xp(amount)
            if events:
                self.msg(f"{a.name} gained {amount} EXP.")
            for ev in events:
                if ev[0] == "level":
                    self.msg(f"{a.name} grew to Lv {ev[1]}!")
                    audio.sfx("levelup")
                elif ev[0] == "move":
                    self.msg(f"{a.name} learned {ev[1]}!")
                elif ev[0] == "learn":
                    # at the move cap: queue a player replace/skip choice
                    self.msg(f"{a.name} wants to learn {MOVES[ev[1]]['name']}!")
                    self._pending_learns.append((a, ev[1]))
                elif ev[0] == "evolve":
                    self.msg(f"{ev[1]} evolved into {ev[2]}!")
        # point the animated EXP bar at the active creature's new fraction; the
        # tween in _animate handles the fill (and roll-over on any level-up)
        self.show_xp = self.active.xp_into_level()
        self._xp_level = self.active.level

    def _award_char_xp(self, amount):
        if amount <= 0:
            return
        for _, lvl, stat in self.app.save.gain_char_xp(amount):
            self.msg(f"You reached Trainer Lv {lvl}!  ({stat.title()} rose to "
                     f"{getattr(self.app.save, stat)})")

    def _quest_bond(self, foe):
        """Surface any quest progress from bonding this Aether, as battle msgs."""
        from . import quests
        for line in quests.notify(self.app.save, "bond", species=foe.species_id):
            self.msg(line)

    # ----- turn entry points (called by menus / tests) -----
    def take_fight(self, move_id, target_index=None, ally_index=None):
        if target_index is not None and 0 <= target_index < len(self.enemies):
            target = self.enemies[target_index]
        else:
            target = self.enemy        # primary target (aimed-at / first living)
        # an ally-target support move heals/cleanses the picked party member
        if ally_index is not None and 0 <= ally_index < len(self.party.members):
            self._ally_target = self.party.members[ally_index]
        else:
            self._ally_target = None
        self._fight_exchange(move_id, target=target)
        self._ally_target = None
        self._post_round()

    def take_run(self):
        if not self.can_run:
            self.msg("You can't flee this battle!")
            self._start_drain()
            return
        if self._try_run():
            self.msg("You got away safely!")
            self.outcome = "ran"
        else:
            self.msg("You couldn't get away!")
            self._enemy_turn_only()
        self._post_round()

    def take_item(self, item_id, target_index=None):
        """Use an item. Returns True if a turn was consumed."""
        it = ITEMS[item_id]
        kind = it["kind"]
        if kind == "catch":
            if not self.can_catch:
                self.msg("The card fizzles - it won't bond this foe!")
                self._start_drain()
                return False
            foe = self.enemy        # bond the aimed-at (primary) foe
            rank = getattr(self.app.save, "char_level", 1)
            if foe.level > rank + 5:
                self.msg(f"{foe.name} is too strong for your bond rank!")
                self.msg("Raise your Trainer level to bond mightier Aethers.")
                self._start_drain()
                return False
            self.inventory.remove(item_id)
            self.msg(f"You played the {it['name']}!")
            ok, shakes = self._attempt_catch(item_id)
            for _ in range(min(shakes, 3)):
                self.msg("...")
            if ok:
                self.msg(f"Gotcha! {foe.name} was bonded!")
                audio.sfx("catch")
                dest = self.party.add(foe)
                if dest == "reserve":
                    self.msg(f"Your team is full - {foe.name} waits in reserve.")
                self._award_char_xp(foe.level * 3 + 5)
                self.app.save.dex_bond(foe.species_id)
                self._quest_bond(foe)
                # remove the bonded foe from the field
                self._remove_foe(foe)
                # only ends the battle if no foes remain (active or in reserve)
                if not self._living_enemies() and not self.enemy_reserve:
                    self.outcome = "caught"
                self._post_round()
                return True
            self.msg(f"{foe.name} broke free!")
            self._enemy_turn_only()
            self._post_round()
            return True

        # targeted items
        tgt = self.party.members[target_index] if target_index is not None else self.active
        if kind == "heal_hp":
            if tgt.fainted or tgt.hp >= tgt.max_hp:
                self.msg("It won't have any effect right now.")
                self._start_drain()
                return False
            healed = tgt.heal_hp(it["value"])
            self.inventory.remove(item_id)
            self.msg(f"{tgt.name} recovered {healed} HP.")
        elif kind == "heal_mp":
            if tgt.fainted or tgt.mp >= tgt.max_mp:
                self.msg("It won't have any effect right now.")
                self._start_drain()
                return False
            got = tgt.restore_mp(it["value"])
            self.inventory.remove(item_id)
            self.msg(f"{tgt.name} recovered {got} MP.")
        elif kind == "revive":
            if not tgt.fainted:
                self.msg("It won't have any effect right now.")
                self._start_drain()
                return False
            tgt.hp = max(1, tgt.max_hp // 2)
            self.inventory.remove(item_id)
            self.msg(f"{tgt.name} was revived!")
        elif kind == "cure":
            if tgt.status != "poison":
                self.msg("It won't have any effect right now.")
                self._start_drain()
                return False
            tgt.status = None
            self.inventory.remove(item_id)
            self.msg(f"{tgt.name} is no longer poisoned.")
        elif kind == "full_restore":
            if tgt.fainted or (tgt.hp >= tgt.max_hp and tgt.mp >= tgt.max_mp
                               and tgt.status is None):
                self.msg("It won't have any effect right now.")
                self._start_drain()
                return False
            tgt.heal_hp(tgt.max_hp)
            tgt.restore_mp(tgt.max_mp)
            tgt.status = None
            self.inventory.remove(item_id)
            self.msg(f"{tgt.name} was fully restored!")
        elif kind == "max_revive":
            if not tgt.fainted:
                self.msg("It won't have any effect right now.")
                self._start_drain()
                return False
            tgt.hp = tgt.max_hp
            self.inventory.remove(item_id)
            self.msg(f"{tgt.name} was revived to full health!")
        else:
            self.msg("Nothing happened.")
            self._start_drain()
            return False
        self._enemy_turn_only()
        self._post_round()
        return True

    def take_swap(self, index, forced=False):
        if index == self.active_index and not self.party.members[index].fainted:
            self.msg(f"{self.active.name} is already in battle!")
            self._start_drain()
            return False
        self.active_index = index
        self.active = self.party.members[index]
        self.active.reset_battle()
        self.participants.add(index)
        self.need_swap = False
        self.msg(f"Go, {self.active.name}!")
        if not forced:
            self._enemy_turn_only()
        self._post_round()
        return True

    # ----- end-of-round resolution -----
    def _post_round(self):
        # end-of-turn status ticks (poison/burn) then weather chip, for the
        # player's active and every living foe
        combatants = [(self.active, "player", None)]
        for foe in self._living_enemies():
            combatants.append((foe, "enemy", foe))
        for who, side, foe in combatants:
            if who.fainted:
                continue
            st = STATUSES.get(who.status)
            if st and st["tick"] > 0:
                dmg = max(1, int(who.max_hp * st["tick"]))
                who.take_damage(dmg)
                verb = "hurt by poison" if who.status == "poison" else "seared by its burn"
                self.msg(f"{who.name} is {verb}! (-{dmg})",
                         on_show=lambda s=side, f=foe: self._reveal(s, f))
            if who.fainted:
                continue
            self._weather_chip(who, side, foe)
        self._evaluate()
        if self.outcome:
            self.after_phase = "end"
        elif self.need_swap:
            self.after_phase = "force_swap"
        elif self._should_offer_low_mp_swap():
            self._low_mp_offered = True
            self.msg(f"{self.active.name} is out of MP for its abilities!")
            self.msg("Swap to another Aether?")
            self.after_phase = "offer_swap"
        else:
            # re-arm the prompt once the active can pay for a move again
            if not self._active_out_of_mp():
                self._low_mp_offered = False
            self.after_phase = "menu"
        self._start_drain()

    def _should_offer_low_mp_swap(self):
        return (not self._low_mp_offered
                and self._active_out_of_mp()
                and self._has_swap_option())

    def _weather_chip(self, who, side, foe=None):
        if not self.weather:
            return
        w = WEATHER[self.weather]
        if w["chip"] <= 0 or who.type in w["immune"]:
            return
        dmg = max(1, int(who.max_hp * w["chip"]))
        who.take_damage(dmg)
        self.msg(f"{who.name} is buffeted by the {w['name'].lower()}! (-{dmg})",
                 on_show=lambda s=side, f=foe: self._reveal(s, f))

    def _remove_foe(self, foe):
        """Take a foe off the field (fainted or bonded) and drop its FX state."""
        if foe in self.enemies:
            self.enemies.remove(foe)
        self._fx.pop(id(foe), None)
        self.target_index = 0

    def _evaluate(self):
        # resolve every foe that fell this round (award XP, send out reserves)
        if self.outcome not in ("caught", "ran"):
            for foe in list(self.enemies):
                if not foe.fainted:
                    continue
                tag = "Foe " if self.kind != "wild" else "The wild "
                # Defer the actual removal (which drops the foe's FX state and
                # takes it off the field) to the moment its "fell!" line is
                # shown. The killing blow's hit FX are queued earlier against
                # this same foe; removing it now would leave _reveal nothing to
                # animate, so the fatal hit would skip its lunge/shake/flash.
                self.msg(f"{tag}{foe.name} fell!",
                         on_show=lambda f=foe: self._remove_foe(f))
                self._award_xp(foe)
                # a reserve foe steps up to keep the field populated
                if self.enemy_reserve:
                    nxt = self.enemy_reserve.pop(0)
                    nxt.reset_battle()
                    self.enemies.append(nxt)
                    self._init_fx(nxt)
                    self.msg(f"{self.opponent_name} sent out {nxt.name}!")
            if not self._living_enemies() and not self.enemy_reserve:
                self.outcome = "win"
                if self.reward:
                    self.app.save.money += self.reward
                    self.msg(f"You earned {self.reward} coin!")
                self._vitality_recover()
                self._award_char_xp(sum(a.level for a in self.enemy_team) * 3 + 5)
                if self.kind == "wild":
                    found = roll_field_find(getattr(self.app.save, "luck", 0))
                    if found:
                        self.app.save.inventory.add(found, 1)
                        self.msg(f"You found a {ITEMS[found]['name']} in the grass!")
        if self.active.fainted and self.outcome is None:
            self.msg(f"{self.active.name} fainted!")
            audio.sfx("faint")
            if self.party.all_fainted():
                self.outcome = "lose"
            else:
                self.need_swap = True

    def _vitality_recover(self):
        vit = getattr(self.app.save, "vitality", 0)
        if vit <= 0:
            return
        healed = False
        for a in self.party.members:
            if not a.fainted and a.hp < a.max_hp:
                if a.heal_hp(max(1, int(a.max_hp * 0.015 * vit))) > 0:
                    healed = True
        if healed:
            self.msg("Your team catches its breath and recovers a little.")

    def _finish(self):
        self._done = True
        # poison/stage changes never persist outside battle
        for a in self.party.members:
            a.reset_battle()
        for a in self.party.reserve:
            a.reset_battle()
        self.app.pop()
        if self.outcome == "lose" and self.on_lose:
            self.on_lose()
        elif self.outcome in ("win", "caught", "ran") and self.on_win:
            self.on_win(self.outcome)

    # =====================================================================
    # Menus
    # =====================================================================
    def _open_action_menu(self):
        self.phase = "menu"
        items = [
            MenuItem("Fight", "fight"),
            MenuItem("Bond", "bond", enabled=self.can_catch),
            MenuItem("Item", "item"),
            MenuItem("Swap", "swap"),
            MenuItem("Run", "run", enabled=self.can_run),
        ]
        self.menu = Menu(items, C.SCREEN_W - 250, C.SCREEN_H - 132,
                         width=234, visible=5, size=22)

    def _open_move_menu(self):
        self.phase = "fight"
        items = []
        for m in self.active.moves:
            mv = MOVES[m]
            mp = mv["mp"]
            right = f"{mp} MP" if mp > 0 else "--"
            col = C.ELEMENT_COLORS.get(mv["type"], C.WHITE)
            items.append(MenuItem(mv["name"], m, right=right,
                                  color=col, enabled=self.active.mp >= mp))
        self.menu = Menu(items, 24, C.SCREEN_H - 150, width=360,
                         visible=4, size=22, title="Choose a move  (X: back)")

    def _battle_items(self):
        # consumables only - bond cards live under the Bond action
        return [iid for iid in ITEMS
                if ITEMS[iid].get("battle") and ITEMS[iid]["kind"] != "catch"
                and self.inventory.has(iid)]

    def _open_bond_menu(self):
        self.phase = "bond"
        ids = [iid for iid in ITEMS if ITEMS[iid]["kind"] == "catch" and self.inventory.has(iid)]
        if not ids:
            self.msg("You have no bond cards!")
            self.after_phase = "menu"
            self._start_drain()
            return
        items = [MenuItem(ITEMS[i]["name"], i, right=f"x{self.inventory.count(i)}") for i in ids]
        self.menu = Menu(items, 24, C.SCREEN_H - 150, width=360,
                         visible=4, size=22, title="Play which card?  (X: back)")

    def _open_item_menu(self):
        self.phase = "item"
        ids = self._battle_items()
        if not ids:
            self.msg("Your bag has nothing useful here.")
            self.after_phase = "menu"
            self._start_drain()
            return
        items = [MenuItem(ITEMS[i]["name"], i, right=f"x{self.inventory.count(i)}")
                 for i in ids]
        self.menu = Menu(items, 24, C.SCREEN_H - 170, width=360,
                         visible=5, size=22, title="Use which item?  (X: back)")

    def _open_target_menu(self, item_id):
        self.phase = "item_target"
        self._pending_item = item_id
        items = []
        for i, a in enumerate(self.party.members):
            tag = "FNT" if a.fainted else f"{a.hp}/{a.max_hp}"
            items.append(MenuItem(f"{a.name}", i, right=tag))
        self.menu = Menu(items, 24, C.SCREEN_H - 200, width=360,
                         visible=6, size=22, title="On which Aether?  (X: back)")

    def _swap_score(self, index):
        """Numeric send-in score for party member `index` vs. the foes on the
        field, blending three signals (higher = better):

          type     - net type matchup (data.matchup_score, ~ -2..+2 per foe)
          level    - the candidate's average level edge over the live foes
          health   - a penalty for a hurt candidate (a near-fainted creature
                     shouldn't read as a confident send-in)

        Returns None when there's nothing to judge (the active creature, the
        fainted, or no living foe).
        """
        if index == self.active_index:
            return None
        a = self.party.members[index]
        if a.fainted:
            return None
        live = self._living_enemies()
        if not live:
            return None
        foe_types = [f.type for f in live]
        type_s = matchup_score(a.type, foe_types)
        # level edge: average (candidate - foe) level, capped so it informs but
        # doesn't dominate a clear type matchup (~ +/-1.5 at a 15-level gap)
        avg_gap = sum(a.level - f.level for f in live) / len(live)
        level_s = max(-1.5, min(1.5, avg_gap / 10.0))
        # health penalty: bites below half HP, steep enough near 0 that a
        # near-fainted creature never reads as a confident send-in even with a
        # clean type edge (-2.5 at 0 HP, smoothly 0 at half HP and above)
        frac = a.hp / max(1, a.max_hp)
        health_s = -2.5 * (0.5 - frac) / 0.5 if frac < 0.5 else 0.0
        return type_s + level_s + health_s

    def _swap_verdict(self, index):
        """A `+` / `-` / `''` send-in tag for party member `index`, blending the
        type matchup with level and HP (see `_swap_score`). Empty for the active
        creature, the fainted, or when there are no living foes to judge."""
        s = self._swap_score(index)
        if s is None:
            return ""
        if s >= 0.5:
            return "+"
        if s <= -0.5:
            return "-"
        return ""

    def _open_swap(self, forced=False):
        self.phase = "force_swap" if forced else "swap"
        self._swap_forced = forced
        items = []
        for i, a in enumerate(self.party.members):
            enabled = (not a.fainted) and i != self.active_index
            tag = "FNT" if a.fainted else f"Lv{a.level}  {a.hp}/{a.max_hp}"
            # matchup hint vs. the current foe(s): green GOOD / red POOR badge (#24)
            v = self._swap_verdict(i)
            badge = ("GOOD", C.GREEN) if v == "+" else ("POOR", C.RED) if v == "-" else None
            items.append(MenuItem(a.name, i, right=tag, enabled=enabled, badge=badge))
        title = "Send out which Aether?" if forced else "Swap to  (X: back)"
        self.menu = Menu(items, 24, C.SCREEN_H - 210, width=380,
                         visible=6, size=22, title=title)

    def _open_learn_menu(self, aether, mid):
        """At the move cap: pick one of the four moves to replace with `mid`,
        or skip. The new move's stats are shown by the draw layer (Desktop)."""
        self.phase = "learn"
        self._learn_aether = aether
        self._learn_move = mid
        items = []
        for i, m in enumerate(aether.moves):
            mv = MOVES[m]
            right = f"{mv['mp']} MP" if mv["mp"] > 0 else "--"
            col = C.ELEMENT_COLORS.get(mv["type"], C.WHITE)
            items.append(MenuItem(f"Replace {mv['name']}", i, right=right, color=col))
        items.append(MenuItem(f"Don't learn {MOVES[mid]['name']}", None))
        self.menu = Menu(items, 24, C.SCREEN_H - 210, width=380, visible=6, size=22,
                         title=f"Learn {MOVES[mid]['name']}?  (X: skip)")

    def take_learn(self, slot):
        """Resolve the pending move-learn choice (called by the menu / tests).
        `slot` is the move index to replace, or None to skip."""
        if not self._pending_learns:
            return
        aether, mid = self._pending_learns.pop(0)
        if slot is None:
            self.msg(f"{aether.name} did not learn {MOVES[mid]['name']}.")
        else:
            old = aether.moves[slot] if 0 <= slot < len(aether.moves) else None
            if aether.learn_or_replace(mid, slot) and old is not None:
                self.msg(f"{aether.name} forgot {MOVES[old]['name']} "
                         f"and learned {MOVES[mid]['name']}!")
            else:
                self.msg(f"{aether.name} learned {MOVES[mid]['name']}!")
        self._start_drain()   # show the result, then process the next learn / phase

    def _learn_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("cancel"):
            self.take_learn(None)            # X skips this move
        elif inp.pressed("confirm"):
            self.take_learn(self.menu.selected())

    # ----- per-phase input -----
    def _menu_nav(self, inp):
        d = inp.dir_repeat()
        if d in ("up", "down"):
            self.menu.move(d)

    def _menu_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("confirm"):
            choice = self.menu.selected()
            if choice == "fight":
                self._open_move_menu()
            elif choice == "bond":
                self._open_bond_menu()
            elif choice == "item":
                self._open_item_menu()
            elif choice == "swap":
                self._open_swap(forced=False)
            elif choice == "run":
                self.take_run()

    def _move_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("cancel"):
            self._open_action_menu()
        elif inp.pressed("confirm"):
            m = self.menu.selected()
            if MOVES[m]["mp"] > self.active.mp:
                return
            if self._move_targets_ally(m):
                self._open_ally_target_menu(m)  # pick which party member to aid
                return
            live = self._living_enemies()
            if len(live) > 1:
                self._open_foe_target_menu(m)   # pick which foe to hit
            else:
                self.take_fight(m)

    @staticmethod
    def _move_targets_ally(move_id):
        eff = MOVES[move_id].get("effect")
        return bool(eff) and eff.get("target") == "ally"

    def _open_ally_target_menu(self, move_id):
        self.phase = "ally_target"
        self._pending_move = move_id
        eff = MOVES[move_id]["effect"]
        kind = eff["kind"]
        items = []
        for i, a in enumerate(self.party.members):
            if kind in ("heal", "heal_mp") and a.fainted:
                tag, enabled = "FNT", False
            elif kind == "heal":
                tag, enabled = f"{a.hp}/{a.max_hp}", True
            elif kind == "heal_mp":
                tag, enabled = f"{a.mp}/{a.max_mp} MP", True
            elif kind == "cure":
                st = STATUSES.get(a.status)
                tag = st["abbr"] if st else "--"
                enabled = not a.fainted
            else:
                tag, enabled = f"{a.hp}/{a.max_hp}", not a.fainted
            note = "  (in battle)" if i == self.active_index else ""
            items.append(MenuItem(f"{a.name}{note}", i, right=tag, enabled=enabled))
        self.menu = Menu(items, 24, C.SCREEN_H - 200, width=380,
                         visible=6, size=22, title="Aid which Aether?  (X: back)")

    def _ally_target_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("cancel"):
            self._open_move_menu()
        elif inp.pressed("confirm"):
            idx = self.menu.selected()
            if idx is None or self.party.members[idx].fainted:
                return
            self.take_fight(self._pending_move, ally_index=idx)

    def _open_foe_target_menu(self, move_id):
        self.phase = "fight_target"
        self._pending_move = move_id
        items = []
        for i, foe in enumerate(self.enemies):
            if foe.fainted:
                continue
            tag = f"Lv{foe.level}  {foe.hp}/{foe.max_hp}"
            items.append(MenuItem(foe.name, i, right=tag))
        self.menu = Menu(items, 24, C.SCREEN_H - 200, width=360,
                         visible=6, size=22, title="Attack which foe?  (X: back)")
        # sync the on-field cursor to the menu's first choice
        first = self.menu.selected()
        if first is not None:
            self.target_index = first

    def _foe_target_input(self, inp):
        self._menu_nav(inp)
        # keep the on-field target cursor in step with the menu selection
        sel = self.menu.selected()
        if sel is not None:
            self.target_index = sel
        if inp.pressed("cancel"):
            self._open_move_menu()
        elif inp.pressed("confirm"):
            idx = self.menu.selected()
            if idx is None:
                return
            self.take_fight(self._pending_move, target_index=idx)

    def _item_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("cancel"):
            self._open_action_menu()
        elif inp.pressed("confirm"):
            iid = self.menu.selected()
            if iid is None:
                return
            self._open_target_menu(iid)

    def _bond_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("cancel"):
            self._open_action_menu()
        elif inp.pressed("confirm"):
            iid = self.menu.selected()
            if iid is not None:
                self.take_item(iid)

    def _target_input(self, inp):
        self._menu_nav(inp)
        if inp.pressed("cancel"):
            self._open_item_menu()
        elif inp.pressed("confirm"):
            idx = self.menu.selected()
            self.take_item(self._pending_item, target_index=idx)

    def _swap_input(self, inp):
        self._menu_nav(inp)
        forced = getattr(self, "_swap_forced", False)
        if inp.pressed("cancel") and not forced:
            self._open_action_menu()
        elif inp.pressed("confirm"):
            idx = self.menu.selected()
            if idx is None:
                return
            if self.party.members[idx].fainted or idx == self.active_index:
                return
            self.take_swap(idx, forced=forced)

    # =====================================================================
    # Update / draw
    # =====================================================================
    def update(self, inp, dt):
        if getattr(self, "_done", False):
            return
        self.bob_t += dt
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)
        self._animate(dt)
        if self.phase == "msg":
            if self.msgbox:
                self.msgbox.update(dt)
                if inp.pressed("confirm") or inp.pressed("cancel"):
                    r = self.msgbox.confirm()
                    if r == "done":
                        self._advance_message()
            else:
                self._enter_after()
        elif self.phase == "menu":
            self._menu_input(inp)
        elif self.phase == "fight":
            self._move_input(inp)
        elif self.phase == "fight_target":
            self._foe_target_input(inp)
        elif self.phase == "ally_target":
            self._ally_target_input(inp)
        elif self.phase == "bond":
            self._bond_input(inp)
        elif self.phase == "item":
            self._item_input(inp)
        elif self.phase == "item_target":
            self._target_input(inp)
        elif self.phase in ("swap", "force_swap"):
            self._swap_input(inp)
        elif self.phase == "learn":
            self._learn_input(inp)

    # ----- animation -----
    def _enemy_anchor(self, slot=0, n=1):
        """Position for foe `slot` of `n` on the field. One foe sits at the
        classic spot; multiples spread across the upper-right band."""
        if n <= 1:
            return C.VIEW_W_PX - 100, 86
        # spread n foes from right toward center, slightly staggered in depth
        span = 150
        right = C.VIEW_W_PX - 70
        x = right - slot * (span / max(1, n - 1)) if n > 1 else right - 30
        y = 70 + (slot % 2) * 30
        return int(x), int(y)

    def _player_anchor(self):
        return 100, C.VIEW_H_PX - 92

    def _pop(self, dmg, side, foe=None):
        if side == "enemy":
            x, y = self._anchor_for_foe(foe if foe is not None else self.enemy)
        else:
            x, y = self._player_anchor()
        self.dmg_pops.append({"x": x, "y": y - 18, "val": int(dmg), "t": 0.0})

    def _anchor_for_foe(self, foe):
        if foe in self.enemies:
            slot = self.enemies.index(foe)
        else:
            slot = 0
        return self._enemy_anchor(slot, len(self.enemies))

    def _reveal(self, side, foe=None):
        """Called as a hit's message appears: drain that bar and fire the
        impact FX (shake / flash / damage number) in sync with the text."""
        if side == "enemy":
            foe = foe if foe is not None else self.enemy
            fx = self._fx.get(id(foe))
            if fx is None:
                return
            old, fx["show"] = fx["show"], foe.hp
            if fx["show"] < old:
                fx["flash"] = 0.22
                self.lunge_p = 0.2
                self.shake = max(self.shake, 6.0)
                self._pop(old - fx["show"], "enemy", foe)
        else:
            old, self.show_p = self.show_p, self.active.hp
            if self.show_p < old:
                self.flash_p = 0.22
                # the foe that struck recoils; default to the primary target
                strike_foe = foe if foe is not None else self.enemy
                sfx = self._fx.get(id(strike_foe))
                if sfx is not None:
                    sfx["lunge"] = 0.2
                self.shake = max(self.shake, 6.0)
                self._pop(old - self.show_p, "player")

    def _send_out(self):
        """Begin sliding the trainer off and their first Aether in."""
        self._revealing = True

    def _animate(self, dt):
        if self._revealing and self.reveal < 1.0:
            self.reveal = min(1.0, self.reveal + dt / 0.35)
        if id(self.active) != self._id_p:
            self._id_p = id(self.active)
            self.disp_p = self.show_p = float(self.active.hp)
        # per-foe HP bar animation
        for foe in self.enemies:
            fx = self._fx.get(id(foe))
            if fx is None:
                self._init_fx(foe)
                fx = self._fx[id(foe)]
            if foe.hp > fx["show"]:        # heals reveal at once
                fx["show"] = foe.hp
            fx["disp"] += (fx["show"] - fx["disp"]) * min(1, dt * 7)
            if abs(fx["disp"] - fx["show"]) < 0.6:
                fx["disp"] = float(fx["show"])
            fx["flash"] = max(0.0, fx["flash"] - dt)
            fx["lunge"] = max(0.0, fx["lunge"] - dt)
        if self.active.hp > self.show_p:
            self.show_p = self.active.hp
        self.disp_p += (self.show_p - self.disp_p) * min(1, dt * 7)
        if abs(self.disp_p - self.show_p) < 0.6:
            self.disp_p = float(self.show_p)
        # animated EXP bar (#19)
        if id(self.active) != self._xp_id:
            self._xp_id = id(self.active)
            self.disp_xp = self.show_xp = self.active.xp_into_level()
            self._xp_level = self._xp_disp_level = self.active.level
        if self._xp_disp_level < self._xp_level:
            # fill toward full, then roll over into the next level
            self.disp_xp += (1.0 - self.disp_xp) * min(1, dt * 6)
            if self.disp_xp > 0.992:
                self.disp_xp = 0.0
                self._xp_disp_level += 1
        else:
            self.disp_xp += (self.show_xp - self.disp_xp) * min(1, dt * 6)
            if abs(self.disp_xp - self.show_xp) < 0.004:
                self.disp_xp = self.show_xp
        for attr in ("shake", "flash_p", "lunge_p"):
            setattr(self, attr, max(0.0, getattr(self, attr) - dt))
        for p in self.dmg_pops:
            p["t"] += dt
        self.dmg_pops = [p for p in self.dmg_pops if p["t"] < 0.9]

    @staticmethod
    def _lunge(t, dur, dx, dy):
        if t <= 0:
            return 0, 0
        s = math.sin((1 - t / dur) * math.pi)
        return dx * s, dy * s

    def _build_bg(self):
        if getattr(self, "_bg", None) is not None:
            return
        W, H = C.VIEW_W_PX, C.VIEW_H_PX
        bg = pygame.Surface((W, H))
        horizon = int(H * 0.56)
        top = (44, 52, 88)        # sky top
        mid = (84, 98, 122)       # shared horizon haze: sky-bottom == ground-top
        low = (30, 44, 38)        # ground bottom
        for y in range(H):
            if y < horizon:
                f, a, b = y / horizon, top, mid
            else:
                f, a, b = (y - horizon) / (H - horizon), mid, low
            bg.fill((int(a[0] + (b[0] - a[0]) * f),
                     int(a[1] + (b[1] - a[1]) * f),
                     int(a[2] + (b[2] - a[2]) * f)), (0, y, W, 1))
        # distant hills resting on the horizon (no seam line)
        for hx, hw, hh, col in ((70, 150, 40, (70, 84, 118)), (240, 180, 52, (60, 74, 108)),
                                (380, 140, 36, (74, 88, 122))):
            pygame.draw.ellipse(bg, col, (hx - hw // 2, horizon - hh, hw, hh * 2))
        self._bg = bg

    def _platform(self, surf, cx, cy, w, h):
        pygame.draw.ellipse(surf, (24, 30, 28), (int(cx - w / 2), int(cy - h / 2), int(w), int(h)))
        pygame.draw.ellipse(surf, (46, 58, 50),
                            (int(cx - w / 2), int(cy - h / 2), int(w), int(h * 0.55)))

    def _flash_overlay(self, surf, cx, cy, S, amt):
        if amt <= 0:
            return
        ov = pygame.Surface((int(S * 2.4), int(S * 2.4)), pygame.SRCALPHA)
        a = int(150 * min(1.0, amt / 0.22))
        pygame.draw.ellipse(ov, (255, 255, 255, a), (0, 0, int(S * 2.4), int(S * 2.4)))
        surf.blit(ov, (int(cx - S * 1.2), int(cy - S * 1.2)))

    # ----- scene (drawn at internal resolution, then upscaled) -----
    def _draw_scene(self, surf):
        bob = math.sin(self.bob_t * 2.0) * 2.5
        n = len(self.enemies)
        for slot, foe in enumerate(self.enemies):
            ex, ey = self._enemy_anchor(slot, n)
            self._platform(surf, ex, ey + 26, 86, 20)
            # trainer battle: trainer stands in until they "send out" the first Aether
            if self.trainer_pal is not None and self.reveal < 1.0 and slot == 0:
                draw_trainer(surf, self.trainer_pal, ex + self.reveal * 150, ey + 18, 52, face=-1)
            if self.reveal <= 0.0:
                continue
            fx = self._fx.get(id(foe), {"flash": 0.0, "lunge": 0.0})
            coff = (1.0 - self.reveal) * 150 if slot == 0 else 0
            ldx, ldy = self._lunge(fx["lunge"], 0.2, -14, 9)
            draw_creature(surf, foe.species_id, ex + ldx + coff, ey + ldy, 40, face=-1, bob=bob)
            self._flash_overlay(surf, ex + ldx + coff, ey + ldy, 40, fx["flash"])
            self._status_fx(surf, ex + ldx + coff, ey + ldy, 40, foe.status)
            # target cursor over the aimed-at foe (only when more than one)
            if n > 1 and slot == self.target_index and not foe.fainted:
                self._draw_target_cursor(surf, ex, ey - 34)

        px, py = self._player_anchor()
        self._platform(surf, px, py + 30, 96, 22)
        pdx, pdy = self._lunge(self.lunge_p, 0.2, 14, -9)
        draw_creature(surf, self.active.species_id, px + pdx, py + pdy, 47, face=1, bob=-bob)
        self._flash_overlay(surf, px + pdx, py + pdy, 47, self.flash_p)
        self._status_fx(surf, px + pdx, py + pdy, 47, self.active.status)
        self._draw_weather(surf)

    def _draw_target_cursor(self, surf, cx, cy):
        t = (pygame.time.get_ticks() // 200) % 2
        oy = -2 if t else 0
        pygame.draw.polygon(surf, C.ACCENT,
                            [(cx, cy + oy + 8), (cx - 7, cy + oy), (cx + 7, cy + oy)])
        pygame.draw.polygon(surf, (10, 14, 26),
                            [(cx, cy + oy + 8), (cx - 7, cy + oy), (cx + 7, cy + oy)], 1)

    def _spark(self, surf, x, y, size, col):
        pts = [(x, y - size), (x - size * 0.32, y - size * 0.15), (x + size * 0.22, y),
               (x - size * 0.22, y + size * 0.4), (x + size * 0.12, y + size * 0.72)]
        pygame.draw.lines(surf, col, False, [(int(a), int(b)) for a, b in pts], 2)

    def _status_fx(self, surf, cx, cy, S, status):
        """Animated overlay for a creature's status condition."""
        if not status:
            return
        t = self.bob_t
        if status == "burn":
            aura = pygame.Surface((int(S * 1.5), int(S * 1.1)), pygame.SRCALPHA)
            pygame.draw.ellipse(aura, (255, 120, 40, 46), aura.get_rect())
            surf.blit(aura, (int(cx - S * 0.75), int(cy - S * 0.1)))
            for i in range(5):
                ph = (t * 1.6 + i * 0.55) % 1.0
                ex = cx + math.sin(t * 2 + i * 2) * (S * 0.42)
                ey = cy + S * 0.24 - ph * S * 1.0
                r = max(1, int((1 - ph) * 4) + 1)
                col = (255, 214, 120) if i % 2 else (250, 140, 60)
                g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(g, (*col, int(220 * (1 - ph))), (r, r), r)
                surf.blit(g, (int(ex - r), int(ey - r)))
        elif status == "poison":
            aura = pygame.Surface((int(S * 1.4), int(S * 1.1)), pygame.SRCALPHA)
            pygame.draw.ellipse(aura, (120, 200, 90, 44), aura.get_rect())
            surf.blit(aura, (int(cx - S * 0.7), int(cy - S * 0.1)))
            for i in range(5):
                ph = (t * 1.15 + i * 0.5) % 1.0
                ex = cx + math.cos(t * 1.5 + i * 1.7) * (S * 0.44)
                ey = cy + S * 0.14 - ph * S * 0.9
                r = max(2, 3 + (i % 2))
                a = int(200 * (1 - ph))
                col = (200, 130, 220) if i % 2 else (150, 215, 120)
                g = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(g, (*col, a), (r + 1, r + 1), r)
                pygame.draw.circle(g, (230, 255, 230, a), (r, r), max(1, r - 1), 1)
                surf.blit(g, (int(ex - r), int(ey - r)))
        elif status == "paralysis":
            if int(t * 6) % 2 == 0:
                for i in range(2):
                    bx = cx + (-1 if i else 1) * S * 0.5
                    by = cy - S * 0.12 + i * S * 0.22
                    self._spark(surf, bx, by, S * 0.28, (245, 228, 110))
        elif status == "sleep":
            for i in range(3):
                ph = (t * 0.5 + i * 0.4) % 1.0
                zx = cx + S * 0.28 + ph * S * 0.5 + math.sin(t + i) * 3
                zy = cy - S * 0.32 - ph * S * 0.55
                f = get_font(int(10 + i * 3), bold=True)
                g = f.render("Z", True, (188, 202, 238))
                g.set_alpha(int(220 * (1 - ph)))
                surf.blit(g, (int(zx), int(zy)))

    def _draw_weather(self, surf):
        if not self.weather:
            return
        W, H, t, wid = C.VIEW_W_PX, C.VIEW_H_PX, self.bob_t, self.weather

        if wid == "rain":
            tint = pygame.Surface((W, H), pygame.SRCALPHA); tint.fill((40, 62, 112, 42))
            surf.blit(tint, (0, 0))
            for i in range(70):
                x = (i * 37 - int(t * 240)) % (W + 30)
                y = (i * 47 + int(t * 640)) % (H + 30)
                pygame.draw.line(surf, (182, 206, 240), (x, y), (x - 4, y + 11), 1)
        elif wid == "sun":
            warm = pygame.Surface((W, H), pygame.SRCALPHA); warm.fill((255, 208, 120, 34))
            surf.blit(warm, (0, 0))
            ray = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(4):
                x0 = 50 + i * 95
                pygame.draw.polygon(ray, (255, 240, 180, 16),
                                    [(x0, 0), (x0 + 26, 0), (x0 - 44, H), (x0 - 80, H)])
            surf.blit(ray, (0, 0))
            for i in range(5):
                ph = (t * 0.8 + i * 0.4) % 1.0
                if ph < 0.5:
                    sx, sy = 40 + i * 80, 30 + (i % 3) * 22
                    a = int(220 * (1 - abs(ph - 0.25) * 4))
                    if a > 0:
                        self._spark_twinkle(surf, sx, sy, a)
        elif wid == "sandstorm":
            tan = pygame.Surface((W, H), pygame.SRCALPHA); tan.fill((202, 172, 112, 48))
            surf.blit(tan, (0, 0))
            for i in range(85):
                x = (i * 29 - int(t * 520)) % (W + 40) - 20
                y = (i * 61 + int(t * 40)) % H
                pygame.draw.line(surf, (216, 196, 152), (x, y), (x + 11, y + 1), 1)
        elif wid == "storm":
            dark = pygame.Surface((W, H), pygame.SRCALPHA); dark.fill((28, 34, 58, 64))
            surf.blit(dark, (0, 0))
            for i in range(5):
                x = (i * 100 - int(t * 380)) % (W + 120) - 60
                pygame.draw.arc(surf, (198, 210, 236), (x, 36 + i * 44, 72, 30), 0.3, 2.7, 1)
            for i in range(28):
                x = (i * 53 - int(t * 880)) % (W + 30)
                y = (i * 71 + int(t * 320)) % (H + 20)
                pygame.draw.line(surf, (200, 215, 240), (x, y), (x - 8, y + 5), 1)
            if math.sin(t * 1.3 + 1.0) > 0.95:
                fl = pygame.Surface((W, H), pygame.SRCALPHA); fl.fill((228, 234, 255, 66))
                surf.blit(fl, (0, 0))

        # weather name chip (on top of the ambience)
        name = WEATHER[wid]["name"]
        f = get_font(16, bold=True)
        tw = f.size(name)[0]
        bx = (W - tw - 20) // 2
        chip = pygame.Rect(bx, 6, tw + 20, 22)
        pygame.draw.rect(surf, (16, 20, 32), chip, border_radius=6)
        pygame.draw.rect(surf, C.ACCENT, chip, width=1, border_radius=6)
        surf.blit(f.render(name, True, C.ACCENT), (bx + 10, 8))

    def _spark_twinkle(self, surf, x, y, a):
        col = (255, 248, 210, a)
        g = pygame.Surface((9, 9), pygame.SRCALPHA)
        pygame.draw.line(g, col, (4, 0), (4, 8), 1)
        pygame.draw.line(g, col, (0, 4), (8, 4), 1)
        surf.blit(g, (int(x - 4), int(y - 4)))

    def _draw_pop(self, surf, x, y, val, alpha):
        f = get_font(30, bold=True)
        for ox, oy, col in ((-2, 0, (20, 12, 12)), (2, 0, (20, 12, 12)),
                            (0, -2, (20, 12, 12)), (0, 2, (20, 12, 12)), (0, 0, (255, 236, 150))):
            s = f.render(str(val), True, col)
            s.set_alpha(int(alpha * 255))
            surf.blit(s, (int(x - s.get_width() / 2 + ox), int(y + oy)))

    def _draw_enemy_panels(self, surf):
        """One full panel for a lone foe; compact stacked panels for several."""
        live_or_all = self.enemies
        if len(live_or_all) <= 1:
            if live_or_all:
                self._draw_enemy_panel(surf, 24, 24, live_or_all[0], compact=False)
            return
        y = 18
        for i, foe in enumerate(live_or_all):
            self._draw_enemy_panel(surf, 24, y, foe, compact=True,
                                   targeted=(i == self.target_index))
            y += 52

    def _draw_enemy_panel(self, surf, x, y, foe, compact=False, targeted=False):
        fx = self._fx.get(id(foe), {"disp": foe.hp})
        if compact:
            rect = pygame.Rect(x, y, 270, 44)
            border = C.ACCENT if targeted else C.BORDER
            draw_panel(surf, rect, fill=C.NEAR_BLACK, border=border,
                       width=2 if targeted else 1, radius=8)
            faint = foe.fainted
            name_col = C.DIM if faint else C.WHITE
            draw_text(surf, foe.name, x + 10, y + 6, 18, name_col)
            draw_text(surf, f"Lv{foe.level}", x + 258, y + 8, 15, C.GREY, right=True)
            if foe.status in STATUSES:
                st = STATUSES[foe.status]
                draw_text(surf, st["abbr"], x + 150, y + 8, 13, st["color"])
            frac = fx["disp"] / max(1, foe.max_hp)
            draw_bar(surf, x + 10, y + 28, 250, 8, frac,
                     hp_color(foe.hp / max(1, foe.max_hp)))
            return
        rect = pygame.Rect(x, y, 300, 70)
        draw_panel(surf, rect, fill=C.NEAR_BLACK, border=C.BORDER, width=2, radius=10)
        draw_text(surf, foe.name, x + 14, y + 10, 24, C.WHITE)
        draw_text(surf, f"Lv{foe.level}", x + 286, y + 12, 20, C.GREY, right=True)
        draw_type_badge(surf, x + 14, y + 38, foe.type, 16)
        frac = fx["disp"] / max(1, foe.max_hp)
        draw_bar(surf, x + 120, y + 42, 166, 12, frac, hp_color(foe.hp / max(1, foe.max_hp)))
        if foe.status in STATUSES:
            st = STATUSES[foe.status]
            draw_text(surf, st["abbr"], x + 96, y + 14, 16, st["color"])
        # offensive hint: what the foe is weak to
        wk = weaknesses(foe.type)
        if wk:
            draw_text(surf, "Weak:", x + 6, y + 76, 16, C.GREY)
            cx = x + 56
            for el in wk:
                draw_text(surf, el, cx, y + 76, 16, C.ELEMENT_COLORS.get(el, C.GREY))
                cx += get_font(16).size(el)[0] + 10

    def _draw_player_panel(self, surf, x, y):
        rect = pygame.Rect(x, y, 300, 96)
        draw_panel(surf, rect, fill=C.NEAR_BLACK, border=C.ACCENT, width=2, radius=10)
        a = self.active
        draw_text(surf, a.name, x + 14, y + 10, 24, C.WHITE)
        draw_text(surf, f"Lv{a.level}", x + 286, y + 12, 20, C.GREY, right=True)
        if a.status in STATUSES:
            st = STATUSES[a.status]
            draw_text(surf, st["abbr"], x + 108, y + 14, 16, st["color"])
        hp = self.disp_p / max(1, a.max_hp)
        draw_text(surf, "HP", x + 14, y + 40, 18, C.GREY)
        draw_bar(surf, x + 44, y + 42, 200, 12, hp, hp_color(a.hp / max(1, a.max_hp)))
        draw_text(surf, f"{a.hp}/{a.max_hp}", x + 286, y + 38, 18, C.WHITE, right=True)
        mp = a.mp / max(1, a.max_mp)
        draw_text(surf, "MP", x + 14, y + 64, 18, C.GREY)
        draw_bar(surf, x + 44, y + 66, 200, 10, mp, C.BLUE)
        draw_text(surf, f"{a.mp}/{a.max_mp}", x + 286, y + 62, 18, C.WHITE, right=True)
        # animated EXP bar (#19)
        maxed = a.level >= MAX_LEVEL
        draw_text(surf, "EXP", x + 14, y + 84, 14, C.DIM)
        draw_xp_bar(surf, x + 44, y + 85, 200, self.disp_xp, h=6, max_level=maxed)
        draw_text(surf, "MAX" if maxed else f"{int(self.disp_xp * 100)}%",
                  x + 286, y + 81, 14, C.DIM, right=True)

    def draw(self, screen):
        self._build_bg()
        self._scene.blit(self._bg, (0, 0))
        self._draw_scene(self._scene)
        # upscale the chunky scene (with a brief shake), then crisp UI on top
        ox = oy = 0
        if self.shake > 0:
            ox = random.uniform(-self.shake, self.shake)
            oy = random.uniform(-self.shake, self.shake)
        screen.fill(C.BLACK)
        pygame.transform.scale(self._scene, (C.SCREEN_W, C.SCREEN_H), screen)
        if ox or oy:
            scaled = pygame.transform.scale(self._scene, (C.SCREEN_W, C.SCREEN_H))
            screen.blit(scaled, (int(ox), int(oy)))

        # damage numbers (full-res, positioned from internal anchors)
        for p in self.dmg_pops:
            sx = p["x"] * C.ZOOM
            sy = (p["y"] - int(p["t"] * 22)) * C.ZOOM
            self._draw_pop(screen, sx, sy, p["val"], max(0.0, 1 - p["t"] / 0.9))

        if self.reveal > 0.5:
            self._draw_enemy_panels(screen)
        if self.phase != "learn":
            self._draw_player_panel(screen, C.SCREEN_W - 312, C.SCREEN_H - 280)

        if self.phase == "msg" and self.msgbox:
            self.msgbox.draw(screen)
        elif self.menu is not None:
            if self.phase == "menu":
                # match the strip to the action menu's actual (clamped) rect so
                # the two stay flush no matter how the menu is positioned (#22)
                my, mh = self.menu.y, self.menu.height()
                strip = pygame.Rect(16, my, C.SCREEN_W - 290, mh)
                draw_panel(screen, strip, fill=C.NEAR_BLACK, border=C.BORDER, width=2, radius=10)
                block_top = strip.y + (mh - 48) // 2
                draw_text(screen, f"What will {self.active.name} do?",
                          strip.x + 18, block_top, 22, C.WHITE)
                draw_text(screen, "Move: D-Pad / Arrows   Confirm: A / Z   Back: B / X",
                          strip.x + 18, block_top + 32, 16, C.DIM)
            elif self.phase == "fight":
                # live stat card for the highlighted move, to the right of the
                # menu and below the player panel (#21)
                mid = self.menu.selected()
                if mid in MOVES:
                    card = pygame.Rect(400, C.SCREEN_H - 154, 384, 142)
                    draw_move_card(screen, card, MOVES[mid], mp_have=self.active.mp)
            elif self.phase == "learn":
                # compare the incoming move against the one in the crosshairs so
                # the player can decide what to forget (#18, reuses #21's widget)
                new_mid = getattr(self, "_learn_move", None)
                if new_mid in MOVES:
                    draw_move_card(screen, pygame.Rect(410, 130, 374, 162),
                                   MOVES[new_mid], title="New move")
                sel = self.menu.selected()
                aeth = getattr(self, "_learn_aether", None)
                if isinstance(sel, int) and aeth is not None and 0 <= sel < len(aeth.moves):
                    draw_move_card(screen, pygame.Rect(410, 304, 374, 162),
                                   MOVES[aeth.moves[sel]], title="Replacing")
            self.menu.draw(screen)
        if self.flash > 0:
            ov = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            ov.fill((255, 255, 255, int(220 * (self.flash / 0.28))))
            screen.blit(ov, (0, 0))
