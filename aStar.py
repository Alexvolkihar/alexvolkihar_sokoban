from PriorityQueue import *

# La classe Initialisation traduit le fichier du niveau en grille et crée la liste des positions des éléments qui ne bougent pas au cours du jeu (EndPoint et Wall):
class Initialisation(object):

    def __init__(self, levelfile):
        self.levelfile = levelfile
        self.level = self.fileToLevel()

    # Traduit le fichier du niveau en grille
    def fileToLevel(self):
        file = open(self.levelfile, 'r')
        x = True
        i = 0
        grid = [[]]
        while x:
            char = file.read(1)
            if not char:
                x = False
            elif char != '\n':
                grid[i].append(char)
            else:
                grid.append([])
                i += 1
        return grid

    # Création de la liste des positions des EndPoints
    def allEndPointPos(self):
        allEndPoint = []
        for i in range(len(self.level)):
            for j in range(len(self.level[i])):
                if self.level[i][j] == '.':
                    allEndPoint.append((i, j))
        return tuple(allEndPoint)

    # Création de la liste des positions des Walls
    def allWallPos(self):
        allWall = []
        for i in range(len(self.level)):
            for j in range(len(self.level[i])):
                if self.level[i][j] == 'X':
                    allWall.append((i, j))
        return tuple(allWall)

    # Renvoie la grille de niveau
    def returnInitGrid(self):
        return self.level

# La classe SearchInLevel cherche la position des éléments qui peuvent bouger et vérifie si le niveau est terminé :
class SearchInLevel(object):
    def __init__(self, levelGrid):
        self.levelGrid = levelGrid

    # Cherche et renvoie la position du joueur dans le niveau
    def playerPos(self):
        for i in range(len(self.levelGrid)):
            for j in range(len(self.levelGrid[i])):
                if self.levelGrid[i][j] == '@':
                    return (i, j)

    # Cherche et renvoie la position des Crates
    def allCratesPosition(self):
        allCrate = []
        for i in range(len(self.levelGrid)):
            for j in range(len(self.levelGrid[i])):
                if self.levelGrid[i][j] == '*':
                    allCrate.append((i, j))
        return tuple(allCrate)

    # Vérifie et renvoie si le niveau est terminé
    def completeLevel(self, cratePos, endPointPos):
        return set(endPointPos) == set(cratePos)

# la classe action se compose de méthodes qui testent les différents mouvements, vérifient s'ils sont faisables et retournent les nouvelles positions des éléments dans le niveau après qu'elles aient été faites :
class Action(object):
    def __init__(self, level, wallPos):
        self.level = level
        self.wallPos = wallPos

    def isLegalAction(self, action, playerPos, cratePos):
        xPlayer, yPlayer = playerPos
        if action[-1].isupper():
            x1, y1 = xPlayer + 2 * action[0], yPlayer + 2 * action[1]
        else:
            x1, y1 = xPlayer + action[0], yPlayer + action[1]
        return (x1, y1) not in cratePos + self.wallPos

    def legalActions(self, playerPos, cratesPos):
        xPlayer, yPlayer = playerPos
        allActions = [[-1, 0, 'u', 'U'], [1, 0, 'd', 'D'], [0, -1, 'l', 'L'], [0, 1, 'r', 'R']]
        legalActions = []
        for action in allActions:
            x1, y1 = xPlayer + action[0], yPlayer + action[1]
            if (x1, y1) in cratesPos:
                action.pop(2)
            else:
                action.pop(3)
            if self.isLegalAction(action, playerPos, cratesPos):
                legalActions.append(action)
            else:
                continue
        return tuple(legalActions)

    def updateState(self, playerPos, cratePos, action):
        xPlayer, yPlayer = playerPos
        newPosPlayer = [xPlayer + action[0], yPlayer + action[1]]
        cratePos = [list(x) for x in cratePos]
        if action[-1].isupper():
            cratePos.remove(newPosPlayer)
            cratePos.append([xPlayer + 2 * action[0], yPlayer + 2 * action[1]])
        cratePos = tuple(tuple(x) for x in cratePos)
        newPosPlayer = tuple(newPosPlayer)
        return newPosPlayer, cratePos

# La classe Astar reconstitue
class AStar(object):
    def __init__(self, level, wallPos, endPointPos):
        self.level = level
        self.wallPos = wallPos
        self.endPointPos = endPointPos
        self.cratePos = SearchInLevel(self.level).allCratesPosition()
        self.playerPos = SearchInLevel(self.level).playerPos()
        self.action = Action(self.level, self.wallPos)
        self.search = SearchInLevel(self.level)

    # Cette fonction vérifie à l'aide de pattern si les positions vont bloquer la resolution du niveau (Merci à KnightofLuna sur GitHub).
    def isFailed(self, posBox):
        rotatePattern = [[0, 1, 2, 3, 4, 5, 6, 7, 8],
                         [2, 5, 8, 1, 4, 7, 0, 3, 6],
                         [0, 1, 2, 3, 4, 5, 6, 7, 8][::-1],
                         [2, 5, 8, 1, 4, 7, 0, 3, 6][::-1]]
        flipPattern = [[2, 1, 0, 5, 4, 3, 8, 7, 6],
                       [0, 3, 6, 1, 4, 7, 2, 5, 8],
                       [2, 1, 0, 5, 4, 3, 8, 7, 6][::-1],
                       [0, 3, 6, 1, 4, 7, 2, 5, 8][::-1]]
        allPattern = rotatePattern + flipPattern

        for box in posBox:
            if box not in self.endPointPos:
                board = [(box[0] - 1, box[1] - 1), (box[0] - 1, box[1]), (box[0] - 1, box[1] + 1), (box[0], box[1] - 1), (box[0], box[1]), (box[0], box[1] + 1), (box[0] + 1, box[1] - 1), (box[0] + 1, box[1]), (box[0] + 1, box[1] + 1)]
                for pattern in allPattern:
                    newBoard = [board[i] for i in pattern]
                    if newBoard[1] in self.wallPos and newBoard[5] in self.wallPos:
                        return True
                    elif newBoard[1] in posBox and newBoard[2] in self.wallPos and newBoard[5] in self.wallPos:
                        return True
                    elif newBoard[1] in posBox and newBoard[2] in self.wallPos and newBoard[5] in posBox:
                        return True
                    elif newBoard[1] in posBox and newBoard[2] in posBox and newBoard[5] in posBox:
                        return True
                    elif newBoard[1] in posBox and newBoard[6] in posBox and newBoard[2] in self.wallPos and newBoard[3] in self.wallPos and newBoard[8] in self.wallPos:
                        return True
        return False

    # cette fonction calcule l'heuristique d'une action
    def heuristic(self, posPlayer, posBox):
        distance = 0
        completes = set(self.endPointPos) & set(posBox)
        sortposBox = list(set(posBox).difference(completes))
        sortposGoals = list(set(self.endPointPos).difference(completes))
        for i in range(len(sortposBox)):
            distance += (abs(sortposBox[i][0] - sortposGoals[i][0])) + (abs(sortposBox[i][1] - sortposGoals[i][1]))
        return distance

    # cette fonction calcule le coût d'une action
    def cost(self, action):
        return len([x for x in action if x.islower()])

    # cette fonction est la boucle infinie qui permet de calculer le chemin à effectuer pour finir le niveau
    def aStarSearch(self):
        beginBox = self.cratePos
        beginPlayer = self.playerPos

        start_state = (beginPlayer, beginBox)
        openList = PriorityQueue()
        openList.push([start_state], self.heuristic(beginPlayer, beginBox))
        closedList = set()
        actions = PriorityQueue()
        actions.push([0], self.heuristic(beginPlayer, start_state[1]))
        while openList.isEmpty() == False:
            node = openList.pop()
            node_action = actions.pop()
            if self.search.completeLevel(node[-1][-1], self.endPointPos):
                node_action.remove(node_action[0])
                return node_action
            if node[-1] not in closedList:
                closedList.add(node[-1])
                cost = self.cost(node_action[1:])
                for action in self.action.legalActions(node[-1][0], node[-1][1]):
                    newPosPlayer, newPosBox = self.action.updateState(node[-1][0], node[-1][1], action)
                    if self.isFailed(newPosBox):
                        continue
                    heuristic = self.heuristic(newPosPlayer, newPosBox)
                    openList.push(node + [(newPosPlayer, newPosBox)], heuristic + cost)
                    actions.push(node_action + [action[-1]], heuristic + cost)