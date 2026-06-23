"""
Spiritbound - audio diagnostic.

Run this from the game folder:

    python audio_check.py

It reports whether the sound mixer starts, whether the music/effect files are
found, and then tries to actually play a track and an effect. Paste the output
if you need help working out why the game is silent.

Written by LJ "HawaiizFynest" Eblacas
"""

import os
import sys
import time

import pygame

from game import assets, audio


def main():
    print("=" * 56)
    print(" Spiritbound audio check")
    print("=" * 56)

    pygame.init()
    pygame.font.init()
    print(f"pygame {pygame.version.ver}   SDL {'.'.join(map(str, pygame.version.SDL))}")
    print(f"mixer after pygame.init(): {pygame.mixer.get_init()}")

    audio.init()
    s = audio.status()
    print(f"mixer enabled: {s['enabled']}")
    print(f"mixer opened as: {s['mixer_init']}")
    print(f"muted: {s['muted']}    volume: {s['volume']}")
    print(f"frozen (built EXE): {bool(getattr(sys, 'frozen', False))}")
    print()
    print(f"assets root: {s['assets_root']}")
    print(f"  exists: {os.path.isdir(s['assets_root'])}")
    print(f"music dir: {s['music_dir']}  (exists: {os.path.isdir(s['music_dir'])})")
    for n, p in s["music"].items():
        print(f"   music/{n:10} {'OK  ' + os.path.basename(p) if p else 'MISSING'}")
    print(f"sfx dir:   {s['sfx_dir']}  (exists: {os.path.isdir(s['sfx_dir'])})")
    for n, p in s["sfx"].items():
        print(f"   sfx/{n:12} {'OK  ' + os.path.basename(p) if p else 'MISSING'}")

    if not s["enabled"]:
        print("\n>> The mixer did not open on this machine, so the game is silent.")
        print(">> Nothing in the assets folder can help until the device opens.")
        print(">> Check that an audio output device is connected and enabled.")
        return

    print("\nPlaying the overworld theme for 3 seconds...")
    audio.set_muted(False)
    audio.set_volume(0.8)
    audio.play_music("overworld")
    time.sleep(0.3)
    busy = pygame.mixer.music.get_busy()
    print(f"   music playing (get_busy): {busy}")
    time.sleep(2.7)

    print("Playing the 'levelup' effect...")
    audio.sfx("levelup")
    time.sleep(1.2)

    audio.stop_music()
    print("\nDone.")
    print("If the numbers look fine but you heard nothing, the problem is")
    print("outside the game: OS volume, the selected output device, or a")
    print("muted application channel in the system mixer.")


if __name__ == "__main__":
    main()
