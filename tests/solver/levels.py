"""The original LAMA levels (legacy/level/test*.txt) converted by hand to XSB: ``X`` -> ``#``, ``*`` -> ``$``.

``test1``-``test11`` are solvable; ``test12``-``test14`` were made unsolvable on purpose by the group.
``BIG`` is not from the group: an open 14x14 room with 9 boxes, too large for a quick search, used to check
that the limits hold.
"""

from alexvolkihar_sokoban.core.level import Level

ROWS: dict[str, list[str]] = {
    "test1": [
        "######",
        "#.  .#",
        "#    #",
        "# $$ #",
        "#@   #",
        "######",
    ],
    "test2": [
        "######",
        "#.  .#",
        "#    #",
        "#$  $#",
        "#@   #",
        "######",
    ],
    "test3": [
        " ######",
        "#.$@  #",
        "###   #",
        "#.##  #",
        "# #   ##",
        "#$ #$  #",
        "#   .  #",
        "########",
    ],
    "test4": [
        "##########",
        "#    @   #",
        "#  $  .  #",
        "#        #",
        "##########",
    ],
    "test5": [
        "#########",
        "#       #",
        "#. $    #",
        "#      @#",
        "#########",
    ],
    "test6": [
        "#######",
        "# .   #",
        "# # # #",
        "# # # #",
        "# $@  #",
        "#     #",
        "#######",
    ],
    "test7": [
        "########",
        "#  . . #",
        "#    # #",
        "## # # #",
        " #  $  #",
        " #  $@ #",
        " #     #",
        " #######",
    ],
    "test8": [
        "  ######",
        "  # ..@#",
        "  # $$ #",
        "  ## ###",
        "   # #",
        "   # #",
        "#### #",
        "#    ##",
        "# #   #",
        "#   # #",
        "###   #",
        "  #####",
    ],
    "test9": [
        "####",
        "#  ####",
        "# . . #",
        "# $$#@#",
        "##    #",
        " ######",
    ],
    "test10": [
        "######",
        "#@   ##",
        "# $$  #",
        "# #. .#",
        "#     #",
        "#######",
    ],
    "test11": [
        "  ####",
        "###  #",
        "#@ .$##",
        "#   $ #",
        "# #.  #",
        "#     #",
        "#######",
    ],
    "test12": [
        "####",
        "# .#",
        "#  ###",
        "##@  #",
        "#  $ #",
        "#  ###",
        "####",
    ],
    "test13": [
        "#####",
        "#@  ##",
        "#.$# #",
        "#  # #",
        "#    #",
        "######",
    ],
    "test14": [
        "########",
        "#      #",
        "# .##$@#",
        "#      #",
        "#####  #",
        "   ####",
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
SOLVABLE = [f"test{i}" for i in range(1, 12)]
UNSOLVABLE = ["test12", "test13", "test14"]
