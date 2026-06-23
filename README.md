# Spiritbound: Legends of Aetheria

[![CI](https://github.com/HawaiizFynest/spiritbound/actions/workflows/ci.yml/badge.svg)](https://github.com/HawaiizFynest/spiritbound/actions/workflows/ci.yml)
[![Build and Release](https://github.com/HawaiizFynest/spiritbound/actions/workflows/release.yml/badge.svg)](https://github.com/HawaiizFynest/spiritbound/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/HawaiizFynest/spiritbound?display_name=tag&sort=semver)](https://github.com/HawaiizFynest/spiritbound/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/HawaiizFynest/spiritbound/total)](https://github.com/HawaiizFynest/spiritbound/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Made with pygame-ce](https://img.shields.io/badge/made%20with-pygame--ce-44cc11)](https://pyga.me/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#run-it)
[![License](https://img.shields.io/badge/license-do%20what%20you%20like-brightgreen)](#license)

*Bond with the spirits of Aetheria.*

> **Note on badges:** the build-status, release, and downloads badges read live
> data from GitHub. They render once the repository is public; while it is
> private they may show "not found" until then.

Spiritbound: Legends of Aetheria is a self-contained RPG that pulls three things into one game: the top-down, walk-anywhere overworld of Zelda, the catch-train-evolve loop of Pokemon, and the turn-based, MP-driven battles of Final Fantasy. You explore Aetheria, a fading world, one tile at a time, find wild Aethers in tall grass, weaken and bond them with Bond Crystals, build a party, and push north to face Nullith, the hollow guardian of a corrupted spring.

The whole game draws its art procedurally at runtime. There are no sprite sheets, image files, or sound files to ship. The Python source is the game. Scenes render to a low-resolution buffer and scale up for a chunky, GBA-style pixel look, while the interface stays crisp on top.

Play it with a keyboard or a Bluetooth Xbox Series X controller. Both work at the same time, so you can pick up either one mid-session without touching a setting.

Written by LJ "HawaiizFynest" Eblacas

## Run it

You need Python 3.10 or newer.

```
pip install -r requirements.txt
python main.py
```

This installs **pygame-ce** (pygame Community Edition), a drop-in replacement for classic pygame that ships pre-built wheels for current Python versions including 3.14. The code imports `pygame` exactly as normal, so nothing changes in how you write or read it.

If you previously installed classic `pygame`, uninstall it first so the two don't clash: `pip uninstall pygame`.

Your save lives in `spiritbound_save.json` next to the game.

## Controls

| Action | Keyboard | Xbox controller |
|--------|----------|-----------------|
| Move | Arrow keys or WASD | Left stick or D-pad |
| Confirm / Talk / Advance text | Z, Enter, or Space | A |
| Cancel / Back | X, Backspace, or Esc | B |
| Open menu (party, bag, save) | C or Tab | Y |
| Pause | P | Start |
| Run (hold while moving) | Shift | X |

Stick deadzone and button mapping live in `game/config.py` if you want to remap anything.

## What you can do

- Walk a four-map world (Aether Vale, Whisper Route, the Hollow Grove, the Aether Spring) with smooth tile movement, running, and warps between areas.
- Catch wild Aethers in tall grass. Lower their HP, then throw a Bond Crystal. Poisoned and weakened targets bond more easily, and a Prime Crystal raises your odds.
- Raise a party of up to six, with a reserve box for the rest. Aethers gain EXP, learn moves, and evolve at set levels.
- Fight turn-based battles built around four stats (HP, ATK, DEF, SPD), MP-cost abilities, a six-element type chart, buffs and debuffs that stack across six stages, status conditions (poison, burn, paralysis, sleep), battle weather that boosts and weakens elements, and item use mid-fight.
- Face multiple foes at once in some encounters and trainer fights (2-on-1, 3-on-1), choosing which one to strike, with turn order rolled across everyone on the field.
- Swap your active Aether during battle, and reorder your lead from the party menu.
- Battle rival, hiker, and ranger trainers and a final boss, earn coin, and spend it at the supply shop. A village healer patches your team up for free.
- Follow a tracked main quest line and pick up optional side quests from the folk of Aetheria, with a Quests tab in the pause menu showing your current objective.
- Fill out the iDentifi, a catalog of every Aether you've seen and bonded, with each entry's type, weaknesses, resistances, and lore (unknown ones stay silhouetted until you meet them).
- Reach one of several endings, chosen by how you played: how widely you bonded, how much you helped the folk of Aetheria, and the path you walked to the Spring.
- Save and continue from the title screen or the pause menu.

Lose a battle and you wake back in Aether Vale with a healed party. No harsh penalty, no lost progress.

## How the code is laid out

```
main.py              entry point: window, save path, main loop
requirements.txt
game/
  config.py          tunables, palette, controller mapping, screen size
  input.py           merged keyboard + controller input, hot-plug aware
  core.py            App, the state stack, font cache, draw helpers
  data.py            species, moves, items, type chart, XP math (no pygame)
  entities.py        Aether, Party, Inventory, GameData save model (no pygame)
  ui.py              procedural creatures, player, NPCs, textbox, menus
  maps.py            tile maps, warps, encounters, NPCs, chests, rendering
  battle.py          turn-based battle: damage, status, catch, XP, menus
  overworld.py       movement, collision, encounters, interaction, camera
  menus.py           title, starter pick, dialogue, pause, shop, game over
  quests.py          quest table + state helpers: main line + side quests (no pygame)
  dex.py             iDentifi catalog: order, seen/bonded status, completion (no pygame)
  endings.py         branching-ending buckets + a choose(save) selector (no pygame)
tests/
  test_logic.py      headless tests for data, entities, maps, battle, quests, dex, status/weather, endings
```

`data.py` and `entities.py` hold no pygame imports, which is what lets the test suite check the rules without a display.

## Tests

The suite runs headless with a dummy video driver, so it needs no window.

```
python tests/test_logic.py
```

It also works under pytest if you have it:

```
pip install pytest
pytest tests/
```

The tests cover the type chart, the XP curve, leveling and evolution, party overflow into reserve, save and load round-trips, every map's shape and reachability (a flood fill confirms warps, NPCs, and chests can all be walked to), the battle outcomes (knockout, catch, trainer reward, loss callback), multi-creature battles (a multi-foe field, reserve send-out, target redirection, catching one foe mid-fight, and the 1-on-1 path staying unchanged), status conditions and weather (ticks, burn's damage cut, paralysis and sleep turn-skips, weather multipliers), the quest system (state transitions, objective matching, reward granting, and a full main-line walkthrough), the iDentifi (seen/bonded tracking, completion tallies, and save backfill), and the branching endings (each bucket is reachable and the selector is total).

## Download a ready-built executable

Every tagged release ships a standalone Windows build. Grab the latest
`Spiritbound.exe` from the [Releases page](https://github.com/HawaiizFynest/spiritbound/releases/latest),
double-click it, and play. Nothing to install. The save file is written next to
the executable.

## Build a standalone executable yourself

PyInstaller bundles the game into one file. The window icon is rendered
procedurally by `build_icon.py`, so build it first if you want the crystal icon
embedded. **Use the bundled spec — it packs the `assets/` folder (music, sound
effects, sprite art) into the EXE so audio and sprites work in the build:**

```
pip install pyinstaller
python build_icon.py
pyinstaller Spiritbound.spec
```

The executable lands in `dist/`. The save file writes next to it.

If you'd rather use a one-line command instead of the spec, you must include the
asset folder yourself with `--add-data` (use `;` on Windows, `:` on macOS/Linux):

```
python -m PyInstaller --onefile --noconsole --name Spiritbound --icon spiritbound.ico --collect-submodules game --add-data "assets;assets" main.py
```

Leaving out `--add-data` (or the spec) is why a build can run silently with no
music or sound effects — the audio files never get bundled. As a quick fix for an
already-built EXE, you can also just drop the `assets` folder next to
`Spiritbound.exe`; the game looks there too.

### Automated releases

`.github/workflows/release.yml` does all of this on GitHub's Windows runners:
it runs the test suite, generates the icon, builds the one-file executable, and
attaches it to a Release. It fires when you push a version tag like `v1.0.0`
(in GitHub Desktop: create the tag, then push tags), and can also be run on
demand from the repository's **Actions** tab via **Run workflow**.

## Glossary

### Elements

Two type triangles drive the matchups. Hitting a type you beat deals double damage; hitting a type that beats you deals half.

| Triangle | Beats in a cycle |
|----------|------------------|
| Fire / Plant / Water | Ember > Verdant > Tide > Ember |
| Electric / Wind / Earth | Bolt > Gale > Terra > Bolt |

| Element | Theme |
|---------|-------|
| Ember | Fire |
| Verdant | Plant |
| Tide | Water |
| Bolt | Electric |
| Gale | Wind |
| Terra | Earth |

### Aethers

| Aether | Element | Notes |
|--------|---------|-------|
| Cindle | Ember | Starter, evolves into Pyrachs at level 16 |
| Sprigit | Verdant | Starter, evolves into Floravine at level 16 |
| Driblet | Tide | Starter, evolves into Tidewyrm at level 16 |
| Pyrachs | Ember | Evolved form of Cindle |
| Floravine | Verdant | Evolved form of Sprigit |
| Tidewyrm | Tide | Evolved form of Driblet |
| Magmaw | Ember | Wild |
| Thornkin | Verdant | Wild |
| Coralisk | Tide | Wild |
| Sparrk | Bolt | Wild, evolves into Voltagon at level 18 |
| Voltagon | Bolt | Evolved form of Sparrk |
| Zephlit | Gale | Wild, evolves into Galecrest at level 18 |
| Galecrest | Gale | Evolved form of Zephlit |
| Plumage | Gale | Wild |
| Pebblit | Terra | Wild, evolves into Boulderon at level 18 |
| Boulderon | Terra | Evolved form of Pebblit |
| Tunneler | Terra | Wild |
| Finnow | Tide | Wild, evolves into Marlance at level 20 |
| Marlance | Tide | Evolved form of Finnow |
| Mawbug | Verdant | Wild, evolves into Mantiscar at level 18 |
| Mantiscar | Verdant | Evolved form of Mawbug |
| Cinderbat | Ember | Wild |
| Duneworm | Terra | Wild |
| Glimmer | Bolt | Wild |
| Puffcap | Verdant | Wild |
| Craghorn | Terra | Wild |
| Saltoad | Tide | Wild |
| Breezel | Gale | Wild |
| Voltkit | Bolt | Wild |
| Nullith | Bolt | The hollow guardian. A boss, and it cannot be bonded |

### Terms

| Term | Meaning |
|------|---------|
| Aether | A creature you bond, train, and battle with |
| Bond Crystal | The item you throw to catch a weakened wild Aether |
| Prime Crystal | A stronger crystal with better catch odds |
| Spring Key | Opens the gate to the Aether Spring |
| Reserve | Where caught Aethers go once your party of six is full |
| MP | The pool that ability use draws from; it does not refill on its own outside battle |
| Coin | Currency for the supply shop |

## Repository

https://github.com/HawaiizFynest/spiritbound

## License

Do what you like with it. Rename the world, add maps, write new Aethers, rebalance the type chart. The code is yours to extend.
