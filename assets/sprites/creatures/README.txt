Crystal Bound - creature sprite drop-in folder
==============================================

Put a PNG here named exactly <species_id>.png and the game loads it
automatically in place of the built-in procedural art. No code changes needed.
If a file is missing, that creature falls back to the procedural sprite.

Guidelines
----------
- Transparent background (RGBA PNG).
- Draw the creature FACING RIGHT; the game flips it for left-facing automatically.
- Square-ish canvas works best (e.g. 48x48 or 64x64). The image is scaled to fit
  and centred, with nearest-neighbour scaling so pixel art stays crisp.
- Keep it readable small - the same sprite is used in the party list, battle,
  and the iDentifi screen at various sizes.

Packaging the EXE
-----------------
Bundle this folder with PyInstaller:
    --add-data "assets/sprites;assets/sprites"      (Windows)
    --add-data "assets/sprites:assets/sprites"      (macOS / Linux)

Species ids (file name = id + ".png")
-------------------------------------
cindle  sprigit  driblet  pyrachs  floravine  tidewyrm  magmaw  thornkin
coralisk  sparrk  voltagon  zephlit  galecrest  plumage  pebblit  boulderon
tunneler  finnow  marlance  mawbug  mantiscar  cinderbat  duneworm  glimmer
puffcap  craghorn  saltoad  breezel  voltkit  nullith
