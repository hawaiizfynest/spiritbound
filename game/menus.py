"""
Spiritbound - menu & overlay states.

  TitleState       New Game / Continue / Quit
  StarterState     pick one of three starter Aethers
  DialogueState    transparent text overlay (drives a ui.Textbox)
  PauseMenuState   transparent: Party (reorder) / Bag (use items) / Save / Close
  ShopState        buy items with coin
  GameOverState    friendly "blacked out" screen; warps home on close

Written by LJ "HawaiizFynest" Eblacas
"""

import os
import math
import pygame

from . import config as C
from .core import State, draw_text, draw_panel, draw_bar, get_font
from .ui import (draw_creature, draw_type_badge, hp_color, draw_xp_bar, Textbox, Menu, MenuItem)
from .data import (SPECIES, ITEMS, MOVES, SHOP_STOCK, weaknesses, resistances,
                   RARE_STOCK, RARE_STOCK_RANK, STATUSES)
from .entities import GameData, make_starter, base_agility, base_spatk, base_spdef, MAX_LEVEL
from . import quests
from . import dex
from . import endings
from . import audio


# ===========================================================================
# Shared helper
# ===========================================================================
def apply_field_item(save, item_id, member):
    """Use a field item on a party member. Returns a message or None if no effect."""
    it = ITEMS[item_id]
    k = it["kind"]
    if k == "heal_hp":
        if member.fainted or member.hp >= member.max_hp:
            return None
        got = member.heal_hp(it["value"])
        save.inventory.remove(item_id)
        return f"{member.name} recovered {got} HP."
    if k == "heal_mp":
        if member.fainted or member.mp >= member.max_mp:
            return None
        got = member.restore_mp(it["value"])
        save.inventory.remove(item_id)
        return f"{member.name} recovered {got} MP."
    if k == "revive":
        if not member.fainted:
            return None
        member.hp = max(1, member.max_hp // 2)
        save.inventory.remove(item_id)
        return f"{member.name} was revived!"
    if k == "cure":
        if member.status != "poison":
            return None
        member.status = None
        save.inventory.remove(item_id)
        return f"{member.name} is no longer poisoned."
    if k == "full_restore":
        if member.fainted or (member.hp >= member.max_hp and member.mp >= member.max_mp
                              and member.status is None):
            return None
        member.heal_hp(member.max_hp)
        member.restore_mp(member.max_mp)
        member.status = None
        save.inventory.remove(item_id)
        return f"{member.name} was fully restored!"
    if k == "max_revive":
        if not member.fainted:
            return None
        member.hp = member.max_hp
        save.inventory.remove(item_id)
        return f"{member.name} was revived to full health!"
    return None


def _draw_type_row(surf, x, y, types, size=16):
    if not types:
        draw_text(surf, "none", x, y, size, C.DIM)
        return
    cx = x
    for el in types:
        draw_text(surf, el, cx, y, size, C.ELEMENT_COLORS.get(el, C.GREY))
        cx += get_font(size).size(el)[0] + 12


def _draw_dim(screen, alpha=170):
    ov = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    ov.set_alpha(alpha)
    ov.fill(C.BLACK)
    screen.blit(ov, (0, 0))


def _alpha_text(surf, text, x, y, size, color, alpha, center=False, bold=False):
    if alpha <= 0:
        return
    s = get_font(size, bold).render(text, True, color)
    s.set_alpha(int(max(0.0, min(1.0, alpha)) * 255))
    surf.blit(s, (x - s.get_width() // 2 if center else x, y))


def _fade_window(t, fade_in, full, fade_out, gone):
    """Triangular/trapezoid opacity envelope over a time window."""
    if t < fade_in or t > gone:
        return 0.0
    if t < full:
        return (t - fade_in) / max(0.001, full - fade_in)
    if t < fade_out:
        return 1.0
    return 1.0 - (t - fade_out) / max(0.001, gone - fade_out)


# ===========================================================================
# IntroState  (opening credits, shown before the title)
# ===========================================================================
class IntroState(State):
    opaque = True

    CREATURES = ["galecrest", "tidewyrm", "pyrachs", "sparrk", "floravine", "marlance"]
    DURATION = 7.4

    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self._done = False

    def update(self, inp, dt):
        self.t += dt
        skip = (inp.pressed("confirm") or inp.pressed("cancel")
                or inp.pressed("start") or inp.pressed("menu"))
        if self.t > 0.6 and skip:
            self._finish()
        elif self.t >= self.DURATION:
            self._finish()

    def _finish(self):
        if self._done:
            return
        self._done = True
        self.app.pop()   # reveal the TitleState waiting beneath

    def draw(self, screen):
        # backdrop gradient
        for i in range(0, C.SCREEN_H, 4):
            f = i / C.SCREEN_H
            screen.fill((int(14 + 10 * f), int(16 + 18 * (1 - f)), int(30 + 26 * (1 - f))),
                        (0, i, C.SCREEN_W, 4))

        # drifting creatures across the band
        for k, sid in enumerate(self.CREATURES):
            x = (k * 150 + self.t * 34) % (C.SCREEN_W + 180) - 90
            y = 132 + 64 * math.sin(self.t * 0.7 + k * 1.3)
            draw_creature(screen, sid, int(x), int(y), 44,
                          face=1 if k % 2 else -1, bob=math.sin(self.t * 2 + k) * 3)

        # phase 1 - studio card
        c1 = _fade_window(self.t, 0.3, 1.3, 2.3, 2.8)
        if c1 > 0:
            _alpha_text(screen, "HawaiizFynest", C.SCREEN_W // 2, C.SCREEN_H // 2 - 28,
                        58, C.ACCENT, c1, center=True, bold=True)
            _alpha_text(screen, "presents", C.SCREEN_W // 2, C.SCREEN_H // 2 + 34,
                        24, C.GREY, c1, center=True)

        # phase 2 - title reveal
        if self.t > 2.7:
            tt = self.t - 2.7
            _alpha_text(screen, C.GAME_TITLE, C.SCREEN_W // 2, 120, 80, C.ACCENT,
                        min(1.0, tt / 0.8), center=True, bold=True)
            _alpha_text(screen, C.GAME_SUBTITLE, C.SCREEN_W // 2, 192, 30, C.WHITE,
                        min(1.0, (tt - 0.4) / 0.6), center=True, bold=True)
            _alpha_text(screen, C.TAGLINE, C.SCREEN_W // 2, 228, 22, C.GREY,
                        min(1.0, (tt - 0.7) / 0.6), center=True)
            ca = min(1.0, (tt - 0.4) / 0.8)
            _alpha_text(screen, "A game by", C.SCREEN_W // 2, C.SCREEN_H - 122,
                        16, C.DIM, ca, center=True)
            _alpha_text(screen, 'LJ "HawaiizFynest" Eblacas', C.SCREEN_W // 2,
                        C.SCREEN_H - 98, 24, C.WHITE, ca, center=True, bold=True)
            _alpha_text(screen, "github.com/HawaiizFynest", C.SCREEN_W // 2,
                        C.SCREEN_H - 64, 19, C.ACCENT, ca, center=True)
            if tt > 1.8 and math.sin(self.t * 4) > 0:
                _alpha_text(screen, "Press Start / Z", C.SCREEN_W // 2, C.SCREEN_H - 28,
                            18, C.GREY, 1.0, center=True)


# ===========================================================================
# DialogueState
# ===========================================================================
class DialogueState(State):
    opaque = False

    def __init__(self, app, lines, speaker=None, on_done=None):
        super().__init__(app)
        self.lines = [l for l in lines] if lines else [""]
        self.speaker = speaker
        self.on_done = on_done
        self.i = 0
        self.box = Textbox(self.lines[0], speaker)

    def update(self, inp, dt):
        self.box.update(dt)
        if inp.pressed("confirm") or inp.pressed("cancel"):
            if self.box.confirm() == "done":
                audio.sfx("select")
                self.i += 1
                if self.i >= len(self.lines):
                    self.app.pop()
                    if self.on_done:
                        self.on_done()
                else:
                    self.box = Textbox(self.lines[self.i], self.speaker)

    def draw(self, screen):
        self.box.draw(screen)


# ===========================================================================
# TitleState
# ===========================================================================
class TitleState(State):
    opaque = True
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self._build_menu()

    def _save_exists(self):
        path = getattr(self.app, "save_path", None)
        return bool(path) and os.path.exists(path)

    def _build_menu(self):
        items = [MenuItem("New Game", "new")]
        if self._save_exists():
            items.append(MenuItem("Continue", "continue"))
        items.append(MenuItem("Quit", "quit"))
        self.menu = Menu(items, C.SCREEN_W // 2 - 110, 360, width=220,
                         visible=4, size=26)

    def update(self, inp, dt):
        self.t += dt
        d = inp.dir_repeat()
        if d in ("up", "down"):
            self.menu.move(d)
        if inp.pressed("confirm"):
            choice = self.menu.selected()
            if choice == "quit":
                self.app.quit()
            elif choice == "new":
                self._new_game()
            elif choice == "continue":
                self._continue()

    def _new_game(self):
        save = GameData()
        save.px, save.py, save.facing = 19, 8, "up"   # near the mentor in Vale
        self.app.save = save
        from .overworld import OverworldState
        self.app.replace_all(OverworldState(self.app))
        # nudge the player toward the mentor
        self.app.push(DialogueState(self.app, [
            C.GAME_TITLE_FULL,
            "The world of Aetheria is fading. Its Aether Spring has gone quiet, and its guardian has fallen hollow.",
            "Speak with Mentor Wren, just north, to choose your first companion.",
        ]))

    def _continue(self):
        path = self.app.save_path
        try:
            self.app.save = GameData.load_from_file(path)
        except Exception:
            self.app.save = GameData()
        from .overworld import OverworldState
        self.app.replace_all(OverworldState(self.app))

    def draw(self, screen):
        # backdrop gradient
        for i in range(0, C.SCREEN_H, 4):
            f = i / C.SCREEN_H
            col = (int(18 + 18 * f), int(20 + 26 * (1 - f)), int(44 + 30 * (1 - f)))
            pygame.draw.rect(screen, col, (0, i, C.SCREEN_W, 4))

        # drifting decorative aethers
        for k, sid in enumerate(("galecrest", "tidewyrm", "pyrachs")):
            x = 130 + k * 270 + math.sin(self.t * 0.8 + k) * 18
            y = 300 + math.cos(self.t * 0.9 + k * 1.7) * 12
            draw_creature(screen, sid, int(x), int(y), 60, face=1 if k % 2 else -1,
                          bob=math.sin(self.t * 2 + k) * 3)

        # title
        draw_text(screen, C.GAME_TITLE, C.SCREEN_W // 2, 96, 86, C.ACCENT,
                  center=True, bold=True, shadow=True)
        draw_text(screen, C.GAME_SUBTITLE, C.SCREEN_W // 2, 170, 30, C.WHITE,
                  center=True, bold=True)
        draw_text(screen, C.TAGLINE, C.SCREEN_W // 2, 206, 22, C.GREY, center=True)
        self.menu.draw(screen)
        draw_text(screen, "A / Z to select    Arrows or D-Pad to move    F11 fullscreen",
                  C.SCREEN_W // 2, C.SCREEN_H - 30, 16, C.DIM, center=True)


# ===========================================================================
# StarterState
# ===========================================================================
class StarterState(State):
    opaque = True
    STARTERS = ["cindle", "sprigit", "driblet"]

    def __init__(self, app, on_choose):
        super().__init__(app)
        self.on_choose = on_choose
        self.idx = 1
        self.t = 0.0

    def update(self, inp, dt):
        self.t += dt
        if inp.repeat("left"):
            self.idx = (self.idx - 1) % len(self.STARTERS)
        if inp.repeat("right"):
            self.idx = (self.idx + 1) % len(self.STARTERS)
        if inp.pressed("confirm"):
            sid = self.STARTERS[self.idx]
            self.app.pop()
            self.on_choose(sid)

    def draw(self, screen):
        pygame.draw.rect(screen, (24, 30, 48), screen.get_rect())
        draw_text(screen, "Choose your first Aether", C.SCREEN_W // 2, 60, 34,
                  C.ACCENT, center=True, bold=True)
        spacing = C.SCREEN_W // 3
        for i, sid in enumerate(self.STARTERS):
            cx = spacing // 2 + i * spacing
            cy = 230
            sel = (i == self.idx)
            if sel:
                draw_panel(screen, pygame.Rect(cx - 96, cy - 120, 192, 240),
                           fill=C.PANEL_HI, border=C.ACCENT, width=3, radius=12)
            else:
                draw_panel(screen, pygame.Rect(cx - 90, cy - 116, 180, 232),
                           fill=C.PANEL, border=C.BORDER, width=2, radius=12)
            bob = math.sin(self.t * 2 + i) * 4 if sel else 0
            draw_creature(screen, sid, cx, cy, 92, face=-1 if i == 0 else 1, bob=bob)
            sp = SPECIES[sid]
            draw_text(screen, sp["name"], cx, cy + 96, 24,
                      C.WHITE if sel else C.GREY, center=True, bold=sel)
            bw = get_font(16).size(sp["type"])[0] + 14
            draw_type_badge(screen, cx - bw // 2, cy + 120, sp["type"], 16)

        sp = SPECIES[self.STARTERS[self.idx]]
        panel = pygame.Rect(60, C.SCREEN_H - 150, C.SCREEN_W - 120, 110)
        draw_panel(screen, panel, fill=C.NEAR_BLACK, border=C.ACCENT, width=2, radius=10)
        base = sp["base"]
        draw_text(screen, sp["name"] + "  -  " + sp["type"], panel.x + 18, panel.y + 14, 22, C.WHITE)
        draw_text(screen,
                  f"HP {base[0]}   ATK {base[1]}   DEF {base[2]}   SpA {base_spatk(sp)}   "
                  f"SpD {base_spdef(sp)}   SPD {base[3]}   AGI {base_agility(sp)}",
                  panel.x + 18, panel.y + 44, 17, C.GREY)
        for j, line in enumerate(_wrap(sp["desc"], 18, panel.width - 36)):
            draw_text(screen, line, panel.x + 18, panel.y + 70 + j * 20, 18, C.GREY)
        draw_text(screen, "Left / Right to look    A / Z to choose",
                  C.SCREEN_W // 2, C.SCREEN_H - 22, 16, C.DIM, center=True)


def _wrap(text, size, w):
    from .core import wrap_text
    return wrap_text(text, size, w)


# ===========================================================================
# ShopState
# ===========================================================================
class ShopState(State):
    opaque = True

    def __init__(self, app):
        super().__init__(app)
        self.save = app.save
        self.discount = min(0.25, 0.03 * getattr(self.save, "charisma", 0))
        self._build()
        self.msg = ""
        self.msg_t = 0.0

    def _price(self, iid):
        return max(1, round(ITEMS[iid]["price"] * (1 - self.discount)))

    def _build(self):
        stock = list(SHOP_STOCK)
        if getattr(self.save, "char_level", 1) >= RARE_STOCK_RANK:
            stock += RARE_STOCK
        items = [MenuItem(ITEMS[i]["name"], i, right=f"{self._price(i)}c")
                 for i in stock]
        items.append(MenuItem("Leave", "leave"))
        self.menu = Menu(items, 40, 150, width=320, visible=10, size=22, title="Tomas' Supplies")

    def update(self, inp, dt):
        if self.msg_t > 0:
            self.msg_t = max(0.0, self.msg_t - dt)
        d = inp.dir_repeat()
        if d in ("up", "down"):
            self.menu.move(d)
        if inp.pressed("cancel"):
            self.app.pop()
            return
        if inp.pressed("confirm"):
            choice = self.menu.selected()
            if choice == "leave":
                self.app.pop()
                return
            price = self._price(choice)
            if self.save.money >= price:
                self.save.money -= price
                self.save.inventory.add(choice, 1)
                self.msg = f"Bought {ITEMS[choice]['name']}!"
            else:
                self.msg = "You can't afford that."
            self.msg_t = 1.6

    def draw(self, screen):
        pygame.draw.rect(screen, (26, 32, 50), screen.get_rect())
        draw_text(screen, "Supply Shop", 40, 40, 34, C.ACCENT, bold=True)
        draw_panel(screen, pygame.Rect(C.SCREEN_W - 250, 40, 210, 44),
                   fill=C.NEAR_BLACK, border=C.GOLD, width=2, radius=8)
        draw_text(screen, f"Coin: {self.save.money}", C.SCREEN_W - 230, 53, 24, C.GOLD)
        if self.discount > 0:
            draw_text(screen, f"Charisma discount: -{int(round(self.discount * 100))}%",
                      40, 82, 18, C.ACCENT)
        if getattr(self.save, "char_level", 1) < RARE_STOCK_RANK:
            draw_text(screen, f"Premium goods unlock at Trainer Lv {RARE_STOCK_RANK}.",
                      40, 104, 16, C.DIM)
        self.menu.draw(screen)

        # description / count panel
        sel = self.menu.selected()
        panel = pygame.Rect(390, 150, C.SCREEN_W - 430, 300)
        draw_panel(screen, panel, fill=C.PANEL, border=C.BORDER, width=2, radius=10)
        if sel and sel != "leave":
            it = ITEMS[sel]
            draw_text(screen, it["name"], panel.x + 18, panel.y + 16, 24, C.WHITE, bold=True)
            draw_text(screen, f"Price: {self._price(sel)} coin", panel.x + 18, panel.y + 50, 18, C.GOLD)
            if self.discount > 0:
                draw_text(screen, f"was {it['price']}", panel.x + 150, panel.y + 52, 16, C.DIM)
            draw_text(screen, f"Owned: {self.save.inventory.count(sel)}", panel.x + 18, panel.y + 74, 18, C.GREY)
            for j, line in enumerate(_wrap(it["desc"], 18, panel.width - 36)):
                draw_text(screen, line, panel.x + 18, panel.y + 110 + j * 22, 18, C.GREY)
        else:
            draw_text(screen, "Thanks for stopping by.", panel.x + 18, panel.y + 18, 20, C.GREY)
        if self.msg_t > 0:
            draw_text(screen, self.msg, C.SCREEN_W // 2, C.SCREEN_H - 40, 22, C.ACCENT, center=True)
        draw_text(screen, "A / Z buy     B / X leave", C.SCREEN_W // 2, C.SCREEN_H - 16, 16, C.DIM, center=True)


# ===========================================================================
# GameOverState
# ===========================================================================
class GameOverState(State):
    opaque = True

    def __init__(self, app, on_close=None):
        super().__init__(app)
        self.on_close = on_close
        self.t = 0.0

    def update(self, inp, dt):
        self.t += dt
        if self.t > 0.4 and inp.pressed("confirm"):
            self.app.pop()
            if self.on_close:
                self.on_close()

    def draw(self, screen):
        pygame.draw.rect(screen, (16, 12, 22), screen.get_rect())
        draw_text(screen, "Your team was overwhelmed.", C.SCREEN_W // 2, 220, 34,
                  C.WHITE, center=True, bold=True)
        draw_text(screen, "You slip back to Vale to let your Aethers recover.",
                  C.SCREEN_W // 2, 270, 22, C.GREY, center=True)
        if math.sin(self.t * 4) > 0:
            draw_text(screen, "Press A / Z to continue", C.SCREEN_W // 2, 360, 20,
                      C.ACCENT, center=True)


# ===========================================================================
# EndingState  (chosen ending + credits, shown after the final boss)
# ===========================================================================
class EndingState(State):
    opaque = True
    music = "ending"

    CREATURES = ["galecrest", "tidewyrm", "pyrachs", "floravine", "marlance", "voltagon"]

    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0          # time within the current phase
        self.save = app.save
        self.ending_id = endings.choose(self.save)
        self.title = endings.title_for(self.ending_id)
        self.subtitle = endings.subtitle_for(self.ending_id)
        self.lines = endings.lines_for(self.ending_id)
        self.vis = endings.visual_for(self.ending_id)
        self.phase = "ending"
        self._saved = False
        self._build_credits()

    # ----- credits content (built from how the run actually went) -----
    def _build_credits(self):
        bonded = dex.bonded_count(self.save)
        total = max(1, dex.bondable_total())
        seen = dex.seen_count(self.save)
        rank = getattr(self.save, "char_level", 1)
        dexpct = int(round(100 * seen / total))
        A = self.vis["accent"]
        self.credits = [
            (C.GAME_TITLE.upper(), 42, A, True),
            (C.GAME_SUBTITLE, 22, C.WHITE, False),
            None,
            ("a game by", 17, C.GREY, False),
            ('LJ "HawaiizFynest" Eblacas', 26, C.WHITE, False),
            None,
            ("Design   Code   Pixel Art", 16, C.GREY, False),
            ("World & Story", 16, C.GREY, False),
            ('LJ "HawaiizFynest" Eblacas', 20, C.WHITE, False),
            None,
            ("- Your Journey -", 20, A, False),
            (f"Ending      {self.title}", 18, C.WHITE, False),
            (f"Bond Rank      {rank}", 18, C.WHITE, False),
            (f"Aethers Bonded      {bonded} / {total}", 18, C.WHITE, False),
            (f"iDentifi Seen      {dexpct}%", 18, C.WHITE, False),
            None,
            ("Bonded with the spirits of Aetheria.", 16, C.GREY, False),
            None,
            None,
            ("Thank you for playing.", 26, C.GOLD, True),
        ]
        # cumulative y offset for each entry
        self._cy = []
        yy = 0
        for e in self.credits:
            yy += (e[1] if e else 16) + 16
            self._cy.append(yy)
        target_y = int(C.SCREEN_H * 0.42)
        self._cred_max = C.SCREEN_H + 40 + self._cy[-1] - target_y
        self._cred_speed = 42.0

    def update(self, inp, dt):
        self.t += dt
        if not self._saved and self.t > 0.1:
            self._saved = True
            path = getattr(self.app, "save_path", None)
            if path:
                try:
                    self.save.save_to_file(path)
                except Exception:
                    pass

        if self.phase == "ending":
            lines_in = 0.8 + len(self.lines) * 0.5 + 0.6
            if self.t > lines_in and (inp.pressed("confirm") or inp.pressed("start")):
                self.phase = "credits"
                self.t = 0.0
        else:  # credits
            if inp.pressed("confirm") or inp.pressed("start"):
                self.app.replace_all(TitleState(self.app))

    # ----- drawing helpers -----
    def _grad(self, screen, top, bot):
        for i in range(0, C.SCREEN_H, 3):
            f = i / C.SCREEN_H
            screen.fill((int(top[0] + (bot[0] - top[0]) * f),
                         int(top[1] + (bot[1] - top[1]) * f),
                         int(top[2] + (bot[2] - top[2]) * f)),
                        (0, i, C.SCREEN_W, 3))

    def _glow(self, screen, cx, cy, r, color, alpha):
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for rr, a in ((1.0, alpha * 0.4), (0.66, alpha * 0.6), (0.36, alpha)):
            pygame.draw.circle(g, (*color, int(a)), (r, r), int(r * rr))
        screen.blit(g, (int(cx - r), int(cy - r)))

    def _scrim(self, screen, alpha):
        s = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        s.fill((6, 8, 16, alpha))
        screen.blit(s, (0, 0))

    def _motif(self, screen):
        motif = self.vis["motif"]
        glow = self.vis["glow"]
        cx = C.SCREEN_W // 2
        stage = int(C.SCREEN_H * 0.74)        # creatures live in the lower area
        if motif == "gather":
            self._glow(screen, cx, stage + 30, 210, glow, 150)
            n = len(self.CREATURES)
            for k, sid in enumerate(self.CREATURES):
                ang = math.pi * (0.15 + 0.7 * (k / (n - 1)))
                rad = 250 - 24 * math.sin(self.t * 0.5 + k)
                x = cx - math.cos(ang) * rad
                y = stage + 40 - math.sin(ang) * 70
                draw_creature(screen, sid, int(x), int(y), 38,
                              face=1 if x < cx else -1, bob=math.sin(self.t * 2 + k) * 3)
        elif motif == "parade":
            for k, sid in enumerate(self.CREATURES):
                x = (k * 150 + self.t * 30) % (C.SCREEN_W + 180) - 90
                y = stage + 30 * math.sin(self.t * 0.6 + k * 1.3)
                draw_creature(screen, sid, int(x), int(y), 40,
                              face=1, bob=math.sin(self.t * 2 + k) * 3)
        elif motif == "freedom":
            lo, hi = 315, C.SCREEN_H - 50      # rise within the lower band only
            span = hi - lo
            for k, sid in enumerate(self.CREATURES):
                y = hi - ((self.t * 30 + k * (span / len(self.CREATURES))) % span)
                x = cx + (k - 2.5) * 118 + math.sin(self.t * 0.8 + k) * 22
                draw_creature(screen, sid, int(x), int(y), 34,
                              face=1 if k % 2 else -1, bob=math.sin(self.t * 2 + k) * 4)
        else:  # spring
            cy = stage
            self._glow(screen, cx, cy, 140, glow, 170)
            for k, sid in enumerate(self.CREATURES):
                ang = self.t * 0.5 + k * (math.tau / len(self.CREATURES))
                x = cx + math.cos(ang) * 180
                y = cy + math.sin(ang) * 78
                draw_creature(screen, sid, int(x), int(y), 34,
                              face=-1 if math.cos(ang) > 0 else 1,
                              bob=math.sin(self.t * 2 + k) * 3)

    # ----- draw -----
    def draw(self, screen):
        if self.phase == "ending":
            self._draw_ending(screen)
        else:
            self._draw_credits(screen)

    def _draw_ending(self, screen):
        top, bot = self.vis["sky"]
        self._grad(screen, top, bot)
        self._motif(screen)
        self._scrim(screen, 95)

        draw_text(screen, self.title, C.SCREEN_W // 2, 66, 46, self.vis["accent"],
                  center=True, bold=True, shadow=True)
        _alpha_text(screen, self.subtitle, C.SCREEN_W // 2, 116, 18, C.GREY,
                    min(1.0, max(0.0, self.t - 0.3)), center=True)
        for j, line in enumerate(self.lines):
            la = min(1.0, max(0.0, (self.t - 0.8 - j * 0.5)))
            _alpha_text(screen, line, C.SCREEN_W // 2, 168 + j * 34, 21, C.WHITE,
                        la, center=True)
        lines_in = 0.8 + len(self.lines) * 0.5 + 0.6
        if self.t > lines_in and math.sin(self.t * 4) > 0:
            draw_text(screen, "Press A / Z  to continue", C.SCREEN_W // 2,
                      C.SCREEN_H - 38, 18, C.GREY, center=True)

    def _draw_credits(self, screen):
        top, bot = self.vis["sky"]
        self._grad(screen, (top[0] // 2, top[1] // 2, top[2] // 2),
                   (bot[0] // 3, bot[1] // 3, bot[2] // 3))
        self._scrim(screen, 70)
        scroll = min(self._cred_max, self.t * self._cred_speed)
        for i, e in enumerate(self.credits):
            if not e:
                continue
            text, size, color, bold = e
            y = C.SCREEN_H + 40 + self._cy[i] - scroll
            if y < -20 or y > C.SCREEN_H + 20:
                continue
            a = 1.0
            if y < 70:
                a = max(0.0, y / 70)
            elif y > C.SCREEN_H - 70:
                a = max(0.0, (C.SCREEN_H - y) / 70)
            _alpha_text(screen, text, C.SCREEN_W // 2, int(y), size, color, a,
                        center=True, bold=bold)
        if scroll >= self._cred_max and math.sin(self.t * 4) > 0:
            draw_text(screen, "Press A / Z  to return", C.SCREEN_W // 2,
                      C.SCREEN_H - 30, 16, C.GREY, center=True)


# ===========================================================================
# PauseMenuState
# ===========================================================================
class PauseMenuState(State):
    opaque = False

    def __init__(self, app):
        super().__init__(app)
        self.save = app.save
        self.mode = "main"
        self.msg = ""
        self.msg_t = 0.0
        self.swap_sel = None
        self._pending_item = None
        self._xp_disp = 0.0       # animated EXP fill for the detail panel (#19)
        self._xp_target = 0.0
        self._reorder_cursor = 0  # move-reorder UI state (#20)
        self._reorder_held = None
        self._build_main()

    # ----- menu builders -----
    def _build_main(self):
        self.mode = "main"
        items = [MenuItem("Party", "party"), MenuItem("Bag", "bag"),
                 MenuItem("Trainer", "trainer"), MenuItem("Quests", "quests"),
                 MenuItem("iDentifi", "dex"),
                 MenuItem("Save", "save"), MenuItem("Close", "close")]
        self.menu = Menu(items, C.SCREEN_W - 230, 60, width=200, visible=7, size=24, title="Pause")

    def _build_trainer(self):
        self.mode = "trainer"
        self.menu = Menu([MenuItem("Back", "back")], C.SCREEN_W - 230, 60,
                         width=200, visible=1, size=24, title="Pause")

    def _build_quests(self):
        self.mode = "quests"
        items = []
        for qid in quests.active_quests(self.save):
            q = quests.QUESTS[qid]
            tag = "MAIN" if q.get("main") else None
            items.append(MenuItem(q["title"], qid, right=tag,
                                  color=C.GOLD if q.get("main") else None))
        for qid in quests.completed_quests(self.save):
            items.append(MenuItem(quests.QUESTS[qid]["title"], qid, right="DONE",
                                  color=C.DIM))
        if not items:
            items = [MenuItem("(no quests yet)", None, enabled=False)]
        self.menu = Menu(items, C.SCREEN_W - 230, 60, width=200, visible=8,
                         size=20, title="Quests")

    def _build_dex(self):
        self.mode = "dex"
        items = []
        for n, sid in enumerate(dex.order(), start=1):
            st = dex.entry_status(self.save, sid)
            if st == dex.BONDED:
                label, tag, col = SPECIES[sid]["name"], "BOND", None
            elif st == dex.SEEN:
                label, tag, col = SPECIES[sid]["name"], "seen", C.GREY
            else:
                label, tag, col = "?????", None, C.DIM
            items.append(MenuItem(f"{n:02d} {label}", sid, right=tag, color=col))
        self.menu = Menu(items, C.SCREEN_W - 230, 60, width=200, visible=11,
                         size=18, title="iDentifi")

    def _build_party(self):
        self.mode = "party"
        self.swap_sel = None
        self._xp_disp = 0.0
        self.menu = self._party_menu("Party  (A: pick/swap)")

    def _party_menu(self, title):
        items = []
        for i, a in enumerate(self.save.party.members):
            tag = "FNT" if a.fainted else f"Lv{a.level}  {a.hp}/{a.max_hp}"
            col = C.RED if a.fainted else None
            items.append(MenuItem(a.name, i, right=tag, color=col))
        if not items:
            items = [MenuItem("(no Aethers yet)", None, enabled=False)]
        return Menu(items, 40, 110, width=320, visible=6, size=22, title=title)

    def _build_bag(self):
        self.mode = "bag"
        ids = [i for i in ITEMS if ITEMS[i].get("field") and self.save.inventory.has(i)]
        items = [MenuItem(ITEMS[i]["name"], i, right=f"x{self.save.inventory.count(i)}") for i in ids]
        if not items:
            items = [MenuItem("(no usable items)", None, enabled=False)]
        self.menu = Menu(items, 40, 110, width=320, visible=7, size=22, title="Bag  (A: use)")

    def _build_bag_target(self, item_id):
        self.mode = "bag_target"
        self._pending_item = item_id
        self._xp_disp = 0.0
        items = []
        for i, a in enumerate(self.save.party.members):
            tag = "FNT" if a.fainted else f"{a.hp}/{a.max_hp}  {a.mp}MP"
            items.append(MenuItem(a.name, i, right=tag))
        self.menu = Menu(items, 40, 110, width=340, visible=6, size=22,
                         title="Use on which Aether?")

    # ----- update -----
    def update(self, inp, dt):
        if self.msg_t > 0:
            self.msg_t = max(0.0, self.msg_t - dt)
        d = inp.dir_repeat()
        if d in ("up", "down") and self.mode != "reorder":
            self.menu.move(d)

        # ease the detail-panel EXP bar toward the highlighted member (#19)
        if self.mode in ("party", "bag_target", "reorder") and self.save.party.members:
            a = self.save.party.members[self.menu.index]
            self._xp_target = 1.0 if a.level >= MAX_LEVEL else a.xp_into_level()
            self._xp_disp += (self._xp_target - self._xp_disp) * min(1, dt * 6)
            if abs(self._xp_disp - self._xp_target) < 0.004:
                self._xp_disp = self._xp_target

        if self.mode == "main":
            self._update_main(inp)
        elif self.mode == "party":
            self._update_party(inp)
        elif self.mode == "reorder":
            self._update_reorder(inp)
        elif self.mode == "trainer":
            self._update_trainer(inp)
        elif self.mode == "quests":
            self._update_quests(inp)
        elif self.mode == "dex":
            self._update_dex(inp)
        elif self.mode == "bag":
            self._update_bag(inp)
        elif self.mode == "bag_target":
            self._update_bag_target(inp)

    def _update_trainer(self, inp):
        if inp.pressed("cancel") or inp.pressed("confirm"):
            self._build_main()

    def _update_quests(self, inp):
        if inp.pressed("cancel"):
            self._build_main()

    def _update_dex(self, inp):
        if inp.pressed("cancel"):
            self._build_main()

    def _update_main(self, inp):
        if inp.pressed("cancel") or inp.pressed("start") or inp.pressed("menu"):
            audio.sfx("back")
            self.app.pop()
            return
        if inp.pressed("confirm"):
            audio.sfx("select")
            c = self.menu.selected()
            if c == "close":
                self.app.pop()
            elif c == "party":
                self._build_party()
            elif c == "trainer":
                self._build_trainer()
            elif c == "quests":
                self._build_quests()
            elif c == "dex":
                self._build_dex()
            elif c == "bag":
                self._build_bag()
            elif c == "save":
                self._save_game()

    def _save_game(self):
        path = getattr(self.app, "save_path", None)
        try:
            if path:
                self.save.save_to_file(path)
                self.msg = "Game saved."
            else:
                self.msg = "Saving is unavailable."
        except Exception:
            self.msg = "Could not save."
        self.msg_t = 1.8

    def _update_party(self, inp):
        if inp.pressed("cancel"):
            if self.swap_sel is not None:
                self.swap_sel = None
            else:
                self._build_main()
            return
        if inp.pressed("menu") and self.swap_sel is None:
            # enter move-reorder for the highlighted creature (#20)
            m = self.save.party.members
            if m and len(m[self.menu.index].moves) >= 2:
                self.mode = "reorder"
                self._reorder_cursor = 0
                self._reorder_held = None
            return
        if inp.pressed("confirm"):
            idx = self.menu.selected()
            if idx is None:
                return
            if self.swap_sel is None:
                self.swap_sel = idx
            else:
                m = self.save.party.members
                m[self.swap_sel], m[idx] = m[idx], m[self.swap_sel]
                self.swap_sel = None
                keep = self.menu.index
                self.menu = self._party_menu("Party  (A: pick/swap)")
                self.menu.index = min(keep, len(self.menu.items) - 1)

    def _update_reorder(self, inp):
        """Reorder the highlighted creature's moves: A grabs a move, then up/down
        slides it (via Aether.swap_moves), A/B drops it; B exits (#20)."""
        members = self.save.party.members
        if not members:
            self.mode = "party"
            return
        a = members[self.menu.index]
        n = len(a.moves)
        d = inp.dir_repeat()
        if self._reorder_held is None:
            if d == "up":
                self._reorder_cursor = (self._reorder_cursor - 1) % n
            elif d == "down":
                self._reorder_cursor = (self._reorder_cursor + 1) % n
            if inp.pressed("confirm"):
                self._reorder_held = self._reorder_cursor
            elif inp.pressed("cancel") or inp.pressed("menu"):
                self.mode = "party"
        else:
            h = self._reorder_held
            if d == "up" and h > 0:
                a.swap_moves(h, h - 1)
                self._reorder_held = self._reorder_cursor = h - 1
            elif d == "down" and h < n - 1:
                a.swap_moves(h, h + 1)
                self._reorder_held = self._reorder_cursor = h + 1
            if inp.pressed("confirm") or inp.pressed("cancel"):
                self._reorder_held = None

    def _update_bag(self, inp):
        if inp.pressed("cancel"):
            self._build_main()
            return
        if inp.pressed("confirm"):
            iid = self.menu.selected()
            if iid is None:
                return
            if not self.save.party.members:
                self.msg = "You have no Aethers."
                self.msg_t = 1.4
                return
            self._build_bag_target(iid)

    def _update_bag_target(self, inp):
        if inp.pressed("cancel"):
            self._build_bag()
            return
        if inp.pressed("confirm"):
            idx = self.menu.selected()
            if idx is None:
                return
            member = self.save.party.members[idx]
            result = apply_field_item(self.save, self._pending_item, member)
            if result is None:
                self.msg = "It won't have any effect."
                self.msg_t = 1.4
            else:
                self.msg = result
                self.msg_t = 1.6
                audio.sfx("heal")
                if not self.save.inventory.has(self._pending_item):
                    self._build_bag()
                else:
                    keep = self.menu.index
                    self._build_bag_target(self._pending_item)
                    self.menu.index = min(keep, len(self.menu.items) - 1)

    # ----- draw -----
    def draw(self, screen):
        _draw_dim(screen, 180)
        self.menu.draw(screen)
        # info panel sits to the LEFT of the menu (which is at SCREEN_W-230)
        panel = pygame.Rect(40, 60, C.SCREEN_W - 286, C.SCREEN_H - 130)
        draw_panel(screen, panel, fill=C.PANEL, border=C.BORDER, width=2, radius=10)
        if self.mode == "party" and self.save.party.members:
            self._draw_party_list(screen, panel)
        elif self.mode == "reorder" and self.save.party.members:
            self._draw_member_detail(screen, panel, self.save.party.members[self.menu.index])
        elif self.mode == "trainer":
            self._draw_trainer(screen, panel)
        elif self.mode == "quests":
            self._draw_quests(screen, panel)
        elif self.mode == "dex":
            self._draw_dex(screen, panel)
        elif self.mode == "bag":
            self._draw_bag_list(screen, panel)
        elif self.mode == "bag_target" and self.save.party.members:
            self._draw_member_detail(screen, panel, self.save.party.members[self.menu.index])
        else:
            draw_text(screen, "Party - reorder your lead.", panel.x + 18, panel.y + 18, 20, C.GREY)
            draw_text(screen, "Bag - use healing items.", panel.x + 18, panel.y + 46, 20, C.GREY)
            draw_text(screen, "Save - store your progress.", panel.x + 18, panel.y + 74, 20, C.GREY)
            draw_text(screen, f"Coin: {self.save.money}", panel.x + 18, panel.bottom - 40, 22, C.GOLD)

        if self.swap_sel is not None:
            draw_text(screen, f"Swapping {self.save.party.members[self.swap_sel].name}...",
                      C.SCREEN_W // 2, C.SCREEN_H - 44, 20, C.ACCENT, center=True)
        if self.msg_t > 0:
            draw_text(screen, self.msg, C.SCREEN_W // 2, C.SCREEN_H - 22, 20, C.ACCENT, center=True)

    def _draw_dex(self, screen, panel):
        # completion tallies across the top
        seen_n, seen_t = dex.seen_count(self.save), dex.total_species()
        bond_n, bond_t = dex.bonded_count(self.save), dex.bondable_total()
        draw_text(screen, "iDentifi", panel.x + 18, panel.y + 14, 24, C.ACCENT, bold=True)
        draw_text(screen, f"Seen {seen_n}/{seen_t}", panel.right - 20, panel.y + 12,
                  16, C.GREY, right=True)
        draw_text(screen, f"Bonded {bond_n}/{bond_t}", panel.right - 20, panel.y + 32,
                  16, C.GOLD, right=True)
        if dex.is_complete(self.save):
            draw_text(screen, "DEX COMPLETE!", panel.x + 18, panel.y + 44, 16, C.GOLD)

        sid = self.menu.selected()
        if not sid:
            return
        e = dex.entry_view(self.save, sid)
        num = dex.order().index(sid) + 1

        if not e["known"]:
            # unknown: a silhouette and a teasing line
            cx, cy = panel.x + 90, panel.y + 150
            silo = pygame.Surface((140, 140), pygame.SRCALPHA)
            draw_creature(silo, sid, 70, 70, 76, face=1)
            dark = pygame.Surface((140, 140), pygame.SRCALPHA)
            dark.fill((10, 12, 20, 255))
            silo.blit(dark, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(silo, (cx - 70, cy - 70))
            draw_text(screen, f"No. {num:02d}", panel.x + 18, panel.y + 80, 22, C.DIM)
            draw_text(screen, "?????", panel.x + 18, panel.y + 110, 28, C.DIM, bold=True)
            draw_text(screen, "Not yet encountered.", panel.x + 18, panel.bottom - 60,
                      18, C.DIM)
            draw_text(screen, "Meet it in the wild to log it.", panel.x + 18,
                      panel.bottom - 36, 16, C.DIM)
            return

        # known: full entry
        draw_creature(screen, sid, panel.x + 88, panel.y + 150, 80, face=1)
        draw_text(screen, f"No. {num:02d}", panel.x + 170, panel.y + 78, 18, C.GREY)
        draw_text(screen, e["name"], panel.x + 170, panel.y + 100, 26, C.WHITE, bold=True)
        draw_type_badge(screen, panel.x + 170, panel.y + 134, e["type"], 16)
        status = "Bonded" if e["status"] == dex.BONDED else "Seen"
        scol = C.GOLD if e["status"] == dex.BONDED else C.GREY
        draw_text(screen, status, panel.right - 20, panel.y + 100, 18, scol, right=True)
        if not e.get("bondable", True):
            draw_text(screen, "(cannot be bonded)", panel.right - 20, panel.y + 124,
                      14, C.DIM, right=True)

        # weakness / resistance (the data the battle screen already computes)
        wy = panel.y + 200
        draw_text(screen, "Weak to:", panel.x + 18, wy, 16, C.GREY)
        _draw_type_row(screen, panel.x + 104, wy, e["weak"])
        draw_text(screen, "Resists:", panel.x + 18, wy + 26, 16, C.GREY)
        _draw_type_row(screen, panel.x + 104, wy + 26, e["resist"])

        # flavor text
        dy = wy + 64
        for line in _wrap(e["desc"], 18, panel.width - 36):
            draw_text(screen, line, panel.x + 18, dy, 18, C.GREY)
            dy += 22

    def _draw_quests(self, screen, panel):
        qid = self.menu.selected()
        if not qid:
            draw_text(screen, "No quests yet.", panel.x + 18, panel.y + 18, 22, C.GREY)
            draw_text(screen, "Talk to the folk of Aetheria to find work.",
                      panel.x + 18, panel.y + 50, 18, C.DIM)
            return
        q = quests.QUESTS[qid]
        done = quests.is_done(self.save, qid)
        head = C.DIM if done else (C.GOLD if q.get("main") else C.ACCENT)
        draw_text(screen, q["title"], panel.x + 18, panel.y + 16, 26, head, bold=True)
        draw_text(screen, "Completed" if done else ("Main Quest" if q.get("main") else "Side Quest"),
                  panel.right - 20, panel.y + 22, 16, C.GREY, right=True)
        y = panel.y + 52
        for line in _wrap(q["desc"], 17, panel.width - 36):
            draw_text(screen, line, panel.x + 18, y, 17, C.GREY)
            y += 22
        y += 10
        draw_text(screen, "Objectives:", panel.x + 18, y, 19, C.ACCENT)
        y += 28
        objs = q["objectives"]
        # clamp so an active quest momentarily parked at the terminal index
        # still shows a current marker rather than rendering everything done
        cur = min(quests.step_index(self.save, qid), len(objs) - 1)
        for i, obj in enumerate(objs):
            # only show current and past objectives (don't spoil the order ahead)
            if not done and i > cur:
                continue
            if done or i < cur:
                mark, col = "x", C.DIM            # completed
            else:
                mark, col = ">", C.WHITE          # current
            draw_text(screen, mark, panel.x + 22, y, 18, col)
            wrapped = _wrap(obj["text"], 17, panel.width - 80)
            for line in wrapped:
                draw_text(screen, line, panel.x + 46, y, 17, col)
                y += 20
            y += 6
        # rewards
        r = q["rewards"]
        if r:
            parts = []
            if r.get("coin"):
                parts.append(f"{r['coin']} coin")
            for iid, n in r.get("items", []):
                parts.append(ITEMS[iid]["name"] + (f" x{n}" if n > 1 else ""))
            if r.get("char_xp"):
                parts.append(f"{r['char_xp']} Trainer EXP")
            if parts:
                draw_text(screen, "Reward: " + ", ".join(parts),
                          panel.x + 18, panel.bottom - 36, 16,
                          C.DIM if done else C.GOLD)

    def _draw_trainer(self, screen, panel):
        draw_text(screen, "Trainer", panel.x + 18, panel.y + 16, 26, C.WHITE, bold=True)
        s = self.save
        draw_text(screen, f"Coin: {s.money}", panel.right - 20, panel.y + 22,
                  20, C.GOLD, right=True)
        lvl = getattr(s, "char_level", 1)
        need = s.char_xp_to_next()
        maxed = lvl >= 30
        draw_text(screen, f"Trainer  Lv {lvl}", panel.x + 18, panel.y + 46, 20, C.GOLD)
        draw_text(screen, "MAX" if maxed else f"EXP {s.char_xp}/{need}",
                  panel.right - 20, panel.y + 48, 15, C.GREY, right=True)
        draw_bar(screen, panel.x + 18, panel.y + 72, panel.width - 36, 8,
                 1.0 if maxed else s.char_xp / max(1, need), C.ACCENT)
        cha = getattr(s, "charisma", 0)
        luck = getattr(s, "luck", 0)
        ins = getattr(s, "insight", 0)
        vit = getattr(s, "vitality", 0)
        rows = [
            ("Charisma", cha, f"Shop prices reduced by {int(round(min(0.25, 0.03*cha)*100))}%."),
            ("Luck", luck, f"Bonds land {int(round(0.03*luck*100))}% more often; better finds."),
            ("Insight", ins, f"Aethers earn {int(round(0.02*ins*100))}% more EXP."),
            ("Vitality", vit, f"Party heals {round(0.015*vit*100, 1)}% HP after a win."),
        ]
        y = panel.y + 100
        for name, val, desc in rows:
            draw_text(screen, name, panel.x + 24, y, 21, C.ACCENT)
            draw_text(screen, str(val), panel.x + 210, y, 21, C.WHITE)
            draw_text(screen, desc, panel.x + 24, y + 24, 15, C.GREY)
            y += 64
        draw_text(screen, "Your stats grow as you adventure.",
                  panel.x + 24, panel.bottom - 38, 16, C.DIM)

    def _draw_party_list(self, screen, panel):
        """Scannable party overview (#30): every creature on one screen with its
        HP / MP / EXP, instead of one detail page each. Pick/swap to reorder."""
        members = self.save.party.members
        draw_text(screen, "Party", panel.x + 18, panel.y + 12, 24, C.ACCENT, bold=True)
        hint = "A drop here   B cancel" if self.swap_sel is not None else \
               "A move   C details   B back"
        draw_text(screen, hint, panel.right - 18, panel.y + 18, 14, C.DIM, right=True)

        top = panel.y + 48
        rowh = 64
        info_x = panel.x + 96
        bar_x = info_x + 28
        bar_end = panel.right - 84
        bw = bar_end - bar_x
        for i, a in enumerate(members):
            ry = top + i * rowh
            row = pygame.Rect(panel.x + 12, ry, panel.width - 24, rowh - 6)
            moving = (self.swap_sel == i)
            sel = (i == self.menu.index)
            if moving or sel:
                pygame.draw.rect(screen, C.PANEL_HI, row, border_radius=8)
                pygame.draw.rect(screen, C.GOLD if moving else C.ACCENT, row,
                                 width=3 if moving else 2, border_radius=8)
            draw_creature(screen, a.species_id, row.x + 38, row.centery, 42, face=1)
            nm_col = C.RED if a.fainted else C.WHITE
            draw_text(screen, a.name, info_x, ry + 4, 19, nm_col)
            nx = info_x + get_font(19).size(a.name)[0] + 10
            draw_type_badge(screen, nx, ry + 6, a.type, 13)
            draw_text(screen, "FNT" if a.fainted else f"Lv{a.level}",
                      panel.right - 18, ry + 6, 15, C.RED if a.fainted else C.GREY, right=True)
            hp = a.hp / max(1, a.max_hp)
            draw_text(screen, "HP", info_x, ry + 28, 12, C.DIM)
            draw_bar(screen, bar_x, ry + 30, bw, 8, hp, hp_color(hp))
            draw_text(screen, f"{a.hp} / {a.max_hp}", panel.right - 16, ry + 25, 14, C.WHITE, right=True)
            mp = a.mp / max(1, a.max_mp)
            draw_text(screen, "MP", info_x, ry + 42, 12, C.DIM)
            draw_bar(screen, bar_x, ry + 44, bw, 7, mp, C.BLUE)
            draw_text(screen, f"{a.mp} / {a.max_mp}", panel.right - 16, ry + 41, 14, C.WHITE, right=True)
            maxed = a.level >= MAX_LEVEL
            draw_text(screen, "XP", info_x, ry + 52, 11, C.DIM)
            draw_xp_bar(screen, bar_x, ry + 54, bw, 1.0 if maxed else a.xp_into_level(),
                        h=4, max_level=maxed)

    def _draw_bag_list(self, screen, panel):
        """Scannable bag (#30): all usable items on one screen with counts, plus
        the selected item's description."""
        draw_text(screen, "Bag", panel.x + 18, panel.y + 12, 24, C.ACCENT, bold=True)
        draw_text(screen, f"Coin: {self.save.money}", panel.right - 18, panel.y + 18,
                  16, C.GOLD, right=True)
        ids = [it.value for it in self.menu.items if it.value is not None]
        if not ids:
            draw_text(screen, "No usable items.", panel.x + 18, panel.y + 60, 20, C.GREY)
            return
        sel_id = self.menu.selected()
        top = panel.y + 48
        rowh = 38
        for i, iid in enumerate(ids):
            ry = top + i * rowh
            row = pygame.Rect(panel.x + 12, ry, panel.width - 24, rowh - 4)
            if iid == sel_id:
                pygame.draw.rect(screen, C.PANEL_HI, row, border_radius=6)
                pygame.draw.rect(screen, C.ACCENT, row, width=2, border_radius=6)
            draw_text(screen, ITEMS[iid]["name"], panel.x + 26, ry + 6, 19, C.WHITE)
            draw_text(screen, f"x{self.save.inventory.count(iid)}",
                      panel.right - 22, ry + 7, 17, C.GREY, right=True)
        if sel_id:
            desc_y = max(top + len(ids) * rowh + 12, panel.bottom - 64)
            pygame.draw.line(screen, C.BORDER, (panel.x + 18, desc_y - 8),
                             (panel.right - 18, desc_y - 8), 1)
            draw_text(screen, ITEMS[sel_id]["desc"], panel.x + 20, desc_y, 16, C.GREY)

    def _draw_member_detail(self, screen, panel, a):
        draw_creature(screen, a.species_id, panel.x + 70, panel.y + 80, 78, face=1)
        draw_text(screen, a.name, panel.x + 140, panel.y + 24, 26, C.WHITE, bold=True)
        draw_text(screen, f"Lv {a.level}", panel.x + 140, panel.y + 56, 20, C.GREY)
        draw_type_badge(screen, panel.x + 220, panel.y + 54, a.type, 16)
        # animated EXP bar (#19)
        maxed = a.level >= MAX_LEVEL
        draw_text(screen, "EXP", panel.x + 140, panel.y + 86, 14, C.DIM)
        draw_xp_bar(screen, panel.x + 184, panel.y + 88, 150, self._xp_disp, h=6, max_level=maxed)
        draw_text(screen, "MAX" if maxed else f"{int(self._xp_disp * 100)}%",
                  panel.x + 344, panel.y + 84, 14, C.DIM)
        hp = a.hp / max(1, a.max_hp)
        draw_text(screen, "HP", panel.x + 24, panel.y + 150, 18, C.GREY)
        draw_bar(screen, panel.x + 56, panel.y + 152, 200, 12, hp, hp_color(hp))
        draw_text(screen, f"{a.hp}/{a.max_hp}", panel.x + 264, panel.y + 148, 18, C.WHITE)
        mp = a.mp / max(1, a.max_mp)
        draw_text(screen, "MP", panel.x + 24, panel.y + 176, 18, C.GREY)
        draw_bar(screen, panel.x + 56, panel.y + 178, 200, 10, mp, C.BLUE)
        draw_text(screen, f"{a.mp}/{a.max_mp}", panel.x + 264, panel.y + 174, 18, C.WHITE)
        stat1 = (f"ATK {a.raw_stat('atk')}    DEF {a.raw_stat('def')}    "
                 f"SpA {a.raw_stat('spatk')}    SpD {a.raw_stat('spdef')}")
        stat2 = f"SPD {a.raw_stat('spd')}    AGI {a.raw_stat('agi')}"
        draw_text(screen, stat1, panel.x + 24, panel.y + 200, 16, C.GREY)
        draw_text(screen, stat2, panel.x + 24, panel.y + 220, 16, C.GREY)
        if a.status in STATUSES:
            st = STATUSES[a.status]
            draw_text(screen, st["abbr"], panel.right - 20, panel.y + 220, 16,
                      st["color"], right=True)
        reorder = (self.mode == "reorder")
        hint = "Up/Dn move  A drop  B done" if (reorder and self._reorder_held is not None) \
            else "Up/Dn pick  A grab  B back" if reorder else "C: reorder"
        draw_text(screen, "Moves:", panel.x + 24, panel.y + 244, 18, C.ACCENT)
        draw_text(screen, hint, panel.right - 20, panel.y + 246, 14, C.DIM, right=True)
        for j, m in enumerate(a.moves):
            mv = MOVES[m]
            col = C.ELEMENT_COLORS.get(mv["type"], C.WHITE)
            ty = "neutral" if mv["type"] is None else mv["type"]
            ry = panel.y + 268 + j * 24
            if reorder and j == self._reorder_cursor:
                held = (self._reorder_held == j)
                box = pygame.Rect(panel.x + 24, ry - 1, panel.width - 40, 22)
                pygame.draw.rect(screen, C.PANEL_HI, box, border_radius=5)
                pygame.draw.rect(screen, C.GOLD if held else C.ACCENT, box,
                                 width=2, border_radius=5)
            draw_text(screen, f"- {mv['name']}", panel.x + 30, ry, 18, col)
            draw_text(screen, f"{ty}   {mv['mp']}MP", panel.right - 20, ry,
                      16, C.GREY, right=True)
        # weaknesses / resistances (derived from the type chart)
        wy = panel.bottom - 70
        draw_text(screen, "Weak to:", panel.x + 24, wy, 16, C.GREY)
        _draw_type_row(screen, panel.x + 110, wy, weaknesses(a.type))
        draw_text(screen, "Resists:", panel.x + 24, wy + 26, 16, C.GREY)
        _draw_type_row(screen, panel.x + 110, wy + 26, resistances(a.type))

    def _draw_item_detail(self, screen, panel, iid):
        it = ITEMS[iid]
        draw_text(screen, it["name"], panel.x + 18, panel.y + 18, 24, C.WHITE, bold=True)
        draw_text(screen, f"Owned: {self.save.inventory.count(iid)}", panel.x + 18, panel.y + 52, 18, C.GREY)
        for j, line in enumerate(_wrap(it["desc"], 18, panel.width - 36)):
            draw_text(screen, line, panel.x + 18, panel.y + 90 + j * 22, 18, C.GREY)
