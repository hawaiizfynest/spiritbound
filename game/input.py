"""
Spiritbound - unified input.

Exposes one clean action set that is fed by BOTH the keyboard and an Xbox
controller at the same time (no mode switch). Supports controller hot-plug,
analog-stick deadzones, edge-triggered buttons and auto-repeat for menus.

Actions:
    up / down / left / right   directional
    confirm                    A button / Z / Enter / Space
    cancel                     B button / X / Backspace / Esc
    menu                       Y button / C / Tab
    start                      Start button / P
    run                        X button / Left-Shift (held)

API:
    inp.begin_frame(events)    call once per frame, after collecting events
    inp.down(action)           True while held
    inp.pressed(action)        True only on the frame it was pressed (edge)
    inp.repeat(action)         True on press, then repeats while held (menus)
    inp.any_pressed()          True if any confirm/start/direction edge fired

Written by LJ "HawaiizFynest" Eblacas
"""

import pygame
from . import config as C

ACTIONS = ("up", "down", "left", "right", "confirm", "cancel", "menu", "start", "run")

# Auto-repeat tuning (in frames at 60 FPS)
_REPEAT_DELAY = 16
_REPEAT_INTERVAL = 6


class Input:
    def __init__(self):
        self.joystick = None
        self.joy_name = ""
        pygame.joystick.init()
        self._init_joystick()

        self.now = {a: False for a in ACTIONS}
        self.prev = {a: False for a in ACTIONS}
        self._held = {a: 0 for a in ACTIONS}   # frames an action has been held

    # -- device handling ----------------------------------------------------
    def _init_joystick(self):
        self.joystick = None
        self.joy_name = ""
        try:
            if pygame.joystick.get_count() > 0:
                js = pygame.joystick.Joystick(0)
                js.init()
                self.joystick = js
                self.joy_name = js.get_name()
        except pygame.error:
            self.joystick = None

    def has_controller(self):
        return self.joystick is not None

    # -- per-frame update ---------------------------------------------------
    def begin_frame(self, events):
        # handle hot-plug
        for e in events:
            if e.type == pygame.JOYDEVICEADDED or e.type == pygame.JOYDEVICEREMOVED:
                self._init_joystick()

        self.prev = dict(self.now)
        self._read_state()

        for a in ACTIONS:
            if self.now[a]:
                self._held[a] += 1
            else:
                self._held[a] = 0

    def _read_state(self):
        k = pygame.key.get_pressed()
        now = {a: False for a in ACTIONS}

        # keyboard
        now["up"]      = k[pygame.K_UP] or k[pygame.K_w]
        now["down"]    = k[pygame.K_DOWN] or k[pygame.K_s]
        now["left"]    = k[pygame.K_LEFT] or k[pygame.K_a]
        now["right"]   = k[pygame.K_RIGHT] or k[pygame.K_d]
        now["confirm"] = k[pygame.K_z] or k[pygame.K_RETURN] or k[pygame.K_SPACE] or k[pygame.K_KP_ENTER]
        now["cancel"]  = k[pygame.K_x] or k[pygame.K_BACKSPACE] or k[pygame.K_ESCAPE]
        now["menu"]    = k[pygame.K_c] or k[pygame.K_TAB]
        now["start"]   = k[pygame.K_p]
        now["run"]     = k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT]

        # controller (merged in)
        js = self.joystick
        if js is not None:
            try:
                nb = js.get_numbuttons()

                def btn(i):
                    return i < nb and js.get_button(i)

                # face buttons
                if btn(C.BTN_A):     now["confirm"] = True
                if btn(C.BTN_B):     now["cancel"] = True
                if btn(C.BTN_Y):     now["menu"] = True
                if btn(C.BTN_START): now["start"] = True
                if btn(C.BTN_X):     now["run"] = True

                # d-pad (hat)
                if js.get_numhats() > 0:
                    hx, hy = js.get_hat(0)
                    if hx < 0: now["left"] = True
                    if hx > 0: now["right"] = True
                    if hy > 0: now["up"] = True
                    if hy < 0: now["down"] = True

                # left analog stick
                na = js.get_numaxes()
                if na > C.AXIS_LX:
                    ax = js.get_axis(C.AXIS_LX)
                    if ax < -C.STICK_DEADZONE: now["left"] = True
                    if ax > C.STICK_DEADZONE:  now["right"] = True
                if na > C.AXIS_LY:
                    ay = js.get_axis(C.AXIS_LY)
                    if ay < -C.STICK_DEADZONE: now["up"] = True
                    if ay > C.STICK_DEADZONE:  now["down"] = True
            except pygame.error:
                # controller yanked mid-poll; drop it and continue on keyboard
                self.joystick = None

        self.now = now

    # -- queries ------------------------------------------------------------
    def down(self, action):
        return self.now.get(action, False)

    def pressed(self, action):
        return self.now.get(action, False) and not self.prev.get(action, False)

    def repeat(self, action):
        h = self._held.get(action, 0)
        if h == 1:
            return True
        if h > _REPEAT_DELAY and (h - _REPEAT_DELAY) % _REPEAT_INTERVAL == 0:
            return True
        return False

    def dir_pressed(self):
        """Return 'up'/'down'/'left'/'right' for a fresh directional edge, else None."""
        for d in ("up", "down", "left", "right"):
            if self.pressed(d):
                return d
        return None

    def dir_repeat(self):
        """Same as dir_pressed but with auto-repeat (for menu scrolling)."""
        for d in ("up", "down", "left", "right"):
            if self.repeat(d):
                return d
        return None

    def any_pressed(self):
        for a in ("confirm", "cancel", "start", "up", "down", "left", "right"):
            if self.pressed(a):
                return True
        return False
