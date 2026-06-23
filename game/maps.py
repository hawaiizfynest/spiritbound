"""
Spiritbound - world maps.

Each map is authored as a grid of single characters (see TILE_DEFS for the
legend). A Map instance knows how to test walkability, look up warps / signs /
NPCs / chests, roll wild encounters and render its visible tiles procedurally
(no image files). NPCs, chests and trainer battles are described as plain data
so the overworld can drive them generically.

Written by LJ "HawaiizFynest" Eblacas
"""

import math
import random
import pygame

from . import config as C

# ---------------------------------------------------------------------------
# Tile legend:  char -> (walkable, kind)
#   kind drives both collision and rendering.
# ---------------------------------------------------------------------------
TILE_DEFS = {
    ".": (True,  "grass"),
    ",": (True,  "grass2"),
    "\"": (True, "tall"),     # tall grass -> wild encounters
    "*": (True,  "flower"),
    "=": (True,  "path"),
    "s": (True,  "sand"),
    "f": (True,  "floor"),
    "~": (False, "water"),
    "T": (False, "tree"),
    "R": (False, "rock"),
    "#": (False, "wall"),
    "S": (False, "spring"),
    "g": (False, "gate"),
    "X": (False, "void"),
    " ": (False, "void"),
    # interiors + buildings
    "d": (True,  "door"),       # building entrance (warps inside)
    "e": (True,  "exit"),       # interior exit mat (warps back outside)
    "F": (True,  "ifloor"),     # interior wood floor
    "W": (False, "iwall"),      # interior wall
    "w": (False, "window"),     # interior wall with a window
    "b": (False, "bed"),
    "t": (False, "table"),
    "c": (False, "chair"),
    "h": (False, "shelf"),
    "r": (True,  "rug"),
    "p": (False, "plant"),
    "K": (False, "counter"),
    "m": (False, "fireplace"),
    # cave / dungeon biome
    "o": (True,  "cfloor"),     # cave stone floor
    "O": (False, "cwall"),      # cave rock wall
    "v": (False, "crystal"),    # glowing crystal cluster
    "A": (False, "stalag"),     # stalagmite formation
    "L": (False, "lava"),       # lava (hazard / blocked)
    # beach / coast biome (dry sand reuses "s")
    "z": (True,  "wetsand"),    # damp shoreline sand
    "Z": (False, "sea"),        # ocean water
    "P": (False, "palm"),       # palm tree
    "B": (False, "beachrock"),  # beach boulder
    "l": (True,  "shell"),      # shell / decoration on sand
    "D": (True,  "dock"),       # wooden pier plank (fishing spot)
}


def _walkable_char(ch):
    return TILE_DEFS.get(ch, (False, "void"))[0]


def _kind(ch):
    return TILE_DEFS.get(ch, (False, "void"))[1]


# ===========================================================================
# Map grids  (validated rectangular)
# ===========================================================================
VALE_GRID = [
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "T..........................T",
    "T..#####....*....#####.....T",
    "T..#####....*....#####.....T",
    "T..#d###....*....###d#.....T",
    "T..........======..........T",
    "T...,,================,,...T",
    "T...,......==~~~~.....,....T",
    "T..........==~~~~..........T",
    "T..........==============.=.",
    "T..........==...............",
    "T..........==.......#####..T",
    "T..........==.......#####..T",
    "T..........==.......##d##..T",
    "T.....,,...==..............T",
    "T..........==.......,,.....T",
    "T..........==..............T",
    "T..........................T",
    "T..........................T",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTT",
]

WHISPER_GRID = [
    "TTTTTTTTTTTTTT..TTTTTTTTTTTTTT",
    "T.............==.............T",
    "T.............==.............T",
    "T..\"\"\"\"\"...TT.==.............T",
    "T..\"\"\"\"\"...TT.==.............T",
    "T..\"\"\"\"\"......=======........T",
    "T..\"\"\"\"\"............=........T",
    "T...................=.\"\"\"\"\"\".T",
    "T...........\"\"\"\"\"\"\".=.\"\"\"\"\"\".T",
    ".=========..\"\"\"\"\"\"\".=.\"\"\"\"\"\".T",
    ".........=..\"\"\"\"\"\"\".=.\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"\"=..\"\"\"\"\"\"\".=.\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"\"=..\"\"\"\"\"\"\".=.\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"\"=..\"\"\"\"\"\"\".=.\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"\"=..\"\"\"\"\"\"\".=........T",
    "T.\"\"\"\"\"\"\"=..........=........T",
    "T........=..........=..~~~~~.T",
    "T........============..~~~~~.T",
    "T................RRR...~~~~~.T",
    "T................RRR...~~~~~.T",
    "T............................T",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
]

GROVE_GRID = [
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "TRRRRRRRRRRRRRggRRRRRRRRRRRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRffffffffffffffffffffffRRRT",
    "TRRRRRRRRRRRffffffRRRRRRRRRRRT",
    "T...........ffffff...........T",
    "T...........ffffff....~~~~~~.T",
    "T........\"\"\"\"f==f\"\"\"\".~~~~~~.T",
    "T........\"\"\"\".==.\"\"\"\".~~~~~~.T",
    "T........\"\"\"\".==.\"\"\"\".~~~~~~.T",
    "T........\"\"\"\".==.\"\"\"\"........T",
    "T.......==============.......T",
    "T.\"\"\"\"\"\"......==..\"\"\"\"\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"......==..\"\"\"\"\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"......==..\"\"\"\"\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"......==..\"\"\"\"\"\"\"\"\"\".T",
    "T.\"\"\"\"\"\"......==..\"\"\"\"\"\"\"\"\"\".T",
    "T.............==.............T",
    "TTTTTTTTTTTTTT..TTTTTTTTTTTTTT",
]

SPRING_GRID = [
    "RRRRRRRRRRRRRRRRRRRRRRRR",
    "RXXXXXXXXXXXXXXXXXXXXXXR",
    "RXffffffffffffffffffffXR",
    "RXffffffSSSSSSSSffffffXR",
    "RXffffffSSSSSSSSffffffXR",
    "RXffffffSSSSSSSSffffffXR",
    "RXffffffSSSSSSSSffffffXR",
    "RXffffffffffffffffffffXR",
    "RXffffffffffffffffffffXR",
    "RXffRffffffffffffffRffXR",
    "RXffffffffffffffffffffXR",
    "RXffffffffffffffffffffXR",
    "RXfffffffff==fffffffffXR",
    "RXfffRfffff==fffffRfffXR",
    "RXfffffffff==fffffffffXR",
    "RXfffffffff==fffffffffXR",
    "RXXXXXXXXXX==XXXXXXXXXXR",
    "RRRRRRRRRRR..RRRRRRRRRRR",
]


# --- Building interiors (13 wide x 9 tall: fills the viewport, no void) ---
SHOP_GRID = [
    "WWwWWWWWWwWWW",
    "WhhhFFFFFhhhW",
    "WFFFFFFFFFFFW",
    "WFKKKFFFKKKFW",
    "WFFFFFFFFFFFW",
    "WFFFFFFFFFFFW",
    "WFFFFrrFFFFFW",
    "WFFFFFFFFFFFW",
    "WWWWWWeWWWWWW",
]

CLINIC_GRID = [
    "WWwWWWWWwWWWW",
    "WbbFFFFFFbbFW",
    "WFFFFFFFFFFFW",
    "WFKKKFFFKKKFW",
    "WFFFFFFFFFFFW",
    "WpFFFFFFFFFpW",
    "WFFFFrrFFFFFW",
    "WFFFFFFFFFFFW",
    "WWWWWWeWWWWWW",
]

HOUSE_GRID = [
    "WWwWWWWWWwWWW",
    "WbFFmFFFhhFFW",
    "WFFFFFFFFFFFW",
    "WFcttcFFFFFFW",
    "WFFFFFFFFppFW",
    "WFFFFFFFFFFFW",
    "WFrrFFFFFFFFW",
    "WFFFFFFFFFFFW",
    "WWWWWWeWWWWWW",
]


# ===========================================================================
# Map definitions (warps, encounter tables, npcs, chests)
#
# warp value: {"to","tx","ty","face", optional "need_item","locked"}
# npc:        {"x","y","face","pal"|"creature","name","lines",
#              optional "script","heal","shop","battle","win_lines",
#              "defeat_flag","gives","gives_flag","sign","reward"}
# chest:      {"x","y","item","qty","flag"}
# ===========================================================================
MAP_DEFS = {
    "vale": {
        "name": "Vale Village",
        "grid": VALE_GRID,
        "encounters": [],
        "warps": {
            (27, 9):  {"to": "whisper", "tx": 1, "ty": 9, "face": "right"},
            (27, 10): {"to": "whisper", "tx": 1, "ty": 10, "face": "right"},
            (4, 4):   {"to": "clinic_in", "tx": 6, "ty": 7, "face": "up"},
            (20, 4):  {"to": "house_in",  "tx": 6, "ty": 7, "face": "up"},
            (22, 13): {"to": "shop_in",   "tx": 6, "ty": 7, "face": "up"},
        },
        "npcs": [
            {"x": 19, "y": 5, "face": "down", "pal": "mentor", "name": "Mentor Wren",
             "script": "starter",
             "lines": [
                 "Ah, there you are. The Aether Spring at the heart of Aetheria has gone quiet.",
                 "Its guardian, Nullith, has fallen hollow, and Aetheria's spirits are scattering.",
                 "You have the knack for bonding, I can tell. Choose a companion and go to it.",
             ],
             "gives": [("bond_crystal", 5)], "gives_flag": "got_starter_kit",
             "win_lines": [
                 "Your team looks rested. The Spring lies north, past Whisper Route and the Grove.",
                 "Bond with the wild Aethers you meet. Strength in numbers, strength in trust.",
             ]},
            {"x": 5, "y": 5, "face": "down", "pal": "elder", "name": "Elder Mara",
             "lines": [
                 "In my youth the Spring sang at dawn. Now there is only static on the wind.",
                 "If anyone can mend the bond, it is one who bonds freely. Be careful up there.",
             ]},
            {"x": 14, "y": 15, "face": "down", "pal": "villager", "name": "Villager",
             "lines": [
                 "Tomas runs the supply shop - the building with the door down the southeast path.",
                 "And Tender Iris sees to weary Aethers in the clinic, the house up the northwest.",
             ]},
            {"x": 16, "y": 16, "face": "down", "pal": "kid", "name": "Kid",
             "lines": ["When I'm older I'm gonna bond a Voltkit! They stick to your head, you know."]},
            {"x": 17, "y": 7, "face": "left", "pal": "fisher", "name": "Fisher Pell",
             "offers": ["pell_salves"],
             "reactions": [
                 {"stat": "luck", "min": 5, "once": "pell_gift",
                  "give": ("bond_crystal", 2),
                  "lines": ["Well now - the current washed these right up at your feet.",
                            "Lucky sort, aren't you? Go on, they're yours."]},
             ],
             "lines": [
                 "Finnow used to crowd this pond. Lately they spook at the static in the air.",
                 "Bond a fast one and it'll evolve into a Marlance. Now that's a catch.",
             ]},
            {"x": 16, "y": 12, "face": "down", "pal": "scholar", "name": "Scholar Aldo",
             "reactions": [
                 {"stat": "insight", "min": 4,
                  "lines": ["You've a sharp eye - so here's the deeper trick:",
                            "Physical moves test a foe's Defense; elemental ones test its Sp. Def. Aim at the weaker wall.",
                            "And a nimble Aether lands more critical hits - Agility bites where Speed only races."]},
             ],
             "lines": [
                 "Six elements, two cycles. Ember bows to Tide, yet scorches Verdant. Round and round.",
                 "Match your move's element against the foe's weakness and you'll hit twice as hard.",
             ]},
            {"x": 9, "y": 7, "face": "down", "sign": True,
             "name": "Sign",
             "lines": ["VALE VILLAGE  -  A quiet corner of Aetheria, home of the Spring-tenders. Please don't feed the Magmaw."]},
        ],
        "chests": [],
    },

    "shop_in": {
        "name": "Tomas's Supplies",
        "grid": SHOP_GRID,
        "encounters": [],
        "warps": {
            (6, 8): {"to": "vale", "tx": 22, "ty": 14, "face": "down"},
        },
        "npcs": [
            {"x": 6, "y": 3, "face": "down", "pal": "shop", "name": "Tomas",
             "shop": True,
             "reactions": [
                 {"stat": "charisma", "min": 4,
                  "lines": ["Ah, a friendly face! My prices always bend for folks I like.",
                            "Take a look - you'll find them kinder than the tag says."]},
             ],
             "lines": ["Welcome in! Heading into the wild? Stock up first - a bonded Aether is a hungry one."]},
            {"x": 2, "y": 7, "face": "right", "sign": True, "name": "Notice",
             "lines": ["TOMAS'S SUPPLIES  -  Cards, salves, and curios for the road ahead."]},
        ],
        "chests": [],
    },

    "clinic_in": {
        "name": "Vale Clinic",
        "grid": CLINIC_GRID,
        "encounters": [],
        "warps": {
            (6, 8): {"to": "vale", "tx": 4, "ty": 5, "face": "down"},
        },
        "npcs": [
            {"x": 6, "y": 3, "face": "down", "pal": "nurse", "name": "Tender Iris",
             "heal": True,
             "reactions": [
                 {"stat": "charisma", "min": 5, "once": "iris_gift",
                  "give": ("greater_salve", 1),
                  "lines": ["There - rested and ready. You've a kind way about you.",
                            "Here, take this. I save a few for travellers I trust."]},
             ],
             "lines": [
                 "You look road-worn. Here - let me see to your Aethers.",
                 "There. Rested and ready. Come back any time before you head out.",
             ]},
            {"x": 10, "y": 5, "face": "down", "pal": "villager", "name": "Patient",
             "lines": ["My Pebblit took a tumble on the route. Iris had it back on its feet in no time."]},
        ],
        "chests": [],
    },

    "house_in": {
        "name": "Vale Home",
        "grid": HOUSE_GRID,
        "encounters": [],
        "warps": {
            (6, 8): {"to": "vale", "tx": 20, "ty": 5, "face": "down"},
        },
        "npcs": [
            {"x": 8, "y": 5, "face": "down", "pal": "elder", "name": "Gran Edda",
             "offers": ["edda_finnow"],
             "lines": [
                 "Make yourself at home, dear. The kettle's always on for a bonder.",
                 "They say the Spring chose this valley because the folk here share so freely.",
             ]},
            {"x": 3, "y": 5, "face": "right", "pal": "kid", "name": "Little Pim",
             "lines": ["Mama says I can't have an Aether till I'm ten. I'm seven and three quarters!"]},
            {"x": 9, "y": 2, "face": "down", "pal": "scholar", "name": "Bookkeeper Toll",
             "reactions": [
                 {"stat": "insight", "min": 4,
                  "lines": ["A reader, are you? Then here's a margin note:",
                            "An Aether's element decides which wall its moves test - aim at the weaker one and the bond comes quicker, too."]},
             ],
             "lines": ["So many ledgers, so little shelf. Mind the stacks by the bookcase."]},
        ],
        "chests": [
            {"x": 1, "y": 6, "item": "salve", "qty": 2, "flag": "house_chest"},
        ],
    },

    "whisper": {
        "name": "Whisper Route",
        "grid": WHISPER_GRID,
        "encounters": [
            ("thornkin", 26, 3, 6),
            ("sparrk",   22, 3, 6),
            ("zephlit",  22, 3, 6),
            ("pebblit",  18, 4, 6),
            ("mawbug",   20, 3, 6),
            ("voltkit",  18, 4, 6),
            ("breezel",  16, 4, 6),
        ],
        "warps": {
            (0, 9):   {"to": "vale", "tx": 25, "ty": 9, "face": "left"},
            (0, 10):  {"to": "vale", "tx": 25, "ty": 10, "face": "left"},
            (14, 0):  {"to": "grove", "tx": 14, "ty": 22, "face": "up"},
            (15, 0):  {"to": "grove", "tx": 15, "ty": 22, "face": "up"},
        },
        "npcs": [
            {"x": 9, "y": 12, "face": "down", "pal": "rival", "name": "Rival Kade",
             "reactions": [
                 {"stat": "charisma", "min": 5,
                  "lines": ["So the whole route's talking about you now. Figures.",
                            "Reputation won't save you here - let's see those Aethers!"]},
             ],
             "lines": [
                 "Knew I'd run into you out here. Caught anything worth bragging about yet?",
                 "Let's see what your bond is made of. Don't hold back!",
             ],
             "battle": [("zephlit", 6), ("magmaw", 7)],
             "reward": 240,
             "defeat_flag": "rival1_beaten",
             "offers": ["kade_starter_lesson"],
             "win_lines": [
                 "Tch. Your team actually listens to you. Respect.",
                 "Go on, the Grove's just north. Watch the cavern; the wild ones there hit harder.",
             ]},
            {"x": 24, "y": 14, "face": "down", "pal": "hiker", "name": "Hiker Bem",
             "lines": [
                 "Been tromping these routes since sunup. Found a Voltkit stuck to my pack!",
                 "You look like a bonder. Quick scrap before you move on?",
             ],
             "battle": [("voltkit", 6), ("mawbug", 7)],
             "reward": 200,
             "defeat_flag": "hiker1_beaten",
             "hunt": {"sight": 4, "speed": 0.16,
                      "alert": "A challenger! You're not slipping past me!"},
             "win_lines": [
                 "Hah! Lighter on your feet than you look. Off you go.",
             ]},
            {"x": 6, "y": 20, "face": "down", "pal": "rival", "name": "Masked Bandit",
             "lines": [
                 "Heh. Nice Aethers. Be a shame if someone... relieved you of them.",
                 "Lose to me and I take the lot. Still want to try your luck?",
             ],
             "battle": [("duneworm", 8), ("cinderbat", 9)],
             "reward": 320,
             "defeat_flag": "bandit_beaten",
             "robber": "masked_bandit",
             "recover_lines": [
                 "Argh - fine, fine! Take your stuff back, it's cursed luck anyway.",
                 "Your stolen items and Aethers are returned to you!",
             ],
             "win_lines": [
                 "You actually beat me. Don't let it go to your head.",
             ]},
            {"x": 2, "y": 16, "face": "down", "sign": True, "name": "Sign",
             "lines": ["WHISPER ROUTE  -  Wild Aethers stir in the tall grass. Weaken one before you bond it."]},
        ],
        "chests": [
            {"x": 26, "y": 19, "item": "bond_crystal", "qty": 3, "flag": "chest_whisper_1"},
        ],
    },

    "grove": {
        "name": "Hollow Grove",
        "grid": GROVE_GRID,
        "weather": "sandstorm",
        "double_chance": 0.22,
        "encounters": [
            ("coralisk", 16, 9, 13),
            ("plumage",  16, 9, 13),
            ("tunneler", 16, 9, 13),
            ("magmaw",   14, 10, 14),
            ("voltagon",  8, 12, 14),
            ("galecrest", 8, 12, 14),
            ("cinderbat", 14, 9, 13),
            ("duneworm",  14, 10, 14),
            ("craghorn",  12, 10, 14),
            ("puffcap",   14, 9, 13),
            ("saltoad",   12, 9, 13),
            ("finnow",    12, 9, 13),
            ("glimmer",    8, 12, 14),
        ],
        "warps": {
            (14, 23): {"to": "whisper", "tx": 14, "ty": 1, "face": "down"},
            (15, 23): {"to": "whisper", "tx": 15, "ty": 1, "face": "down"},
            (14, 2):  {"to": "spring", "tx": 11, "ty": 15, "face": "up",
                       "need_item": "spring_key",
                       "locked": "A sealed gate hums with old Aether. It needs the Spring Key."},
            (15, 2):  {"to": "spring", "tx": 11, "ty": 15, "face": "up",
                       "need_item": "spring_key",
                       "locked": "A sealed gate hums with old Aether. It needs the Spring Key."},
        },
        "npcs": [
            {"x": 22, "y": 10, "face": "down", "pal": "ranger", "name": "Ranger Sela",
             "lines": [
                 "Hold there. The grove's wild ones are jumpy with the Spring gone sour.",
                 "If you mean to reach the gate, prove your team can handle the climb.",
             ],
             "battle": [("cinderbat", 12), ("craghorn", 13), ("duneworm", 12)],
             "active": 2,
             "reward": 360,
             "defeat_flag": "ranger1_beaten",
             "win_lines": [
                 "Good. Your Aethers trust you - they'll need to, up at the Spring.",
                 "The Key was lost somewhere in this grove. Search the far corners.",
             ]},
            {"x": 8, "y": 16, "face": "down", "sign": True, "name": "Sign",
             "lines": ["HOLLOW GROVE  -  The sealed gate north leads to the Spring. The Key was lost in the grove long ago."]},
        ],
        "chests": [
            {"x": 25, "y": 17, "item": "spring_key", "qty": 1, "flag": "got_spring_key"},
            {"x": 3, "y": 17, "item": "greater_salve", "qty": 2, "flag": "chest_grove_1"},
            {"x": 24, "y": 6, "item": "prime_crystal", "qty": 1, "flag": "chest_grove_2"},
        ],
    },

    "spring": {
        "name": "Aether Spring",
        "grid": SPRING_GRID,
        "encounters": [],
        "warps": {
            (11, 17): {"to": "grove", "tx": 14, "ty": 3, "face": "down"},
            (12, 17): {"to": "grove", "tx": 14, "ty": 3, "face": "down"},
        },
        "npcs": [
            {"x": 11, "y": 7, "face": "down", "creature": "nullith", "name": "Nullith",
             "lines": [
                 "The hollow guardian turns toward you. Static crackles where its voice should be.",
                 "It does not know you. It remembers only the Spring, and the silence that took it.",
             ],
             "battle": [("nullith", 25)],
             "boss": True,
             "defeat_flag": "nullith_beaten",
             "win_lines": [
                 "As the last spark fades, Nullith's form softens - and the Spring draws a long, clear breath.",
                 "Light returns to the water. Somewhere far below, the land remembers how to sing.",
                 "You did not conquer the guardian. You reminded it how to bond. Spiritbound - thank you for playing.",
             ]},
        ],
        "chests": [],
    },
}


# ===========================================================================
# Map class
# ===========================================================================
class Map:
    def __init__(self, map_id):
        d = MAP_DEFS[map_id]
        self.id = map_id
        self.name = d["name"]
        self.grid = d["grid"]
        self.h = len(self.grid)
        self.w = max(len(r) for r in self.grid)
        # pad rows defensively (all our grids are already rectangular)
        self.grid = [r.ljust(self.w, "X") for r in self.grid]
        self.warps = d.get("warps", {})
        self.encounters = d.get("encounters", [])
        self.npcs = d.get("npcs", [])
        self.chests = d.get("chests", [])
        self.weather = d.get("weather")     # optional ambient battle weather id
        self.double_chance = d.get("double_chance", 0.0)  # chance of a 2-foe wild pack

    # --- queries -----------------------------------------------------------
    def char_at(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            return self.grid[y][x]
        return "X"

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def tile_walkable(self, x, y):
        return _walkable_char(self.char_at(x, y))

    def is_tall(self, x, y):
        return _kind(self.char_at(x, y)) == "tall"

    def warp_at(self, x, y):
        return self.warps.get((x, y))

    def sign_at(self, x, y):
        for n in self.npcs:
            if n.get("sign") and n["x"] == x and n["y"] == y:
                return n
        return None

    def npc_at(self, x, y):
        for n in self.npcs:
            if n["x"] == x and n["y"] == y:
                return n
        return None

    def chest_at(self, x, y):
        for ch in self.chests:
            if ch["x"] == x and ch["y"] == y:
                return ch
        return None

    def roll_encounter(self):
        """Pick (species_id, level) from this map's weighted table, or None."""
        if not self.encounters:
            return None
        total = sum(e[1] for e in self.encounters)
        r = random.uniform(0, total)
        upto = 0
        for sid, weight, lo, hi in self.encounters:
            upto += weight
            if r <= upto:
                return sid, random.randint(lo, hi)
        sid, _, lo, hi = self.encounters[-1]
        return sid, random.randint(lo, hi)

    # --- validation (used by tests) ---------------------------------------
    def validate(self, opened_flags=()):
        """Sanity-check authored placements. Returns a list of problems."""
        problems = []
        for (wx, wy) in self.warps:
            if not self.in_bounds(wx, wy):
                problems.append(f"{self.id}: warp at ({wx},{wy}) out of bounds")
        def has_walk_neighbor(x, y):
            return any(self.tile_walkable(x + dx, y + dy)
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        for n in self.npcs:
            x, y = n["x"], n["y"]
            if not self.in_bounds(x, y):
                problems.append(f"{self.id}: npc '{n.get('name')}' at ({x},{y}) out of bounds")
            elif not has_walk_neighbor(x, y):
                problems.append(f"{self.id}: npc '{n.get('name')}' at ({x},{y}) unreachable")
        for c in self.chests:
            x, y = c["x"], c["y"]
            if not self.in_bounds(x, y):
                problems.append(f"{self.id}: chest at ({x},{y}) out of bounds")
            elif not has_walk_neighbor(x, y):
                problems.append(f"{self.id}: chest at ({x},{y}) unreachable")
        return problems

    # --- rendering ---------------------------------------------------------
    def draw(self, surf, cam_px, cam_py):
        """Draw visible tiles. cam_px/cam_py is the top-left world pixel."""
        t = C.TILE
        x0 = max(0, cam_px // t)
        y0 = max(0, cam_py // t)
        x1 = min(self.w, (cam_px + C.SCREEN_W) // t + 1)
        y1 = min(self.h, (cam_py + C.SCREEN_H) // t + 1)
        for ty in range(y0, y1):
            for tx in range(x0, x1):
                sx = tx * t - cam_px
                sy = ty * t - cam_py
                _draw_tile(surf, self, sx, sy, tx, ty)


# ===========================================================================
# Tile rendering (procedural, baked into cached surfaces)
# ===========================================================================
import random as _random


def _lt(c, f):
    return (min(255, int(c[0] + (255 - c[0]) * f)), min(255, int(c[1] + (255 - c[1]) * f)),
            min(255, int(c[2] + (255 - c[2]) * f)))


def _dk(c, f):
    return (max(0, int(c[0] * (1 - f))), max(0, int(c[1] * (1 - f))), max(0, int(c[2] * (1 - f))))


def _mx(a, b, f):
    return (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), int(a[2] + (b[2] - a[2]) * f))


def _rng(*key):
    return _random.Random(hash(key) & 0xffffffff)


_VARIANTS = 6
_tile_cache = {}      # kind -> [Surface,...]
_anim_cache = {}      # kind -> [frame Surface,...]
_FOAM = None


def _grass_surf(seed):
    t = C.TILE
    s = pygame.Surface((t, t))
    base = C.C_GRASS if seed % 2 == 0 else C.C_GRASS_2
    s.fill(base)
    r = _rng("grass", seed)
    # very soft, sparse mottling so large grass areas read as texture, not a pattern
    if r.random() < 0.55:
        pygame.draw.ellipse(s, _dk(base, 0.05),
                            (r.randint(2, t - 12), r.randint(2, t - 10),
                             r.randint(8, 12), r.randint(5, 8)))
    # an occasional small grass tuft (little v shapes)
    for _ in range(r.randint(0, 2)):
        x = r.randint(5, t - 6); y = r.randint(t // 2, t - 5)
        pygame.draw.line(s, _dk(base, 0.2), (x, y), (x - 2, y - 4), 1)
        pygame.draw.line(s, _dk(base, 0.2), (x, y), (x + 2, y - 4), 1)
        pygame.draw.line(s, _lt(base, 0.18), (x + 1, y), (x + 1, y - 3), 1)
    return s


def _ifloor_surf(seed):
    """Warm wood-plank interior floor; used as the base for furniture tiles."""
    t = C.TILE
    r = _rng("ifloor", seed)
    base = (164, 126, 84)
    s = pygame.Surface((t, t)); s.fill(base)
    plank_h = t // 2
    for py in range(0, t, plank_h):
        shade = _lt(base, 0.05) if (py // plank_h) % 2 == 0 else _dk(base, 0.06)
        pygame.draw.rect(s, shade, (0, py, t, plank_h))
        pygame.draw.line(s, _dk(base, 0.30), (0, py), (t, py), 1)
        pygame.draw.line(s, _lt(base, 0.10), (0, py + 1), (t, py + 1), 1)
    off = (seed % 2) * (t // 2)
    pygame.draw.line(s, _dk(base, 0.22), (off % t, 0), (off % t, plank_h), 1)
    pygame.draw.line(s, _dk(base, 0.22), ((off + t // 2) % t, plank_h),
                     ((off + t // 2) % t, t), 1)
    for _ in range(8):
        s.set_at((r.randint(0, t - 1), r.randint(0, t - 1)), _dk(base, 0.12))
    return s


def _cfloor_surf(seed):
    """Dark stone cave floor; base for crystal/stalagmite tiles."""
    t = C.TILE
    r = _rng("cfloor", seed)
    base = (74, 72, 88)
    s = pygame.Surface((t, t)); s.fill(base)
    pygame.draw.ellipse(s, _dk(base, 0.08), (r.randint(1, 6), r.randint(1, 6),
                                             r.randint(9, 14), r.randint(7, 10)))
    for _ in range(7):
        s.set_at((r.randint(0, t - 1), r.randint(0, t - 1)),
                 _lt(base, 0.10) if r.random() < 0.5 else _dk(base, 0.13))
    return s


def _bake(kind, seed):
    t = C.TILE
    r = _rng(kind, seed)
    if kind in ("grass", "grass2"):
        return _grass_surf(seed)
    if kind == "tall":
        s = _grass_surf(seed + 7)
        pygame.draw.ellipse(s, _dk(C.C_TALL, 0.25), (2, t - 10, t - 4, 10))
        for bx in (4, 10, 16, 22, 27):
            base_y = t - 3 + r.randint(-1, 1)
            h = r.randint(13, 19)
            pygame.draw.line(s, _dk(C.C_TALL, 0.2), (bx, base_y), (bx, base_y - h), 3)
            pygame.draw.line(s, C.C_TALL, (bx + 1, base_y), (bx + 1, base_y - h + 2), 2)
            pygame.draw.line(s, _lt(C.C_TALL, 0.25), (bx + 1, base_y - h + 2), (bx + 1, base_y - h), 2)
        return s
    if kind == "path":
        s = pygame.Surface((t, t)); s.fill(C.C_PATH)
        for _ in range(26):
            x = r.randint(0, t); y = r.randint(0, t)
            c = _lt(C.C_PATH, 0.12) if r.random() < 0.5 else _dk(C.C_PATH, 0.12)
            s.set_at((x, y), c)
        for _ in range(r.randint(1, 2)):
            x = r.randint(5, t - 5); y = r.randint(5, t - 5); rad = r.randint(2, 3)
            pygame.draw.circle(s, _dk(C.C_PATH, 0.18), (x, y + 1), rad)
            pygame.draw.circle(s, _lt(C.C_PATH, 0.16), (x, y), rad)
        return s
    if kind == "sand":
        s = pygame.Surface((t, t)); s.fill(C.C_SAND)
        for _ in range(30):
            s.set_at((r.randint(0, t - 1), r.randint(0, t - 1)),
                     _dk(C.C_SAND, 0.1) if r.random() < 0.5 else _lt(C.C_SAND, 0.12))
        return s
    if kind == "floor":
        s = pygame.Surface((t, t)); s.fill(C.C_FLOOR)
        h = t // 2
        for by in range(0, t, h):
            for bx in range(0, t, h):
                shade = _lt(C.C_FLOOR, 0.06) if (bx // h + by // h) % 2 == 0 else _dk(C.C_FLOOR, 0.08)
                pygame.draw.rect(s, shade, (bx + 1, by + 1, h - 2, h - 2))
        for k in range(0, t + 1, h):
            pygame.draw.line(s, _dk(C.C_FLOOR, 0.3), (0, k), (t, k), 1)
            pygame.draw.line(s, _dk(C.C_FLOOR, 0.3), (k, 0), (k, t), 1)
        if r.random() < 0.3:
            x = r.randint(4, t - 4)
            pygame.draw.line(s, _dk(C.C_FLOOR, 0.25), (x, 4), (x + r.randint(-4, 4), t - 4), 1)
        return s
    if kind == "void":
        s = pygame.Surface((t, t))
        for y in range(t):
            f = y / t
            pygame.draw.line(s, _mx(C.C_VOID, C.C_VOID_2, f), (0, y), (t, y))
        for _ in range(r.randint(2, 4)):
            x = r.randint(2, t - 2); y = r.randint(2, t - 2)
            s.set_at((x, y), _lt(C.C_VOID, 0.4))
        return s
    if kind == "wall":
        s = pygame.Surface((t, t)); s.fill(C.C_WALL)
        pygame.draw.rect(s, C.C_WALL_HI, (0, 0, t, 7))
        pygame.draw.rect(s, _dk(C.C_WALL, 0.35), (0, t - 6, t, 6))
        # brick seams (staggered)
        pygame.draw.line(s, _dk(C.C_WALL, 0.4), (0, t // 2), (t, t // 2), 2)
        pygame.draw.line(s, _dk(C.C_WALL, 0.4), (t // 2, 7), (t // 2, t // 2), 2)
        off = (seed % 2) * (t // 2)
        pygame.draw.line(s, _dk(C.C_WALL, 0.4), ((off) % t, t // 2), ((off) % t, t - 6), 2)
        pygame.draw.line(s, _lt(C.C_WALL, 0.12), (0, 8), (t, 8), 1)
        return s
    if kind == "rock":
        s = _grass_surf(seed + 3)
        pygame.draw.ellipse(s, (0, 0, 0, 0), (0, 0, 0, 0))
        pygame.draw.ellipse(s, _dk(C.C_GRASS, 0.25), (5, t - 9, t - 10, 8))
        pts = [(5, t - 6), (4, 13), (11, 5), (t - 9, 5), (t - 4, 14), (t - 5, t - 6)]
        pygame.draw.polygon(s, C.C_ROCK, pts)
        pygame.draw.polygon(s, C.C_ROCK_HI, [(11, 5), (t - 9, 5), (t - 13, 14), (12, 15)])
        pygame.draw.polygon(s, _dk(C.C_ROCK, 0.22), [(t - 9, 5), (t - 4, 14), (t - 8, t - 7), (t - 13, 15)])
        pygame.draw.line(s, _dk(C.C_ROCK, 0.3), (14, 7), (16, t - 7), 1)
        return s
    if kind == "tree":
        s = _grass_surf(seed + 5)
        cx, cy = t // 2, t // 2
        pygame.draw.ellipse(s, _dk(C.C_GRASS, 0.34), (cx - 12, t - 9, 24, 8))
        # trunk (shaded)
        pygame.draw.rect(s, (96, 66, 42), (cx - 3, cy + 2, 6, 13))
        pygame.draw.rect(s, (118, 84, 54), (cx - 3, cy + 2, 2, 13))
        pygame.draw.rect(s, (70, 48, 32), (cx + 1, cy + 2, 2, 13))
        # canopy on a temp layer so we can give it one clean dark rim
        lay = pygame.Surface((t, t), pygame.SRCALPHA)
        clumps = ((0, -9, 12), (-8, -2, 9), (8, -2, 9), (-4, 4, 8), (5, 4, 8))
        for dx, dy, rad in clumps:
            pygame.draw.circle(lay, C.C_TREE, (cx + dx, cy + dy), rad)
        rim = pygame.mask.from_surface(lay).to_surface(
            setcolor=(*_dk(C.C_TREE, 0.45), 255), unsetcolor=(0, 0, 0, 0))
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            s.blit(rim, (ox, oy))
        s.blit(lay, (0, 0))
        # highlight + leafy texture
        pygame.draw.circle(s, C.C_TREE_HI, (cx - 4, cy - 11), 6)
        pygame.draw.circle(s, _lt(C.C_TREE_HI, 0.14), (cx - 5, cy - 12), 3)
        rr = _rng("treetex", seed)
        for _ in range(5):
            dx = rr.randint(-9, 9); dy = rr.randint(-14, 3)
            pygame.draw.circle(s, _dk(C.C_TREE, 0.14), (cx + dx, cy + dy), 2)
        return s
    if kind == "tree_old_unused":
        return _grass_surf(seed)
    if kind == "flower":
        s = _grass_surf(seed + 9)
        cx, cy = t // 2 + r.randint(-3, 3), t // 2 + r.randint(-2, 2)
        petal = [(220, 110, 140), (240, 210, 90), (170, 140, 220), (235, 235, 240)][seed % 4]
        pygame.draw.line(s, _dk(C.C_GRASS, 0.1), (cx, cy + 6), (cx, cy + 1), 1)
        for ang in range(0, 360, 72):
            import math as _m
            px = cx + int(4 * _m.cos(_m.radians(ang)))
            py = cy + int(4 * _m.sin(_m.radians(ang)))
            pygame.draw.circle(s, petal, (px, py), 3)
        pygame.draw.circle(s, C.GOLD, (cx, cy), 2)
        return s
    if kind == "gate":
        s = pygame.Surface((t, t)); s.fill(C.C_WALL)
        pygame.draw.rect(s, C.C_WALL_HI, (0, 0, t, 6))
        pygame.draw.rect(s, _dk(C.C_WALL, 0.3), (0, t - 6, t, 6))
        for bx in (7, 15, 23):
            pygame.draw.line(s, C.ACCENT_DK, (bx, 4), (bx, t - 4), 3)
            pygame.draw.line(s, C.ACCENT, (bx, 5), (bx, t - 5), 1)
        pygame.draw.rect(s, C.ACCENT_DK, (1, 1, t - 2, t - 2), width=2)
        return s
    if kind == "ifloor":
        return _ifloor_surf(seed)
    if kind == "iwall":
        base = (150, 116, 82)
        s = pygame.Surface((t, t)); s.fill(base)
        pygame.draw.rect(s, (200, 184, 158), (0, 0, t, int(t * 0.55)))   # plaster upper
        pygame.draw.line(s, (120, 92, 64), (0, int(t * 0.55)), (t, int(t * 0.55)), 2)
        pygame.draw.rect(s, (170, 154, 130), (0, 0, t, 3))               # top highlight
        pygame.draw.rect(s, _dk(base, 0.4), (0, t - 4, t, 4))            # base shadow
        for gx in range(6, t, 8):
            pygame.draw.line(s, _dk(base, 0.15), (gx, int(t * 0.55) + 2), (gx, t - 4), 1)
        return s
    if kind == "window":
        base = (150, 116, 82)
        s = pygame.Surface((t, t)); s.fill((200, 184, 158))
        pygame.draw.rect(s, (118, 90, 62), (5, 4, t - 10, t - 13))       # frame
        pygame.draw.rect(s, (150, 205, 230), (7, 6, t - 14, t - 17))     # sky pane
        pygame.draw.line(s, (205, 232, 246), (8, 8), (t - 9, t - 13), 1)  # glint
        pygame.draw.line(s, (118, 90, 62), (t // 2, 6), (t // 2, t - 11), 2)
        pygame.draw.line(s, (118, 90, 62), (7, (t - 11) // 2 + 2), (t - 8, (t - 11) // 2 + 2), 2)
        pygame.draw.rect(s, _dk(base, 0.4), (0, t - 4, t, 4))
        return s
    if kind == "bed":
        s = _ifloor_surf(seed)
        frame = (122, 84, 52)
        pygame.draw.rect(s, frame, (3, 2, t - 6, t - 4), border_radius=3)
        pygame.draw.rect(s, (238, 236, 240), (6, 4, t - 12, 8), border_radius=2)  # pillow
        blanket = (70, 150, 165)
        pygame.draw.rect(s, blanket, (5, 13, t - 10, t - 17), border_radius=2)
        pygame.draw.line(s, _lt(blanket, 0.18), (5, 16), (t - 5, 16), 1)
        pygame.draw.rect(s, _dk(frame, 0.3), (3, 2, t - 6, t - 4), width=2, border_radius=3)
        return s
    if kind == "table":
        s = _ifloor_surf(seed)
        top = (156, 114, 74)
        pygame.draw.ellipse(s, _dk((164, 126, 84), 0.25), (5, t - 9, t - 10, 7))
        for lx in (7, t - 9):
            pygame.draw.rect(s, (96, 66, 42), (lx, t // 2, 3, t // 2 - 3))
        pygame.draw.rect(s, top, (4, 8, t - 8, 10), border_radius=2)
        pygame.draw.rect(s, _lt(top, 0.16), (4, 8, t - 8, 3), border_radius=2)
        pygame.draw.rect(s, _dk(top, 0.3), (4, 15, t - 8, 3))
        return s
    if kind == "chair":
        s = _ifloor_surf(seed)
        pygame.draw.ellipse(s, _dk((164, 126, 84), 0.22), (9, t - 8, t - 18, 6))
        pygame.draw.rect(s, (120, 86, 54), (11, 5, t - 22, 14), border_radius=2)   # back
        pygame.draw.rect(s, (140, 100, 62), (9, 15, t - 18, 7), border_radius=2)   # seat
        for lx in (10, t - 12):
            pygame.draw.rect(s, (96, 66, 42), (lx, 21, 3, 7))
        return s
    if kind == "shelf":
        s = _ifloor_surf(seed)
        case = (108, 78, 50)
        pygame.draw.rect(s, case, (2, 1, t - 4, t - 3))
        pygame.draw.rect(s, _dk(case, 0.3), (2, 1, t - 4, t - 3), width=2)
        for shy in (10, 19, 28):
            pygame.draw.line(s, _dk(case, 0.4), (3, shy), (t - 3, shy), 2)
        cols = [(190, 72, 72), (70, 120, 180), (80, 160, 90), (210, 180, 80), (150, 90, 170)]
        rr2 = _rng("books", seed)
        for shy in (2, 11, 20):
            bx = 4
            while bx < t - 6:
                bw = rr2.randint(2, 4); bh = rr2.randint(6, 8)
                pygame.draw.rect(s, cols[rr2.randint(0, len(cols) - 1)], (bx, shy + (8 - bh), bw, bh))
                bx += bw + 1
        return s
    if kind == "rug":
        s = _ifloor_surf(seed)
        base, border = (170, 70, 70), (228, 206, 160)
        pygame.draw.rect(s, border, (3, 6, t - 6, t - 12), border_radius=4)
        pygame.draw.rect(s, base, (6, 9, t - 12, t - 18), border_radius=3)
        pygame.draw.rect(s, border, (t // 2 - 3, 9, 6, t - 18))
        pygame.draw.rect(s, border, (6, t // 2 - 3, t - 12, 6))
        return s
    if kind == "plant":
        s = _ifloor_surf(seed)
        pot = (180, 104, 66)
        pygame.draw.polygon(s, pot, [(11, t - 4), (t - 11, t - 4), (t - 13, t - 12), (13, t - 12)])
        pygame.draw.rect(s, _lt(pot, 0.15), (12, t - 12, t - 24, 2))
        leaf = (70, 150, 80)
        for dx, dy in ((0, -6), (-5, -2), (5, -2), (-3, -9), (3, -9)):
            pygame.draw.circle(s, leaf, (t // 2 + dx, t - 13 + dy), 5)
        pygame.draw.circle(s, _lt(leaf, 0.18), (t // 2 - 2, t - 22), 3)
        return s
    if kind == "counter":
        s = _ifloor_surf(seed)
        wood = (140, 100, 62)
        pygame.draw.rect(s, wood, (0, 4, t, t - 8))
        pygame.draw.rect(s, _lt(wood, 0.18), (0, 4, t, 4))
        pygame.draw.rect(s, _dk(wood, 0.32), (0, t - 8, t, 4))
        pygame.draw.line(s, _dk(wood, 0.25), (0, t // 2), (t, t // 2), 1)
        return s
    if kind == "fireplace":
        base = (150, 116, 82)
        s = pygame.Surface((t, t)); s.fill(base)
        pygame.draw.rect(s, (200, 184, 158), (0, 0, t, int(t * 0.4)))
        stone = (120, 120, 134)
        pygame.draw.rect(s, stone, (2, 4, t - 4, t - 6))
        pygame.draw.rect(s, _dk(stone, 0.3), (2, 4, t - 4, t - 6), width=2)
        pygame.draw.rect(s, (30, 24, 28), (7, 12, t - 14, t - 16))       # firebox
        pygame.draw.rect(s, (96, 66, 42), (8, t - 9, t - 16, 3))         # log
        for fx, fh, col in ((t // 2 - 4, 8, (220, 120, 40)), (t // 2, 11, (240, 180, 60)),
                            (t // 2 + 4, 7, (220, 120, 40))):
            pygame.draw.polygon(s, col, [(fx - 3, t - 9), (fx + 3, t - 9), (fx, t - 9 - fh)])
        pygame.draw.rect(s, (140, 100, 62), (0, 2, t, 4))               # mantel
        return s
    if kind == "door":
        s = _bake("wall", seed)
        door = (88, 60, 38)
        pygame.draw.rect(s, (60, 42, 28), (5, 2, t - 10, 3))            # lintel
        pygame.draw.rect(s, door, (7, 4, t - 14, t - 4))
        pygame.draw.rect(s, (110, 78, 50), (9, 6, t - 18, t - 8))       # inner panel
        pygame.draw.rect(s, _dk(door, 0.4), (7, 4, t - 14, t - 4), width=2)
        pygame.draw.line(s, (60, 42, 28), (t // 2, 6), (t // 2, t - 2), 1)
        pygame.draw.circle(s, C.GOLD, (t - 12, t // 2), 2)             # knob
        return s
    if kind == "exit":
        s = _ifloor_surf(seed)
        pygame.draw.rect(s, (120, 92, 64), (4, 0, t - 8, 7))            # threshold
        mat = (150, 120, 80)
        pygame.draw.rect(s, mat, (7, t - 12, t - 14, 8), border_radius=2)
        pygame.draw.rect(s, _dk(mat, 0.25), (7, t - 12, t - 14, 8), width=1, border_radius=2)
        pygame.draw.polygon(s, C.ACCENT, [(t // 2 - 4, t - 8), (t // 2 + 4, t - 8), (t // 2, t - 3)])
        return s
    if kind == "cfloor":
        return _cfloor_surf(seed)
    if kind == "cwall":
        base = (36, 34, 48)
        s = pygame.Surface((t, t)); s.fill(base)
        pygame.draw.rect(s, _lt(base, 0.24), (0, 0, t, 4))         # bright lit top
        pygame.draw.rect(s, _lt(base, 0.10), (0, 4, t, 3))
        pygame.draw.rect(s, _dk(base, 0.4), (0, t - 5, t, 5))      # dark base
        rr = _rng("cwall", seed)
        for _ in range(3):
            x = rr.randint(3, t - 9); y = rr.randint(8, t - 10)
            w = rr.randint(5, 9); h = rr.randint(4, 6)
            pygame.draw.polygon(s, _lt(base, 0.12), [(x, y + h), (x + w // 2, y), (x + w, y + h)])
            pygame.draw.line(s, _dk(base, 0.35), (x, y + h), (x + w, y + h), 1)
        return s
    if kind == "crystal":
        s = _cfloor_surf(seed)
        glow = pygame.Surface((t, t), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C.ACCENT, 60), (t // 2, t // 2 + 2), int(t * 0.42))
        s.blit(glow, (0, 0))
        cyan, cyan_dk = C.ACCENT, C.ACCENT_DK
        for bx, h, w in ((t * 0.5, t * 0.72, t * 0.18), (t * 0.34, t * 0.5, t * 0.14),
                         (t * 0.66, t * 0.52, t * 0.14)):
            by = t - 4
            pts = [(bx, by - h), (bx + w / 2, by - h * 0.45), (bx + w * 0.3, by),
                   (bx - w * 0.3, by), (bx - w / 2, by - h * 0.45)]
            ipts = [(int(px), int(py)) for px, py in pts]
            pygame.draw.polygon(s, cyan_dk, [(px + 1, py + 1) for px, py in ipts])
            pygame.draw.polygon(s, cyan, ipts)
            pygame.draw.polygon(s, _lt(cyan, 0.4),
                                [(int(bx), int(by - h)), (int(bx + w * 0.18), int(by - h * 0.5)),
                                 (int(bx), int(by - h * 0.2)), (int(bx - w * 0.14), int(by - h * 0.5))])
        return s
    if kind == "stalag":
        s = _cfloor_surf(seed)
        rock = (96, 96, 112)
        by = t - 3
        pts = [(t * 0.46, 4), (t * 0.46 + t * 0.22, by), (t * 0.46 - t * 0.22, by)]
        ipts = [(int(px), int(py)) for px, py in pts]
        pygame.draw.polygon(s, _dk(rock, 0.25), [(px + 1, py) for px, py in ipts])
        pygame.draw.polygon(s, rock, ipts)
        pygame.draw.polygon(s, _lt(rock, 0.18),
                            [(int(t * 0.46), 4), (int(t * 0.46 + t * 0.07), int(t * 0.5)),
                             (int(t * 0.46 - t * 0.03), int(t * 0.5))])
        pts2 = [(t * 0.74, t * 0.52), (t * 0.74 + t * 0.12, by), (t * 0.74 - t * 0.12, by)]
        pygame.draw.polygon(s, rock, [(int(px), int(py)) for px, py in pts2])
        return s
    if kind == "lava":
        top, bot = (160, 58, 22), (96, 32, 14)
        s = pygame.Surface((t, t))
        for y in range(t):
            f = y / t
            s.fill((int(top[0] + (bot[0] - top[0]) * f),
                    int(top[1] + (bot[1] - top[1]) * f),
                    int(top[2] + (bot[2] - top[2]) * f)), (0, y, t, 1))
        rr = _rng("lava", seed)
        for _ in range(3):                                          # cooled crust patches
            pygame.draw.ellipse(s, _dk(bot, 0.28),
                                (rr.randint(0, t - 11), rr.randint(0, t - 9),
                                 rr.randint(7, 12), rr.randint(5, 8)))
        for _ in range(3):                                          # molten cracks
            x1 = rr.randint(2, t - 2); y1 = rr.randint(2, t - 2)
            x2 = x1 + rr.randint(-9, 9); y2 = y1 + rr.randint(-9, 9)
            pygame.draw.line(s, (255, 168, 56), (x1, y1), (x2, y2), 2)
            pygame.draw.line(s, (255, 232, 140), (x1, y1), ((x1 + x2) // 2, (y1 + y2) // 2), 1)
        for _ in range(4):
            s.set_at((rr.randint(0, t - 1), rr.randint(0, t - 1)), (255, 220, 120))
        return s
    if kind == "wetsand":
        base = (166, 144, 98)
        s = pygame.Surface((t, t)); s.fill(base)
        rr = _rng("wetsand", seed)
        for y in (int(t * 0.28), int(t * 0.55), int(t * 0.82)):     # seamless ripples
            pygame.draw.line(s, _dk(base, 0.13), (0, y), (t, y), 1)
            pygame.draw.line(s, _lt(base, 0.09), (0, y + 1), (t, y + 1), 1)
        for _ in range(7):
            s.set_at((rr.randint(0, t - 1), rr.randint(0, t - 1)),
                     _dk(base, 0.16) if rr.random() < 0.6 else _lt(base, 0.12))
        return s
    if kind == "sea":
        top, bot = (66, 158, 182), (40, 116, 150)
        s = pygame.Surface((t, t))
        for y in range(t):
            f = y / t
            s.fill((int(top[0] + (bot[0] - top[0]) * f),
                    int(top[1] + (bot[1] - top[1]) * f),
                    int(top[2] + (bot[2] - top[2]) * f)), (0, y, t, 1))
        rr = _rng("sea", seed)
        for _ in range(2):                                                # foam streaks
            y = rr.randint(3, t - 5)
            pygame.draw.line(s, _lt(top, 0.22), (rr.randint(0, 6), y),
                             (rr.randint(t - 8, t), y + rr.randint(-1, 1)), 1)
        for _ in range(3):
            s.set_at((rr.randint(0, t - 1), rr.randint(0, t - 1)), (212, 240, 246))
        return s
    if kind == "palm":
        s = _bake("sand", seed)
        trunk = (132, 96, 56)
        tx0 = int(t * 0.5)
        pygame.draw.line(s, trunk, (tx0, t - 2), (tx0 - 2, int(t * 0.42)), max(2, int(t * 0.08)))
        pygame.draw.line(s, _lt(trunk, 0.15), (tx0, t - 2), (tx0 - 2, int(t * 0.42)), 1)
        leaf, leaf_d = (60, 150, 80), (40, 110, 56)
        cxp, cyp = tx0 - 2, int(t * 0.4)
        for dx, dy in ((-1, -0.4), (1, -0.4), (-0.8, 0.15), (0.8, 0.15), (0, -1)):
            ex, ey = cxp + dx * t * 0.32, cyp + dy * t * 0.3
            pygame.draw.line(s, leaf_d, (cxp, cyp), (int(ex), int(ey)), 3)
            pygame.draw.line(s, leaf, (cxp, cyp), (int(ex), int(ey)), 2)
        pygame.draw.circle(s, (120, 90, 60), (cxp, cyp), 2)
        return s
    if kind == "beachrock":
        s = _bake("sand", seed)
        rock = (150, 142, 150)
        pygame.draw.ellipse(s, _dk(rock, 0.3), (5, int(t * 0.4), t - 10, int(t * 0.5)))
        pygame.draw.ellipse(s, rock, (5, int(t * 0.36), t - 10, int(t * 0.46)))
        pygame.draw.ellipse(s, _lt(rock, 0.16), (9, int(t * 0.4), int(t * 0.4), int(t * 0.2)))
        return s
    if kind == "shell":
        s = _bake("sand", seed)
        rr = _rng("shell", seed)
        col = (236, 170, 180) if rr.random() < 0.5 else (240, 200, 140)
        cxp, cyp = int(t * 0.5), int(t * 0.54)
        hinge = (cxp, cyp + int(t * 0.12))
        fan = [hinge]
        for dx in (-0.2, -0.1, 0.0, 0.1, 0.2):
            fan.append((int(cxp + dx * t), cyp - int(t * 0.14)))
        pygame.draw.polygon(s, col, fan)
        pygame.draw.polygon(s, _dk(col, 0.25), fan, 1)
        for dx in (-0.12, 0.0, 0.12):
            pygame.draw.line(s, _dk(col, 0.2), hinge, (int(cxp + dx * t), cyp - int(t * 0.12)), 1)
        return s
    if kind == "dock":
        water = (46, 120, 150)
        s = pygame.Surface((t, t)); s.fill(water)
        wood = (150, 110, 68)
        ph = t // 4
        for i, py in enumerate(range(0, t, ph)):
            pygame.draw.rect(s, wood if i % 2 == 0 else _dk(wood, 0.08), (0, py + 1, t, ph - 2))
            pygame.draw.line(s, _lt(wood, 0.15), (0, py + 1), (t, py + 1), 1)
        for py in range(ph // 2, t, ph):
            pygame.draw.circle(s, _dk(wood, 0.4), (3, py), 1)
            pygame.draw.circle(s, _dk(wood, 0.4), (t - 3, py), 1)
        return s
    # fallback
    return _grass_surf(seed)


def _water_frames():
    if "water" in _anim_cache:
        return _anim_cache["water"]
    t = C.TILE
    frames = []
    for f in range(4):
        s = pygame.Surface((t, t))
        for y in range(t):
            fr = y / t
            s.fill(_mx(C.C_WATER, C.C_WATER_2, fr), (0, y, t, 1))
        for row in range(-6, t, 7):
            y = row + (f * 2) % 7
            x0 = (f * 5) % 10
            pygame.draw.line(s, _lt(C.C_WATER, 0.22), (x0, y), (x0 + 11, y), 2)
            pygame.draw.line(s, _lt(C.C_WATER, 0.22), (x0 + 17, y + 3), (x0 + 27, y + 3), 2)
        frames.append(s)
    _anim_cache["water"] = frames
    return frames


def _spring_frames():
    if "spring" in _anim_cache:
        return _anim_cache["spring"]
    t = C.TILE
    base = (26, 64, 78)
    frames = []
    for f in range(4):
        s = pygame.Surface((t, t)); s.fill(base)
        cx, cy = t // 2, t // 2
        for k in range(3):
            rad = (f * 2 + k * 5) % 16 + 2
            a = max(0, 160 - rad * 9)
            ring = pygame.Surface((t, t), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*C.C_SPRING, a), (cx, cy), rad, 2)
            s.blit(ring, (0, 0))
        glow = pygame.Surface((t, t), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*C.C_SPRING, 70), (cx, cy), 6)
        s.blit(glow, (0, 0))
        pygame.draw.circle(s, (235, 252, 255), (cx, cy), 2)
        r = _rng("spring", f)
        for _ in range(3):
            s.set_at((r.randint(2, t - 2), r.randint(2, t - 2)), (210, 245, 250))
        frames.append(s)
    _anim_cache["spring"] = frames
    return frames


def _variant(kind, tx, ty):
    if kind not in _tile_cache:
        _tile_cache[kind] = [_bake(kind, i) for i in range(_VARIANTS)]
    return _tile_cache[kind][(tx * 7 + ty * 13) % _VARIANTS]


def _foam_edge():
    global _FOAM
    if _FOAM is None:
        t = C.TILE
        _FOAM = pygame.Surface((t, 4), pygame.SRCALPHA)
        for x in range(t):
            if (x // 3) % 2 == 0:
                _FOAM.set_at((x, 1), (*_lt(C.C_WATER, 0.5), 200))
                _FOAM.set_at((x, 2), (*_lt(C.C_WATER, 0.35), 150))
    return _FOAM


def _draw_tile(surf, m, sx, sy, tx, ty):
    t = C.TILE
    ch = m.char_at(tx, ty)
    kind = _kind(ch)

    if kind == "water":
        frames = _water_frames()
        surf.blit(frames[(pygame.time.get_ticks() // 220) % len(frames)], (sx, sy))
        # shoreline foam where a neighbour is land
        foam = _foam_edge()
        if _kind(m.char_at(tx, ty - 1)) != "water":
            surf.blit(foam, (sx, sy))
        if _kind(m.char_at(tx, ty + 1)) != "water":
            surf.blit(pygame.transform.flip(foam, False, True), (sx, sy + t - 4))
        if _kind(m.char_at(tx - 1, ty)) != "water":
            surf.blit(pygame.transform.rotate(foam, -90), (sx, sy))
        if _kind(m.char_at(tx + 1, ty)) != "water":
            surf.blit(pygame.transform.rotate(foam, 90), (sx + t - 4, sy))
        return

    if kind == "spring":
        frames = _spring_frames()
        surf.blit(frames[(pygame.time.get_ticks() // 200) % len(frames)], (sx, sy))
        return

    surf.blit(_variant(kind, tx, ty), (sx, sy))

    # subtle dirt rim where a path meets greenery
    if kind == "path":
        rim = _dk(C.C_PATH, 0.16)
        if _kind(m.char_at(tx, ty - 1)) in ("grass", "grass2", "tall", "flower"):
            pygame.draw.line(surf, rim, (sx, sy), (sx + t, sy), 1)
        if _kind(m.char_at(tx, ty + 1)) in ("grass", "grass2", "tall", "flower"):
            pygame.draw.line(surf, rim, (sx, sy + t - 1), (sx + t, sy + t - 1), 1)
        if _kind(m.char_at(tx - 1, ty)) in ("grass", "grass2", "tall", "flower"):
            pygame.draw.line(surf, rim, (sx, sy), (sx, sy + t), 1)
        if _kind(m.char_at(tx + 1, ty)) in ("grass", "grass2", "tall", "flower"):
            pygame.draw.line(surf, rim, (sx + t - 1, sy), (sx + t - 1, sy + t), 1)


def get_map(map_id):
    return Map(map_id)


ALL_MAP_IDS = list(MAP_DEFS.keys())
