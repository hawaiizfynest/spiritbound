"""
Spiritbound - core application shell + state stack + draw helpers.

Written by LJ "HawaiizFynest" Eblacas
"""

import pygame
from . import config as C
from . import audio
from .input import Input

# ---------------------------------------------------------------------------
# Font cache + text helpers
# ---------------------------------------------------------------------------
_font_cache = {}


def get_font(size, bold=False):
    key = (size, bool(bold))
    f = _font_cache.get(key)
    if f is None:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _font_cache[key] = f
    return f


def draw_text(surf, text, x, y, size=20, color=C.WHITE, center=False,
              right=False, bold=False, shadow=False):
    font = get_font(size, bold)
    if shadow:
        sh = font.render(text, True, C.BLACK)
        srect = sh.get_rect()
        if center:   srect.center = (x + 1, y + 1)
        elif right:  srect.topright = (x + 1, y + 1)
        else:        srect.topleft = (x + 1, y + 1)
        surf.blit(sh, srect)
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:   rect.center = (x, y)
    elif right:  rect.topright = (x, y)
    else:        rect.topleft = (x, y)
    surf.blit(img, rect)
    return rect


def text_width(text, size, bold=False):
    return get_font(size, bold).size(text)[0]


def wrap_text(text, size, max_width, bold=False):
    """Word-wrap a string to a list of lines that fit max_width pixels."""
    font = get_font(size, bold)
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if font.size(trial)[0] <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def draw_panel(surf, rect, fill=C.PANEL, border=C.BORDER, width=2, radius=8):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if width > 0:
        pygame.draw.rect(surf, border, rect, width=width, border_radius=radius)


def draw_bar(surf, x, y, w, h, frac, fg, bg=C.DARK, border=C.BLACK):
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=h // 2)
    if frac > 0:
        fw = max(2, int((w - 2) * frac))
        pygame.draw.rect(surf, fg, (x + 1, y + 1, fw, h - 2), border_radius=(h - 2) // 2)
    pygame.draw.rect(surf, border, (x, y, w, h), width=1, border_radius=h // 2)


# ---------------------------------------------------------------------------
# State base class
# ---------------------------------------------------------------------------
class State:
    opaque = True   # if False, the state below is drawn too (overlays/menus)

    def __init__(self, app):
        self.app = app

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, inp, dt):
        pass

    def draw(self, screen):
        pass


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        pygame.display.set_caption(C.GAME_TITLE_FULL)
        # SCALED lets pygame upscale/letterbox our fixed-size surface to the
        # real window or display, so the F11 fullscreen toggle needs no draw
        # changes; RESIZABLE allows maximizing the window too.
        self.screen = pygame.display.set_mode(
            (C.SCREEN_W, C.SCREEN_H), pygame.SCALED | pygame.RESIZABLE)
        self.fullscreen = False
        self.clock = pygame.time.Clock()
        self.input = Input()
        self.stack = []
        self.running = True
        self.save = None          # active GameData (set on new/continue)
        audio.init()              # guarded; no-ops if there's no audio device

    def toggle_fullscreen(self):
        """Flip between windowed and fullscreen. With SCALED, pygame rescales
        the same SCREEN_W x SCREEN_H surface, so nothing else has to change.
        Guarded so a platform that can't toggle never crashes the loop."""
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = not self.fullscreen
        except pygame.error:
            pass

    # stack management ------------------------------------------------------
    def _apply_music(self):
        """Let the top scene drive the music. A state opts in with a `music`
        class attr (e.g. OverworldState.music = 'overworld'); overlays that don't
        set one leave the current track alone. play_music is idempotent + guarded
        and the game currently ships no tracks, so this is silent until files are
        added (#13)."""
        if self.stack:
            track = getattr(self.stack[-1], "music", None)
            if track:
                audio.play_music(track)

    def push(self, state):
        self.stack.append(state)
        state.enter()
        self._apply_music()

    def pop(self):
        if self.stack:
            s = self.stack.pop()
            s.exit()
        self._apply_music()

    def change(self, state):
        if self.stack:
            self.pop()
        self.push(state)

    def replace_all(self, state):
        while self.stack:
            self.pop()
        self.push(state)

    def quit(self):
        self.running = False

    # main loop -------------------------------------------------------------
    def run(self):
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            dt = min(dt, 0.05)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                    audio.toggle_muted()
                    if self.save is not None:
                        self.save.audio_muted = audio.is_muted()
            self.input.begin_frame(events)

            if not self.stack:
                self.running = False
                break

            self.stack[-1].update(self.input, dt)
            self._draw()
            pygame.display.flip()

    def _draw(self):
        self.screen.fill(C.BLACK)
        if not self.stack:
            return
        start = len(self.stack) - 1
        while start > 0 and not self.stack[start].opaque:
            start -= 1
        for s in self.stack[start:]:
            s.draw(self.screen)
