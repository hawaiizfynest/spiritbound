"""
Locate bundled game assets. Searched in order so audio/sprites are found whether
they're bundled inside a one-file EXE, sitting in an `assets/` folder next to the
EXE, or run straight from source:

    assets.path("sprites", "creatures", "sparrk.png")

Bundle the folder into the EXE with PyInstaller --add-data, e.g.
    --add-data "assets;assets"   (Windows; use ':' on macOS/Linux)
or just build with the shipped Spiritbound.spec, or drop the `assets` folder
beside the .exe.
"""
import os
import sys


def _source_root():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "assets")


def _candidates():
    base = getattr(sys, "_MEIPASS", None)
    if base:                                   # unpacked one-file bundle
        yield os.path.join(base, "assets")
    if getattr(sys, "frozen", False):          # beside the executable
        yield os.path.join(os.path.dirname(sys.executable), "assets")
    else:                                       # running from source
        yield _source_root()
    yield os.path.join(os.getcwd(), "assets")  # current dir, last resort


def root():
    for c in _candidates():
        if os.path.isdir(c):
            return c
    return _source_root()


def path(*parts):
    return os.path.join(root(), *parts)
