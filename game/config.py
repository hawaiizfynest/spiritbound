"""
Spiritbound - global configuration.

Written by LJ "HawaiizFynest" Eblacas
"""

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
GAME_TITLE = "Spiritbound"                 # main wordmark
GAME_SUBTITLE = "Legends of Aetheria"        # shown beneath the wordmark
GAME_TITLE_FULL = "Spiritbound: Legends of Aetheria"
WORLD_NAME = "Aetheria"
TAGLINE = "Bond with the spirits of Aetheria."

TILE = 32                      # pixel size of one map tile (internal render space)
VIEW_W = 25                    # tiles visible horizontally
VIEW_H = 18                    # tiles visible vertically (top rows used for play, bottom for HUD hint)
SCREEN_W = VIEW_W * TILE       # 800 (window width)
SCREEN_H = VIEW_H * TILE       # 576 (window height)
FPS = 60

# Gameplay scenes (overworld + battle) render to a low-res buffer that is then
# scaled up with nearest-neighbour, giving a chunky, zoomed-in GBA look while
# UI/text is drawn crisp at full resolution on top.
ZOOM = 2
VIEW_W_PX = SCREEN_W // ZOOM   # 400 internal px wide  (~12.5 tiles visible)
VIEW_H_PX = SCREEN_H // ZOOM   # 288 internal px tall  (~9 tiles visible)

# ---------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------
WALK_FRAMES = 8                # frames to slide one tile while walking
RUN_FRAMES = 4                 # frames to slide one tile while running (hold Run)
ENCOUNTER_CHANCE = 0.11        # per-step chance to trigger a wild battle in tall grass

# ---------------------------------------------------------------------------
# Palette  (RGB)
# ---------------------------------------------------------------------------
BLACK       = (8, 10, 16)
NEAR_BLACK  = (14, 17, 26)
DARK        = (22, 26, 38)
PANEL       = (30, 35, 50)
PANEL_HI    = (44, 51, 72)
BORDER      = (96, 108, 140)
WHITE       = (236, 240, 248)
GREY        = (150, 158, 178)
DIM         = (96, 104, 124)
ACCENT      = (64, 210, 224)    # cyan, the UI accent
ACCENT_DK   = (28, 120, 132)
GOLD        = (240, 196, 92)
RED         = (224, 84, 84)
GREEN       = (96, 208, 120)
YELLOW      = (236, 206, 96)
BLUE        = (96, 150, 236)
XP_COLOR    = (168, 152, 244)    # periwinkle, the EXP bar (distinct from MP blue)

# World tile colors
C_GRASS     = (58, 110, 64)
C_GRASS_2   = (50, 98, 58)
C_TALL      = (40, 92, 50)
C_TALL_2    = (32, 78, 44)
C_PATH      = (158, 138, 96)
C_PATH_2    = (146, 126, 86)
C_WATER     = (52, 96, 168)
C_WATER_2   = (44, 84, 150)
C_TREE      = (28, 70, 40)
C_TREE_HI   = (40, 96, 54)
C_ROCK      = (92, 92, 104)
C_ROCK_HI   = (120, 120, 134)
C_SAND      = (198, 178, 120)
C_FLOWER    = (220, 120, 150)
C_FLOOR     = (78, 64, 60)
C_FLOOR_2   = (70, 57, 53)
C_WALL      = (60, 50, 70)
C_WALL_HI   = (84, 72, 96)
C_VOID      = (44, 30, 60)
C_VOID_2    = (34, 22, 48)
C_SPRING    = (120, 200, 220)

# ---------------------------------------------------------------------------
# Element colors (used for typing, moves and creature accents)
# ---------------------------------------------------------------------------
ELEMENT_COLORS = {
    "Ember":   (236, 110, 60),
    "Verdant": (96, 196, 96),
    "Tide":    (78, 150, 230),
    "Bolt":    (240, 206, 80),
    "Gale":    (160, 220, 220),
    "Terra":   (180, 140, 86),
}

# ---------------------------------------------------------------------------
# Controller mapping (SDL2 / pygame default layout for Xbox controllers)
# Series X pads over Bluetooth / USB enumerate with these indices on Windows.
# If a particular pad maps differently, adjust these constants only.
# ---------------------------------------------------------------------------
BTN_A = 0          # confirm
BTN_B = 1          # cancel / back
BTN_X = 2          # (free / used as Run alongside dpad)
BTN_Y = 3          # open menu
BTN_LB = 4
BTN_RB = 5
BTN_BACK = 6       # view button
BTN_START = 7      # start / pause
AXIS_LX = 0        # left stick horizontal
AXIS_LY = 1        # left stick vertical
STICK_DEADZONE = 0.45

# Save file
SAVE_FILE = "spiritbound_save.json"
