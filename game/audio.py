"""
Spiritbound - audio.

Guarded music + sound-effect plumbing. This is the *wiring*: the game currently
ships no audio files, so every call here no-ops cleanly when the mixer can't
start (no audio device / dummy SDL driver) or when a requested track/effect
isn't present yet. Drop .ogg loops into assets/audio/music and .wav effects into
assets/audio/sfx and they start playing - no code changes needed (#13).

Public API:
    audio.init()                       # once, after pygame is up
    audio.play_music(name)             # loop a track by base name (idempotent)
    audio.stop_music()
    audio.sfx(name)                    # one-shot effect by base name
    audio.set_volume(v) / get_volume()
    audio.set_muted(b) / toggle_muted() / is_muted()
    audio.apply_settings(muted, volume)  # load saved prefs from the save
"""
import os
import sys

import pygame

from . import assets

_MUSIC_EXTS = (".ogg", ".mp3", ".wav")
_SFX_EXTS = (".wav", ".ogg")

_enabled = False        # mixer is up
_muted = False
_volume = 0.6           # 0..1 master volume
_current = None         # base name of the track currently requested
_sfx_cache = {}         # name -> Sound | None (None = looked up, file missing)


def init():
    """Bring the mixer up once. Tries the default device first, then forces a
    retry with explicit, widely-supported parameters if that didn't take. A
    machine with no usable audio device just leaves audio disabled so every call
    below becomes a silent no-op."""
    global _enabled
    if _enabled:
        return
    try:
        if pygame.mixer.get_init() is None:
            try:
                pygame.mixer.init()
            except Exception:
                pass
        if pygame.mixer.get_init() is None:
            # the implicit open (e.g. from pygame.init()) failed or never ran;
            # tear down and try again with conservative explicit settings
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        _enabled = pygame.mixer.get_init() is not None
        if _enabled:
            try:
                pygame.mixer.set_num_channels(16)
            except Exception:
                pass
            _apply_music_volume()
    except Exception:
        _enabled = False


def status():
    """A snapshot of the audio system for diagnostics (see audio_check.py)."""
    music_dir = assets.path("audio", "music")
    sfx_dir = assets.path("audio", "sfx")
    music = {n: _find(music_dir, n, _MUSIC_EXTS)
             for n in ("overworld", "battle", "title", "ending")}
    sfx_files = {n: _find(sfx_dir, n, _SFX_EXTS)
                 for n in ("hit", "levelup", "catch", "select", "back", "faint", "heal")}
    try:
        mixer_init = pygame.mixer.get_init()
    except Exception:
        mixer_init = None
    return {
        "pygame": getattr(pygame.version, "ver", "?"),
        "sdl": ".".join(str(x) for x in getattr(pygame.version, "SDL", ())),
        "enabled": _enabled,
        "mixer_init": mixer_init,
        "muted": _muted,
        "volume": _volume,
        "assets_root": assets.root(),
        "music_dir": music_dir,
        "sfx_dir": sfx_dir,
        "music": music,
        "sfx": sfx_files,
    }


def write_status_log(path):
    """Write a human-readable audio status file (handy for the --noconsole EXE,
    where stdout is invisible). Never raises."""
    try:
        s = status()
        lines = ["Spiritbound - audio status",
                 f"pygame {s['pygame']}  SDL {s['sdl']}",
                 f"mixer enabled: {s['enabled']}   mixer_init: {s['mixer_init']}",
                 f"muted: {s['muted']}   volume: {s['volume']}",
                 f"assets root: {s['assets_root']}",
                 f"music dir:   {s['music_dir']}",
                 f"sfx dir:     {s['sfx_dir']}",
                 "", "music files:"]
        for n, p in s["music"].items():
            lines.append(f"   {n:10} {'OK  ' + p if p else 'MISSING'}")
        lines.append("sfx files:")
        for n, p in s["sfx"].items():
            lines.append(f"   {n:10} {'OK  ' + p if p else 'MISSING'}")
        lines += ["",
                  "Read me:",
                  " - mixer enabled False  -> this machine's audio device did not open.",
                  " - files MISSING        -> the 'assets' folder isn't beside the program.",
                  " - all OK but silent    -> check OS volume / output device, or 'muted' above."]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        pass


def _find(dirpath, name, exts):
    for ext in exts:
        p = os.path.join(dirpath, name + ext)
        if os.path.isfile(p):
            return p
    return None


def _apply_music_volume():
    if not _enabled:
        return
    try:
        pygame.mixer.music.set_volume(0.0 if _muted else _volume)
    except Exception:
        pass


def play_music(name):
    """Loop a music track by base name. Idempotent: asking for the track that is
    already playing does nothing, so re-entering a scene won't restart it.
    No-ops when audio is off or the file isn't there yet."""
    global _current
    if not _enabled or not name:
        _current = name
        return
    try:
        if name == _current and pygame.mixer.music.get_busy():
            return
    except Exception:
        pass
    path = _find(assets.path("audio", "music"), name, _MUSIC_EXTS)
    _current = name
    if not path:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        return
    try:
        pygame.mixer.music.load(path)
        _apply_music_volume()
        pygame.mixer.music.play(-1)
    except Exception:
        pass


def stop_music():
    global _current
    _current = None
    if not _enabled:
        return
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


def sfx(name):
    """Play a one-shot effect by base name. No-ops when off / muted / missing."""
    if not _enabled or _muted or not name:
        return
    snd = _sfx_cache.get(name, 0)
    if snd == 0:                    # not looked up yet
        path = _find(assets.path("audio", "sfx"), name, _SFX_EXTS)
        try:
            snd = pygame.mixer.Sound(path) if path else None
        except Exception:
            snd = None
        _sfx_cache[name] = snd
    if snd is not None:
        try:
            snd.set_volume(_volume)
            snd.play()
        except Exception:
            pass


def set_volume(v):
    global _volume
    _volume = max(0.0, min(1.0, float(v)))
    _apply_music_volume()


def get_volume():
    return _volume


def is_muted():
    return _muted


def set_muted(b):
    global _muted
    _muted = bool(b)
    _apply_music_volume()


def toggle_muted():
    set_muted(not _muted)
    return _muted


def apply_settings(muted, volume):
    """Load persisted prefs (from the save) into the audio system."""
    global _muted, _volume
    _muted = bool(muted)
    _volume = max(0.0, min(1.0, float(volume)))
    _apply_music_volume()
