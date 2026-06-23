"""
Spiritbound - entry point.

A keyboard- and Xbox-controller-friendly RPG that crosses the overworld
exploration of Zelda, the creature-collecting of Pokemon, and the turn-based,
MP-driven battles of Final Fantasy. Run it with:

    python main.py

Art and maps are generated procedurally at runtime; the optional audio (music +
sound effects) and any drop-in sprite art live in the assets/ folder. When you
package a build, bundle assets/ with it (see README / Spiritbound.spec) or the
game runs silently.

Written by LJ "HawaiizFynest" Eblacas
"""

import os
import sys

import pygame

from game import config as C
from game import audio
from game.core import App
from game.menus import TitleState, IntroState


def _save_path():
    """A writable location next to the game (works frozen or as a script)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = os.path.expanduser("~")
    path = os.path.join(base, C.SAVE_FILE)
    # carry a pre-rename save over to the new filename, once, so existing
    # playthroughs survive the Spiritbound rename
    if not os.path.exists(path):
        legacy = os.path.join(base, "crystalbound_save.json")
        if os.path.exists(legacy):
            try:
                os.replace(legacy, path)
            except OSError:
                pass
    return path


def main():
    pygame.init()
    pygame.font.init()
    try:
        pygame.joystick.init()
    except Exception:
        pass

    app = App()                       # creates the window + caption (inits audio)
    app.save_path = _save_path()
    # drop an audio diagnostic next to the save; harmless, and the only window
    # into sound problems when the windowed EXE has no console
    audio.write_status_log(os.path.join(os.path.dirname(app.save_path), "audio_status.txt"))
    app.push(TitleState(app))         # waits beneath the intro
    app.push(IntroState(app))         # opening credits, pops to reveal the title
    try:
        app.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
