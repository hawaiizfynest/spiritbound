"""
Spiritbound - overworld.

The Zelda-style layer: walk a connected world a tile at a time (with smooth
tweening), bump into collisions, cross warps between maps, trigger wild
encounters in tall grass, and interact with NPCs / signs / chests by facing
them and pressing Confirm. Pushes the battle screen and the various menus.

Written by LJ "HawaiizFynest" Eblacas
"""

import pygame

from . import config as C
from .core import State, draw_text, draw_panel
from .ui import draw_player, draw_npc, draw_creature, NPC_PALETTES
from .maps import get_map
from .entities import Aether, make_starter
from .battle import BattleState
from .menus import DialogueState, StarterState, ShopState, GameOverState, PauseMenuState, EndingState
from . import quests
from . import audio

_DIRV = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_EXCLAIM_TIME = 0.55   # how long the "!" alert bubble holds before the trainer speaks (#8)


class OverworldState(State):
    opaque = True
    music = "overworld"

    def __init__(self, app):
        super().__init__(app)
        self.save = app.save
        self.map = get_map(self.save.map_id)
        self.px = self.save.px
        self.py = self.save.py
        self.facing = self.save.facing
        self.step = 0
        self.anim_t = 0.0
        self.turn_cd = 0.0

        self.moving = False
        self.move_from = (self.px, self.py)
        self.move_to = (self.px, self.py)
        self.move_t = 0.0
        self.move_dur = C.WALK_FRAMES / C.FPS

        self.fade = 0.0          # 0..1 black overlay for warps
        self._fade_warp = None   # pending (map,x,y,facing)
        self._hunters = {}       # id(npc) -> runtime roam/chase state
        self._build_hunters()

    def _build_hunters(self):
        """Seed runtime state for active-hunting trainers on the current map.
        A hunting NPC carries a `hunt` dict; until beaten it roams its home tile
        and chases the player on sight. Kept off the shared map dicts so reloads
        stay clean."""
        from . import ai  # local import keeps ai.py pure / overworld import light
        self._ai = ai
        self._hunters = {}
        for n in self.map.npcs:
            if not n.get("hunt") or not n.get("battle"):
                continue
            if self.save.has_flag(n.get("defeat_flag", "")):
                continue
            self._hunters[id(n)] = {
                "npc": n, "x": n["x"], "y": n["y"],
                "home": (n["x"], n["y"]), "facing": n.get("face", "down"),
                "chasing": False, "cd": 0.0, "exclaim": 0.0,
            }

    def _hunter_at(self, x, y):
        """The hunting NPC occupying (x, y) at its runtime position, or None."""
        for h in self._hunters.values():
            if h["x"] == x and h["y"] == y:
                return h
        return None

    def enter(self):
        # re-sync from save in case a sub-state changed position/map
        if (self.map.id != self.save.map_id):
            self.map = get_map(self.save.map_id)
        self.px, self.py = self.save.px, self.save.py
        self.facing = self.save.facing
        self._build_hunters()
        audio.apply_settings(self.save.audio_muted, self.save.audio_volume)

    # =====================================================================
    # Helpers
    # =====================================================================
    def _sync_save(self):
        self.save.map_id = self.map.id
        self.save.px = self.px
        self.save.py = self.py
        self.save.facing = self.facing

    def _front_tile(self):
        dx, dy = _DIRV[self.facing]
        return self.px + dx, self.py + dy

    def _blocked(self, x, y):
        if not self.map.tile_walkable(x, y):
            return True
        # NPCs and signs block; opened chests do not, closed chests do.
        # A hunting NPC is excluded here (its live tile is handled by
        # _hunter_at) so its vacated home tile doesn't stay phantom-blocked.
        n = self.map.npc_at(x, y)
        if n is not None and id(n) not in self._hunters:
            return True
        if self._hunter_at(x, y) is not None:   # a roaming hunter blocks too
            return True
        ch = self.map.chest_at(x, y)
        if ch is not None and not self.save.has_flag(ch["flag"]):
            return True
        return False

    def _begin_move(self, nx, ny, running):
        self.moving = True
        self.move_from = (self.px, self.py)
        self.move_to = (nx, ny)
        self.move_t = 0.0
        self.move_dur = (C.RUN_FRAMES if running else C.WALK_FRAMES) / C.FPS

    def _on_arrive(self, inp):
        self.px, self.py = self.move_to
        self._sync_save()
        # warp?
        w = self.map.warp_at(self.px, self.py)
        if w is not None:
            need = w.get("need_item")
            if need and not self.save.inventory.has(need):
                self.app.push(DialogueState(self.app, [w.get("locked", "It's sealed.")]))
                return
            self._start_warp(w["to"], w["tx"], w["ty"], w.get("face", self.facing))
            return
        # wild encounter?
        if self.map.is_tall(self.px, self.py):
            if self.save.party.first_healthy_index() is not None:
                import random
                if random.random() < C.ENCOUNTER_CHANCE:
                    self._start_encounter()
                    return

    def _start_warp(self, map_id, tx, ty, facing):
        self._fade_warp = (map_id, tx, ty, facing)
        self.fade = 0.001  # begin fade-out

    def _do_warp(self):
        map_id, tx, ty, facing = self._fade_warp
        self.map = get_map(map_id)
        self.px, self.py = tx, ty
        self.facing = facing
        self.moving = False
        self._sync_save()
        self._fade_warp = None
        self._build_hunters()
        self._quest_event("reach", map=map_id)

    def _start_encounter(self):
        import random
        roll = self.map.roll_encounter()
        if roll is None:
            return
        sid, lvl = roll
        foes = [Aether(sid, lvl)]
        # some areas spring "pack" encounters: a second wild foe joins the field
        dbl = getattr(self.map, "double_chance", 0.0)
        if dbl and len(self.save.party.members) >= 2 and random.random() < dbl:
            roll2 = self.map.roll_encounter()
            if roll2:
                sid2, lvl2 = roll2
                foes.append(Aether(sid2, max(1, lvl2 - 1)))
        self.app.push(BattleState(self.app, foes, kind="wild",
                                  weather=getattr(self.map, "weather", None),
                                  active_on_field=len(foes),
                                  on_lose=self._blackout))

    def _quest_event(self, event, **params):
        """Fire a quest objective check and, if anything advanced, queue the
        resulting lines as a dialogue. Returns the list of messages."""
        msgs = quests.notify(self.save, event, **params)
        if msgs:
            self.app.push(DialogueState(self.app, msgs, speaker="Quest"))
        return msgs

    def _show_ending(self):
        """Roll the chosen ending after the final boss falls."""
        self.app.push(EndingState(self.app))

    def _blackout(self):
        def revive_home():
            self.save.party.heal_all()
            self.map = get_map("vale")
            self.px, self.py = 8, 8
            self.facing = "down"
            self.moving = False
            self._sync_save()
        self.app.push(GameOverState(self.app, on_close=revive_home))

    # =====================================================================
    # Interaction
    # =====================================================================
    def _interact(self):
        fx, fy = self._front_tile()

        chest = self.map.chest_at(fx, fy)
        if chest is not None and not self.save.has_flag(chest["flag"]):
            from .data import ITEMS
            self.save.inventory.add(chest["item"], chest["qty"])
            self.save.set_flag(chest["flag"])
            name = ITEMS[chest["item"]]["name"]
            qty = chest["qty"]
            extra = f" x{qty}" if qty > 1 else ""
            item_id = chest["item"]
            self.app.push(DialogueState(
                self.app, [f"You found {name}{extra}!"],
                on_done=lambda iid=item_id: self._quest_event("collect", item=iid)))
            return True

        sign = self.map.sign_at(fx, fy)
        if sign is not None:
            self.app.push(DialogueState(self.app, sign["lines"]))
            return True

        npc = self.map.npc_at(fx, fy)
        if npc is not None:
            return self._talk(npc)
        return False

    def _react_lines(self, npc):
        """If the NPC has stat-gated reactions and the player meets one, return its
        lines (granting any one-time gift). Otherwise return None."""
        save = self.save
        for r in npc.get("reactions", []):
            stat = r.get("stat")
            if stat and getattr(save, stat, 0) < r.get("min", 0):
                continue
            once = r.get("once")
            if once and save.has_flag(once):
                continue
            lines = list(r.get("lines", []))
            gave = []
            if r.get("give"):
                from .data import ITEMS
                it, qty = r["give"]
                save.inventory.add(it, qty)
                gave.append(ITEMS[it]["name"] + (f" x{qty}" if qty > 1 else ""))
            if r.get("coin"):
                save.money += r["coin"]
                gave.append(f"{r['coin']} coin")
            if once and gave:
                save.set_flag(once)
            if gave:
                lines.append("(Received " + ", ".join(gave) + "!)")
            return lines
        return None

    def _offer_quests(self, npc):
        """Start any quests this NPC offers; returns queued quest-start lines."""
        msgs = []
        for qid in npc.get("offers", []):
            started = quests.start(self.save, qid)
            if started:
                msgs += started
        return msgs

    def _talk(self, npc):
        save = self.save
        name = npc.get("name", "")

        # trainer / boss battle not yet won
        if npc.get("battle") and not save.has_flag(npc.get("defeat_flag", "")):
            def start_battle():
                team = [Aether(sid, lv) for sid, lv in npc["battle"]]
                kind = "boss" if npc.get("boss") else "trainer"
                robber_id = npc.get("robber")   # set => this trainer robs on a win

                def on_win(outcome):
                    save.set_flag(npc["defeat_flag"])
                    lines = list(npc.get("win_lines", []))
                    # a robber returns everything it stole when finally beaten
                    if robber_id and save.has_stash(robber_id):
                        save.recover_stash(robber_id)
                        lines += list(npc.get("recover_lines",
                                              ["Your stolen items and Aethers are returned!"]))
                    # progress existing quests first, then surface any new offers
                    lines += quests.notify(save, "defeat", flag=npc["defeat_flag"])
                    lines += quests.notify(save, "talk", who=name)
                    lines += self._offer_quests(npc)
                    # beating the boss rolls the credits / chosen ending
                    after = self._show_ending if npc.get("boss") else None
                    if lines:
                        self.app.push(DialogueState(self.app, lines, speaker=name,
                                                    on_done=after))
                    elif after:
                        after()

                def on_lose():
                    if robber_id:
                        save.rob(robber_id)
                    self._blackout()

                self.app.push(BattleState(
                    self.app, team, kind=kind, opponent_name=name,
                    reward=npc.get("reward", 0), trainer=npc.get("pal"),
                    weather=getattr(self.map, "weather", None),
                    active_on_field=npc.get("active", 1),
                    on_win=on_win, on_lose=on_lose))
            pre = self._react_lines(npc) or npc["lines"]
            self.app.push(DialogueState(self.app, pre, speaker=name, on_done=start_battle))
            return True

        # mentor: hand out a starter the first time
        if npc.get("script") == "starter" and not save.started:
            def after_intro():
                self.app.push(StarterState(self.app, on_choose=self._grant_starter(npc)))
            self.app.push(DialogueState(self.app, npc["lines"], speaker=name, on_done=after_intro))
            return True

        # shopkeeper
        if npc.get("shop"):
            def open_shop():
                self.app.push(ShopState(self.app))
            greet = self._react_lines(npc) or npc["lines"]
            self.app.push(DialogueState(self.app, greet, speaker=name, on_done=open_shop))
            return True

        # plain talk (mentor after starter heals; trainers show their win lines)
        lines = list(npc.get("lines", []))
        if npc.get("defeat_flag") and save.has_flag(npc["defeat_flag"]) and npc.get("win_lines"):
            lines = list(npc["win_lines"])
        if npc.get("script") == "starter" and save.started:
            save.party.heal_all()
            lines = ["Your Aethers look rested and ready."] + list(npc.get("win_lines", npc["lines"]))
        elif npc.get("heal"):
            save.party.heal_all()
        # stat-driven reactions (townsfolk only; defeated trainers keep their win lines)
        if not npc.get("battle"):
            reacted = self._react_lines(npc)
            if reacted is not None:
                lines = reacted
        # quest givers + talk objectives
        lines += self._offer_quests(npc)
        lines += quests.notify(save, "talk", who=name)
        self.app.push(DialogueState(self.app, lines, speaker=name))
        return True

    def _grant_starter(self, npc):
        def cb(species_id):
            from .data import SPECIES
            self.save.party.add(make_starter(species_id))
            self.save.started = True
            self.save.dex_bond(species_id)
            for it, n in npc.get("gives", []):
                self.save.inventory.add(it, n)
            if npc.get("gives_flag"):
                self.save.set_flag(npc["gives_flag"])
            sp = SPECIES[species_id]["name"]
            lines = [
                f"A fine choice - {sp} already trusts you.",
                "Take these Bond Crystals. Weaken a wild Aether, then throw one to bond it.",
                "The Spring lies north, past Whisper Route and the Hollow Grove. Go carefully.",
            ]
            # begin the main quest (its first objective, got-starter, is already
            # satisfied, so start() also advances past it). Surface its lines.
            started = quests.start(self.save, quests.MAIN_QUEST_ID)
            if started:
                lines += started
            self.app.push(DialogueState(self.app, lines, speaker=npc.get("name", "Mentor")))
        return cb

    # =====================================================================
    # Update
    # =====================================================================
    def _held_dir(self, inp):
        for d in ("up", "down", "left", "right"):
            if inp.down(d):
                return d
        return None

    # ----- active-hunting trainers (#8) -----
    def _hunter_move_blocked(self, h, x, y):
        """Collision for a hunter stepping to (x, y): walls, other NPCs, other
        hunters, closed chests, and the player's own tile all block."""
        if not self.map.tile_walkable(x, y):
            return True
        if self.map.npc_at(x, y) is not None:
            return True
        ch = self.map.chest_at(x, y)
        if ch is not None and not self.save.has_flag(ch["flag"]):
            return True
        other = self._hunter_at(x, y)
        if other is not None and other is not h:
            return True
        return False

    def _update_hunters(self, dt):
        """Advance roaming/chasing trainers. On sight a trainer turns to face the
        player and raises a "!" alert; after a short beat it speaks, then closes
        in for the battle on contact. Returns True while a trainer is mid-beat so
        the caller can keep the player frozen until the alert fires (#8)."""
        if not self._hunters or self.moving or self._fade_warp is not None:
            return False
        for h in list(self._hunters.values()):
            npc = h["npc"]
            if self.save.has_flag(npc.get("defeat_flag", "")):
                continue
            # mid "!" beat: hold still, then fire the alert dialogue when it ends
            if h["exclaim"] > 0:
                h["exclaim"] = max(0.0, h["exclaim"] - dt)
                if h["exclaim"] <= 0:
                    self.app.push(DialogueState(
                        self.app, [npc["hunt"].get("alert", "Hey! You there - hold it!")],
                        speaker=npc.get("name", "")))
                return True
            sight = npc["hunt"].get("sight", 4)
            # spot the player? turn to face them and raise the alert
            if not h["chasing"] and self._ai.in_sight_cone(
                    h["x"], h["y"], h["facing"], self.px, self.py, sight):
                h["chasing"] = True
                h["facing"] = self._ai.facing_toward(h["x"], h["y"], self.px, self.py)
                h["exclaim"] = _EXCLAIM_TIME
                return True
            if not h["chasing"]:
                continue
            # contact: adjacent to the player -> battle
            if abs(h["x"] - self.px) + abs(h["y"] - self.py) <= 1:
                h["facing"] = self._ai.facing_toward(h["x"], h["y"], self.px, self.py)
                self._start_hunter_battle(npc)
                return True
            # otherwise step toward the player on a movement cooldown
            h["cd"] = max(0.0, h["cd"] - dt)
            if h["cd"] > 0:
                continue
            dx, dy = self._ai.step_toward(h["x"], h["y"], self.px, self.py)
            h["facing"] = self._ai.facing_toward(h["x"], h["y"], self.px, self.py)
            nx, ny = h["x"] + dx, h["y"] + dy
            if not self._hunter_move_blocked(h, nx, ny):
                h["x"], h["y"] = nx, ny
            h["cd"] = npc["hunt"].get("speed", 0.18)
        return False

    def _start_hunter_battle(self, npc):
        # face the player and route through the normal trainer-battle flow
        self.facing = self._ai.facing_toward(self.px, self.py, npc["x"], npc["y"])
        self._talk(npc)

    def update(self, inp, dt):
        self.anim_t += dt
        if self.turn_cd > 0:
            self.turn_cd = max(0.0, self.turn_cd - dt)

        # warp fade handling
        if self._fade_warp is not None:
            self.fade = min(1.0, self.fade + dt * 6.0)
            if self.fade >= 1.0:
                self._do_warp()
            return
        if self.fade > 0:
            self.fade = max(0.0, self.fade - dt * 6.0)

        # roaming/hunting trainers advance whether or not the player is moving;
        # skip while moving so a battle never triggers mid-tween
        if not self.moving:
            if self._update_hunters(dt):
                return   # a trainer is mid "!" beat — hold the player still

        if self.moving:
            self.move_t += dt
            self.step += 1
            if self.move_t >= self.move_dur:
                self.moving = False
                self._on_arrive(inp)
                # chain into next step if still holding a direction
                if not self.moving and self._fade_warp is None:
                    d = self._held_dir(inp)
                    if d and self.facing == d:
                        nx, ny = self.px + _DIRV[d][0], self.py + _DIRV[d][1]
                        if not self._blocked(nx, ny):
                            self._begin_move(nx, ny, inp.down("run"))
            return

        # idle: menu / interact / start moving
        if inp.pressed("start") or inp.pressed("menu"):
            self._sync_save()
            self.app.push(PauseMenuState(self.app))
            return
        if inp.pressed("confirm"):
            if self._interact():
                return

        d = self._held_dir(inp)
        if d:
            if self.facing != d:
                self.facing = d
                self.turn_cd = 0.09
            elif self.turn_cd <= 0:
                nx, ny = self.px + _DIRV[d][0], self.py + _DIRV[d][1]
                if self._blocked(nx, ny):
                    self.step += 1
                else:
                    self._begin_move(nx, ny, inp.down("run"))

    # =====================================================================
    # Draw
    # =====================================================================
    def _player_pixel(self):
        if self.moving:
            t = min(1.0, self.move_t / self.move_dur)
            fx, fy = self.move_from
            tx, ty = self.move_to
            x = (fx + (tx - fx) * t) * C.TILE
            y = (fy + (ty - fy) * t) * C.TILE
        else:
            x = self.px * C.TILE
            y = self.py * C.TILE
        return x, y

    def _camera(self, ppx, ppy):
        cam_x = int(ppx + C.TILE / 2 - C.VIEW_W_PX / 2)
        cam_y = int(ppy + C.TILE / 2 - C.VIEW_H_PX / 2)
        cam_x = max(0, min(cam_x, max(0, self.map.w * C.TILE - C.VIEW_W_PX)))
        cam_y = max(0, min(cam_y, max(0, self.map.h * C.TILE - C.VIEW_H_PX)))
        return cam_x, cam_y

    def _draw_exclaim(self, surf, cx, head_y):
        """A '!' alert bubble above a trainer that just spotted the player (#8).
        Drawn on the world surface so it scales with the chunky map pixels."""
        w, hh = 12, 14
        x, y = cx - w // 2, head_y - hh
        pygame.draw.rect(surf, C.NEAR_BLACK, (x - 1, y - 1, w + 2, hh + 2), border_radius=4)
        pygame.draw.rect(surf, C.WHITE, (x, y, w, hh), border_radius=3)
        pygame.draw.polygon(surf, C.NEAR_BLACK,
                            [(cx - 3, y + hh - 1), (cx + 3, y + hh - 1), (cx, y + hh + 4)])
        pygame.draw.polygon(surf, C.WHITE,
                            [(cx - 2, y + hh - 1), (cx + 2, y + hh - 1), (cx, y + hh + 2)])
        pygame.draw.rect(surf, C.RED, (cx - 1, y + 3, 2, 6))     # the stroke
        pygame.draw.rect(surf, C.RED, (cx - 1, y + 10, 2, 2))    # the dot

    def _draw_chest(self, screen, cx, cy):
        t = C.TILE
        pygame.draw.ellipse(screen, (20, 24, 36), (cx - 11, cy + 8, 22, 8))
        pygame.draw.rect(screen, (150, 110, 60), (cx - 10, cy - 6, 20, 14), border_radius=3)
        pygame.draw.rect(screen, (110, 78, 40), (cx - 10, cy - 11, 20, 7), border_radius=3)
        pygame.draw.rect(screen, C.GOLD, (cx - 2, cy - 8, 4, 9), border_radius=1)
        pygame.draw.circle(screen, C.GOLD, (cx, cy - 1), 2)

    def _draw_sign(self, screen, cx, cy):
        pygame.draw.rect(screen, (96, 70, 44), (cx - 2, cy - 2, 4, 16))
        pygame.draw.rect(screen, (150, 116, 72), (cx - 11, cy - 12, 22, 14), border_radius=3)
        pygame.draw.rect(screen, (110, 82, 50), (cx - 11, cy - 12, 22, 14), width=2, border_radius=3)
        for i in range(3):
            pygame.draw.line(screen, (90, 66, 40), (cx - 7, cy - 9 + i * 4), (cx + 7, cy - 9 + i * 4), 1)

    def draw(self, screen):
        if getattr(self, "_world", None) is None:
            self._world = pygame.Surface((C.VIEW_W_PX, C.VIEW_H_PX))
        world = self._world
        ppx, ppy = self._player_pixel()
        cam_x, cam_y = self._camera(ppx, ppy)
        self.map.draw(world, cam_x, cam_y)

        # collect y-sorted drawables
        drawables = []
        for ch in self.map.chests:
            if not self.save.has_flag(ch["flag"]):
                drawables.append((ch["y"], "chest", ch))
        for n in self.map.npcs:
            if n.get("boss") and self.save.has_flag(n.get("defeat_flag", "")):
                continue
            drawables.append((n["y"], "obj", n))
        drawables.append((self.py + (1 if self.moving else 0), "player", None))
        drawables.sort(key=lambda d: d[0])

        bob = int((pygame.time.get_ticks() // 240) % 2)  # subtle 1px npc bob
        for _, kind, obj in drawables:
            if kind == "player":
                sx = int(ppx - cam_x + C.TILE / 2)
                sy = int(ppy - cam_y + C.TILE / 2)
                draw_player(world, sx, sy, self.facing, self.step)
            elif kind == "chest":
                sx = obj["x"] * C.TILE - cam_x + C.TILE // 2
                sy = obj["y"] * C.TILE - cam_y + C.TILE // 2
                self._draw_chest(world, sx, sy)
            else:  # npc / sign / creature
                n = obj
                # hunting trainers render at their live roam/chase position
                h = self._hunters.get(id(n))
                ox, oy = (h["x"], h["y"]) if h else (n["x"], n["y"])
                face = h["facing"] if h else n.get("face", "down")
                sx = ox * C.TILE - cam_x + C.TILE // 2
                sy = oy * C.TILE - cam_y + C.TILE // 2
                if n.get("sign"):
                    self._draw_sign(world, sx, sy)
                elif n.get("creature"):
                    draw_creature(world, n["creature"], sx, sy - 2, 30,
                                  face=-1, bob=bob)
                else:
                    pal_name = n.get("pal", "villager")
                    pal = NPC_PALETTES.get(pal_name, NPC_PALETTES["villager"])
                    draw_npc(world, sx, sy, face, pal, step=bob * 6,
                             key=n.get("name"), role=pal_name)
                # "!" alert bubble while this hunter is mid spotted-beat (#8)
                if h and h["exclaim"] > 0:
                    self._draw_exclaim(world, sx, sy - 14)

        # upscale the world (chunky GBA pixels), then draw UI crisp on top
        pygame.transform.scale(world, (C.SCREEN_W, C.SCREEN_H), screen)
        self._draw_hud(screen)

        if self.fade > 0:
            ov = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
            ov.set_alpha(int(255 * self.fade))
            ov.fill(C.BLACK)
            screen.blit(ov, (0, 0))

    def _draw_hud(self, screen):
        # location banner (top-left)
        label = self.map.name
        w = max(140, len(label) * 11 + 28)
        draw_panel(screen, pygame.Rect(12, 12, w, 34),
                   fill=C.NEAR_BLACK, border=C.ACCENT, width=2, radius=8)
        draw_text(screen, label, 26, 21, 22, C.ACCENT)
        # controls hint (bottom)
        hint = ("Move: Arrows/D-Pad   Talk: Z/A   Menu: C/Y   Run: Shift   "
                "F11 Fullscreen   M Mute")
        draw_text(screen, hint, C.SCREEN_W // 2, C.SCREEN_H - 18, 16, C.GREY,
                  center=True, shadow=True)
