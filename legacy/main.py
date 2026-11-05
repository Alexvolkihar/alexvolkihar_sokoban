from sokoban import *
from aStar import *
import sys, time

if __name__ == '__main__':
    # vérification du nombre d'arguments saisis par l'utilisateur
    if len(sys.argv) != 3:
        sys.stderr.write("\nTo many arguments\n")
        sys.exit(1)

    levelPath = sys.argv[2]
    # vérification de si l'utilisateur veut jouer ou résoudre le niveau
    if sys.argv[1] == 'play':
        PygView().run()
    elif sys.argv[1] == 'solve':
        startTime = time.time()

        level = Initialisation(levelPath).returnInitGrid()
        posWalls = Initialisation(levelPath).allWallPos()
        posGoals = Initialisation(levelPath).allEndPointPos()

        path = AStar(level, posWalls, posGoals).aStarSearch()

        endTime = time.time()
        totalTime = round(endTime-startTime, 3)
        # verifie si le niveau est valide
        if path == None:
            sys.stderr.write("\nLe niveau est invalide et ne peut pas être résolu\n")
        else:
            PygView().doAstarPath(path, totalTime)
    else:
        sys.stderr.write("\nWrong command ! please use solve or play\n")
