"""Small levels made for these tests, also bundled in the game.

The solvable ones are the levels of the First steps pack (``data/levels/first-steps.json``); the
unsolvable ones (no box starts on a dead square, the search has to prove it) are in the hidden
``bench-extra`` pack. ``BIG`` is an open 14x14 room with 9 boxes, too large for a quick search, used to
check that the limits hold.
"""

from alexvolkihar_sokoban.core.level import Level

ROWS: dict[str, list[str]] = {
    "first-push": [
        "########",
        "#   #  #",
        "# $   .#",
        "#@ ##  #",
        "########",
    ],
    "room": [
        "#######",
        "#.   .#",
        "#  $  #",
        "# $   #",
        "#@    #",
        "#######",
    ],
    "twins": [
        "  #####",
        "###   #",
        "#. $# #",
        "# $@  #",
        "#.  ###",
        "#####",
    ],
    "spiral": [
        "##########",
        "#        #",
        "# ###### #",
        "# #.  $  #",
        "# # $$ # #",
        "# #. .   #",
        "# ########",
        "#@ #",
        "####",
    ],
    "crossroads": [
        "  #####",
        "  #   #",
        "###$# ###",
        "#  . .  #",
        "# $ @ $ #",
        "#  . .  #",
        "### #$###",
        "  #   #",
        "  #####",
    ],
    "hallway": [
        "#########",
        "#@  #   #",
        "# $   $ #",
        "#   #   #",
        "## ### ##",
        "#.     .#",
        "#########",
    ],
    "loop": [
        "#########",
        "#   .   #",
        "# # # # #",
        "# $ @ $ #",
        "# # # # #",
        "#   .   #",
        "#########",
    ],
    "three-way": [
        "  ####",
        "###  ####",
        "#  $ $  #",
        "# #.@.# #",
        "#   $   #",
        "###.  ###",
        "  #####",
    ],
    "pillars": [
        "#########",
        "#   #   #",
        "# $   $ #",
        "#  #.#  #",
        "#   .   #",
        "## #@# ##",
        " #     #",
        " #######",
    ],
    "courtyard": [
        " ########",
        " #  #   #",
        "## $  $ #",
        "#  ##.# #",
        "# $ ... #",
        "#  ## $ ##",
        "## @     #",
        " #########",
    ],
    "warehouse": [
        "##########",
        "#    #   #",
        "# $  # $ #",
        "#  #   # #",
        "## #.#.  #",
        "#   ..   #",
        "# $  $ #@#",
        "#      # #",
        "##########",
    ],
    "finale": [
        " #########",
        " #   #   #",
        "## $ . $ ##",
        "#  ## ##  #",
        "# . $@$ . #",
        "#  ## ##  #",
        "##   .   ##",
        " #########",
    ],
    "sealed": [
        "#######",
        "#@  #.#",
        "# $ $.#",
        "#   # #",
        "#######",
    ],
    "divide": [
        "#########",
        "#.  #   #",
        "# $ # . #",
        "# $   ###",
        "# @ ###",
        "#####",
    ],
    "bend": [
        "######",
        "#@   ###",
        "# $$   #",
        "##  #. #",
        " #  . ##",
        " ######",
    ],
}

BIG_ROWS: list[str] = [
    "################",
    "#@             #",
    "#  $   $   $   #",
    "#    #    #    #",
    "#  $   $   $   #",
    "#              #",
    "#   #  ##  #   #",
    "#  $   $   $   #",
    "#              #",
    "#  ##      ##  #",
    "#      ..      #",
    "#     ...      #",
    "#     ....     #",
    "#              #",
    "################",
]


LEVELS: dict[str, Level] = {name: Level.from_rows(rows, title=name) for name, rows in ROWS.items()}
BIG = Level.from_rows(BIG_ROWS, title="big")
SOLVABLE = [
    "first-push",
    "room",
    "twins",
    "spiral",
    "crossroads",
    "hallway",
    "loop",
    "three-way",
    "pillars",
    "courtyard",
    "warehouse",
    "finale",
]
UNSOLVABLE = ["sealed", "divide", "bend"]
