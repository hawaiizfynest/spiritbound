Crystal Bound - player / NPC sprite drop-in folder
==================================================

Characters load a PNG from here automatically, picked in this order:
  1. <npc-name-slug>.png   e.g. "Mentor Wren"  -> mentor_wren.png   (one NPC)
  2. <role>.png            e.g. that NPC's "pal" -> mentor.png        (all of that role)
  3. built-in procedural art (if neither file exists)
The player uses player.png. No code changes needed; missing files just fall back.

Name slug rule: lowercase, non-letters/digits -> "_"  ("Tender Iris" -> tender_iris).

Facing (overworld characters face up / down / left / right)
----------------------------------------------------------
Simplest: one file (e.g. mentor.png) drawn front-facing - it's used for every
direction, auto-flipped for left. For nicer results, add directional files:
  <key>_down.png  <key>_up.png  <key>_left.png  <key>_right.png
  <key>_side.png  (used for BOTH sides; auto-flipped for left)
A missing direction falls back: side -> other side flipped -> base <key>.png.

Guidelines
----------
- Transparent background (RGBA PNG); feet at the BOTTOM of the image (it stands
  on its shadow). Taller-than-wide canvas works well, e.g. 48x64.
- Draw side/base art facing RIGHT (the game flips it for left).
- Nearest-neighbour scaling keeps pixel art crisp.

Packaging the EXE
-----------------
    --add-data "assets/sprites;assets/sprites"      (Windows)
    --add-data "assets/sprites:assets/sprites"      (macOS / Linux)

Role (pal) names in the game - use as <role>.png (tier 2)
---------------------------------------------------------
elder fisher hiker kid mentor nurse ranger rival scholar shop villager 
(plus player.png for the player)
