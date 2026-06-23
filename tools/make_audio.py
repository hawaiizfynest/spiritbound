"""
Generate Spiritbound's chiptune music loops and sound effects as .wav files
into assets/audio/. Run from the repo root:

    python tools/make_audio.py

Requires numpy (a build-time tool only - the game itself needs no numpy; only
the produced .wav files ship). The audio system (game/audio.py) auto-loads
whatever is present here, so tweaking a sound is: edit a recipe below, re-run.

Written by LJ "HawaiizFynest" Eblacas.
"""
import os
import wave

import numpy as np

SR = 22050
_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "assets", "audio")
MUSIC_DIR = os.path.join(_ROOT, "music")
SFX_DIR = os.path.join(_ROOT, "sfx")

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note(name):
    """Frequency for a note like 'A4' / 'C#5' (A4 = 440 Hz). 'R' = rest (0)."""
    if name in (None, "R"):
        return 0.0
    pitch, octave = name[:-1], int(name[-1])
    semi = _NAMES.index(pitch) - _NAMES.index("A") + (octave - 4) * 12
    return 440.0 * (2 ** (semi / 12.0))


def env(n, attack=0.005, release=0.04):
    """Fade-in/out envelope (samples) so notes don't click."""
    e = np.ones(n)
    a = min(int(SR * attack), n // 2)
    r = min(int(SR * release), n - a)
    if a > 0:
        e[:a] = np.linspace(0, 1, a)
    if r > 0:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def square(freq, n, duty=0.5):
    if freq <= 0:
        return np.zeros(n)
    t = np.arange(n) / SR
    return np.where((t * freq) % 1.0 < duty, 1.0, -1.0)


def triangle(freq, n):
    if freq <= 0:
        return np.zeros(n)
    t = np.arange(n) / SR
    return 2 * np.abs(2 * ((t * freq) % 1.0) - 1) - 1


def sweep_square(f0, f1, n, duty=0.5):
    freq = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.where((phase / (2 * np.pi)) % 1.0 < duty, 1.0, -1.0)


def noise(n):
    return np.random.uniform(-1, 1, n)


def _write(path, samples):
    s = np.clip(samples, -1, 1)
    pcm = (s * 32767).astype("<i2")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _mix(*tracks):
    n = max(len(t) for t in tracks)
    out = np.zeros(n)
    for t in tracks:
        out[:len(t)] += t
    return out


def _seq(events, osc="square", vol=0.3, duty=0.5, gap=0.0):
    """Render a melody: events = [(note_name, seconds), ...]."""
    parts = []
    for name, dur in events:
        n = int(SR * dur)
        f = note(name)
        if osc == "triangle":
            w = triangle(f, n)
        else:
            w = square(f, n, duty)
        parts.append(w * env(n) * (vol if f > 0 else 0.0))
        if gap:
            parts.append(np.zeros(int(SR * gap)))
    return np.concatenate(parts) if parts else np.zeros(0)


# ---------------------------------------------------------------------------
# Sound effects
# ---------------------------------------------------------------------------
def sfx_hit():
    n = int(SR * 0.14)
    body = noise(n) * (np.linspace(1, 0, n) ** 2) * 0.45
    thud = sweep_square(260, 90, n) * np.linspace(1, 0, n) * 0.25
    return body + thud


def sfx_levelup():
    return _seq([("C5", .09), ("E5", .09), ("G5", .09), ("C6", .22)],
                duty=0.5, vol=0.32)


def sfx_catch():
    return _seq([("A4", .08), ("R", .03), ("E5", .08), ("R", .03), ("A5", .2)],
                duty=0.35, vol=0.3)


def sfx_select():
    return _seq([("E5", .05)], duty=0.5, vol=0.28)


def sfx_back():
    return _seq([("B4", .06), ("E4", .07)], duty=0.5, vol=0.26)


def sfx_faint():
    n = int(SR * 0.45)
    return sweep_square(440, 110, n, duty=0.5) * np.linspace(1, 0, n) ** 1.5 * 0.3


def sfx_heal():
    return _seq([("E5", .07), ("G5", .07), ("C6", .07), ("E6", .14)],
                osc="triangle", vol=0.34)


# ---------------------------------------------------------------------------
# Music loops  (melody square lead + triangle bass, simple + consonant)
# ---------------------------------------------------------------------------
def _bass(events, vol=0.26):
    return _seq(events, osc="triangle", vol=vol)


def _kick_track(beats, beat_dur, vol=0.4):
    """A noise 'kick' on the given beat indices, length = total beats."""
    total = int(SR * beat_dur * max(beats, default=0, key=lambda b: b) ) if beats else 0
    out = np.zeros(int(SR * beat_dur * (max(beats) + 1))) if beats else np.zeros(0)
    kn = int(SR * 0.06)
    k = (noise(kn) * np.linspace(1, 0, kn) ** 3) * vol
    for b in beats:
        i = int(SR * beat_dur * b)
        out[i:i + kn] += k[:len(out) - i]
    return out


def music_title():
    # calm, slow arpeggio in C major (~8s)
    b = 60 / 84
    mel = [("C5", b), ("E5", b), ("G5", b), ("E5", b),
           ("A4", b), ("C5", b), ("E5", b), ("C5", b),
           ("F4", b), ("A4", b), ("C5", b), ("A4", b),
           ("G4", b), ("B4", b), ("D5", b), ("G4", b)]
    bass = [("C3", b * 4), ("A2", b * 4), ("F2", b * 4), ("G2", b * 4)]
    return _mix(_seq(mel, vol=0.22, duty=0.5), _bass(bass, vol=0.22))


def music_overworld():
    # bright, walking-tempo melody in C major (~8s)
    b = 60 / 120
    mel = [("G4", b), ("C5", b), ("E5", b), ("G5", b/2), ("E5", b/2),
           ("F5", b), ("E5", b), ("D5", b), ("C5", b),
           ("E5", b), ("G5", b), ("A5", b), ("G5", b/2), ("E5", b/2),
           ("D5", b), ("E5", b), ("C5", b), ("R", b)]
    bass = [("C3", b), ("G3", b), ("C3", b), ("G3", b),
            ("F3", b), ("C3", b), ("F3", b), ("C3", b),
            ("C3", b), ("G3", b), ("A3", b), ("E3", b),
            ("G3", b), ("G3", b), ("C3", b), ("C3", b)]
    return _mix(_seq(mel, vol=0.24, duty=0.5), _bass(bass, vol=0.24))


def music_battle():
    # faster, driving, A-minor with a kick (~8s)
    b = 60 / 152
    mel = [("A4", b/2), ("A4", b/2), ("C5", b), ("E5", b), ("D5", b),
           ("E5", b/2), ("F5", b/2), ("E5", b), ("C5", b), ("A4", b),
           ("E5", b/2), ("E5", b/2), ("G5", b), ("A5", b), ("E5", b),
           ("D5", b), ("C5", b), ("B4", b), ("A4", b)]
    bass = [("A2", b/2)] * 8 + [("F2", b/2)] * 4 + [("E2", b/2)] * 4 + \
           [("A2", b/2)] * 4 + [("G2", b/2)] * 4 + [("E2", b/2)] * 6
    n_beats = int(round(sum(d for _, d in mel) / (b / 2)))
    kick = _kick_track(list(range(0, n_beats, 2)), b / 2, vol=0.32)
    return _mix(_seq(mel, vol=0.22, duty=0.5), _bass(bass, vol=0.24), kick)


def music_ending():
    # warm, slow, resolved C major (~8s)
    b = 60 / 76
    mel = [("E5", b), ("G5", b), ("C6", b * 2),
           ("A5", b), ("F5", b), ("G5", b * 2),
           ("F5", b), ("E5", b), ("D5", b), ("C5", b),
           ("G4", b), ("C5", b), ("E5", b * 2)]
    bass = [("C3", b * 2), ("G2", b * 2), ("F2", b * 2), ("G2", b * 2),
            ("A2", b * 2), ("F2", b * 2), ("C3", b * 2), ("C3", b * 2)]
    return _mix(_seq(mel, osc="triangle", vol=0.24), _bass(bass, vol=0.22))


SFX = {
    "hit": sfx_hit, "levelup": sfx_levelup, "catch": sfx_catch,
    "select": sfx_select, "back": sfx_back, "faint": sfx_faint, "heal": sfx_heal,
}
MUSIC = {
    "title": music_title, "overworld": music_overworld,
    "battle": music_battle, "ending": music_ending,
}


def main():
    np.random.seed(7)
    for name, fn in SFX.items():
        _write(os.path.join(SFX_DIR, name + ".wav"), fn())
        print("sfx  ", name)
    for name, fn in MUSIC.items():
        _write(os.path.join(MUSIC_DIR, name + ".wav"), fn())
        print("music", name)
    print("done ->", _ROOT)


if __name__ == "__main__":
    main()
