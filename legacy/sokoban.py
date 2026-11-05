import pygame, os, sys

class Cell(object):
    FICHIER = ""
    CELL_TYPE = ""
     #initialisation des variables des cellules :
    def __init__(self, x, y, fichier = FICHIER, cell_type = CELL_TYPE):
        self.x = x
        self.y = y
        PATH_IMG = os.path.join("img", fichier)
        self.image = pygame.image.load(PATH_IMG)
        self.cell_type = cell_type
    #definition de la méthode visant a afficher les cellules dans la fenetre pygame :
    def paint(self, screen):
        self.image = pygame.transform.scale(self.image, (Grid.SIZE, Grid.SIZE))
        screen.blit(self.image, (self.x+25, self.y+25))
    #définition de la méthode permettant de récupérer les Types de chaque cellule (essentielle pour les test de déplacement) :
    def get_type(self):
        return self.cell_type



#Definition de chaque cellule heritant de la classe "Cell" :
class Wall(Cell):
    FICHIER = "WallRound_Brown.png"
    CELL_TYPE = "wall"

    def __init__(self, x, y):
        Cell.__init__(self, x, y, Wall.FICHIER, Wall.CELL_TYPE)

class Ground(Cell):
    FICHIER = "empty.png"
    CELL_TYPE = "ground"

    def __init__(self, x, y):
        Cell.__init__(self, x, y, Ground.FICHIER, Ground.CELL_TYPE)

class EndPoint(Cell):
    FICHIER = "EndPoint_Brown.png"
    CELL_TYPE = "end_point"

    def __init__(self, x, y):
        Cell.__init__(self, x, y, EndPoint.FICHIER, EndPoint.CELL_TYPE)

class Crate(Cell):
    FICHIER = "Crate_Brown.png"
    CELL_TYPE = "crate"

    def __init__(self, x, y):
        Cell.__init__(self, x, y, Crate.FICHIER, Crate.CELL_TYPE)

class Character(Cell):
    FICHIER = "Character4.png"
    CELL_TYPE = "character"

    def __init__(self, x, y):
        Cell.__init__(self, x, y, Character.FICHIER, Character.CELL_TYPE)



#classe responsable de l'importation, de l'affichage et de la modification de la grille de jeu :
class Grid(object):
    SIZE = 48

    def __init__(self):
        self.cells = {}
        self.allEndPoint = []
        self.level = sys.argv[2] # Récupère l'argument pour lancer le niveau

        self.nbrDeplacement = 0

        # Ouvre le niveau et le transforme en grille :
        file = open(self.level, 'r')
        x = True
        i = 0
        self.grid = [[]]
        while x:
            char = file.read(1)
            if not char:
                x = False
            elif char != '\n':
                self.grid[i].append(char)
            else:
                self.grid.append([])
                i += 1

        #Transforme la grille en dictionnaire :
        for i in range(len(self.grid)):
            for j in range(len(self.grid[i])):
                if self.grid[i][j] == 'X':
                    self.cells[(i, j)] = Wall(i * Grid.SIZE, j * Grid.SIZE)
                elif self.grid[i][j] == ' ':
                    self.cells[(i, j)] = Ground(i * Grid.SIZE, j * Grid.SIZE)
                elif self.grid[i][j] == '*':
                    self.cells[(i, j)] = Crate(i * Grid.SIZE, j * Grid.SIZE)
                elif self.grid[i][j] == '.':
                    self.cells[(i, j)] = EndPoint(i * Grid.SIZE, j * Grid.SIZE)
                    self.allEndPoint.append((i, j))
                elif self.grid[i][j] == '@':
                    self.cells[(i, j)] = Character(i * Grid.SIZE, j * Grid.SIZE)
                    self.xPlayer = i
                    self.yPlayer = j

    # Remplace le personnage par du vide dans cells :
    def clearPlayer(self):
        self.cells[(self.xPlayer, self.yPlayer)] = Ground(self.xPlayer * Grid.SIZE, self.yPlayer * Grid.SIZE)
    # Remplace le personnage par un end point dans cells :
    def clearPlayerOnEndPoint(self):
        self.cells[(self.xPlayer, self.yPlayer)] = EndPoint(self.xPlayer * Grid.SIZE, self.yPlayer * Grid.SIZE)
    # La méthode setPlayer déplace le personnage dans le dictionnaire cells :
    def setPlayer(self):
        self.cells[(self.xPlayer, self.yPlayer)] = Character(self.xPlayer * Grid.SIZE, self.yPlayer * Grid.SIZE)
    # la méthode getType récupère le type de la cellule en (i, j) grace à la méthode du même nom dans la classe Cell() :
    def getType(self, i, j):
        return self.cells[(i, j)].get_type()
    # La méthode crateMouve déplace les cellules de type crate :
    def crateMoove(self, x, y):
        self.cells[(x,y)] = Crate(x * Grid.SIZE, y * Grid.SIZE)
    # La méthode playerOnEndPoint vérifie si un joueur est sur un EndPoint :
    def playerOnEndPoint(self, x, y):
        if (x, y) in self.allEndPoint:
            return True
        else:
            return False


    # Les méthodes up, down, left, right sont des méthodes qui testent la validité des déplacement et , qui si possible, les effectuent :
    def up(self):
        if self.getType(self.xPlayer, self.yPlayer - 1) == Wall.CELL_TYPE:
            return
        elif self.getType(self.xPlayer, self.yPlayer - 1) == Crate.CELL_TYPE:
            if self.getType(self.xPlayer, self.yPlayer - 2) == Ground.CELL_TYPE or self.getType(self.xPlayer, self.yPlayer - 2) == EndPoint.CELL_TYPE:
                self.crateMoove(self.xPlayer, self.yPlayer -2)
            else:
                return
        if self.playerOnEndPoint(self.xPlayer, self.yPlayer):
            self.clearPlayerOnEndPoint()
        else:
            self.clearPlayer()
        self.yPlayer -= 1
        self.setPlayer()
        self.nbrDeplacement += 1

    def down(self):
        if self.getType(self.xPlayer, self.yPlayer + 1) == Wall.CELL_TYPE:
            return
        elif self.getType(self.xPlayer, self.yPlayer + 1) == Crate.CELL_TYPE:
            if self.getType(self.xPlayer, self.yPlayer + 2) == Ground.CELL_TYPE or self.getType(self.xPlayer, self.yPlayer + 2) == EndPoint.CELL_TYPE:
                self.crateMoove(self.xPlayer, self.yPlayer + 2)
            else:
                return
        if self.playerOnEndPoint(self.xPlayer, self.yPlayer):
            self.clearPlayerOnEndPoint()
        else:
            self.clearPlayer()
        self.yPlayer += 1
        self.setPlayer()
        self.nbrDeplacement += 1

    def right(self):
        if self.getType(self.xPlayer + 1, self.yPlayer) == Wall.CELL_TYPE:
            return
        elif self.getType(self.xPlayer+1, self.yPlayer) == Crate.CELL_TYPE:
            if self.getType(self.xPlayer + 2, self.yPlayer) == Ground.CELL_TYPE or self.getType(self.xPlayer + 2, self.yPlayer) == EndPoint.CELL_TYPE:
                self.crateMoove(self.xPlayer + 2, self.yPlayer)
            else:
                return
        if self.playerOnEndPoint(self.xPlayer, self.yPlayer):
            self.clearPlayerOnEndPoint()
        else:
            self.clearPlayer()
        self.xPlayer += 1
        self.setPlayer()
        self.nbrDeplacement += 1

    def left(self):
        if self.getType(self.xPlayer - 1, self.yPlayer) == Wall.CELL_TYPE:
            return
        elif self.getType(self.xPlayer - 1, self.yPlayer) == Crate.CELL_TYPE:
            if self.getType(self.xPlayer - 2, self.yPlayer) == Ground.CELL_TYPE or self.getType(self.xPlayer - 2, self.yPlayer) == EndPoint.CELL_TYPE:
                self.crateMoove(self.xPlayer - 2, self.yPlayer)
            else:
                return
        if self.playerOnEndPoint(self.xPlayer, self.yPlayer):
            self.clearPlayerOnEndPoint()
        else:
            self.clearPlayer()
        self.xPlayer -= 1
        self.setPlayer()
        self.nbrDeplacement += 1

        # la méthode endGame vérifie si tout les points sont occupés par des caisses. Si c'est le cas elle renvoie "True" et met fin au jeu dans PygView().run()
    def endGame(self):
        for i in range (len(self.allEndPoint)):
            if self.getType(self.allEndPoint[i][0], self.allEndPoint[i][1]) == Crate.CELL_TYPE:
                pass
            else:
                return
        return True
    # la méthode paint dessine le niveau dans la fenêtre grâce à son appel dans la classe PygView :
    def paint(self, screen):
        for cell in self.cells.values():
            cell.paint(screen)

    # récupère la longueur niveau pour dimensionner la fenêtre :
    def widhtGrid(self):
        return len(self.grid)
    # récupère la largeur de la plus grande ligne du niveau pour dimensionner la fenêtre :
    def heightGrid(self):
        x = 0
        for i in range (len(self.grid)):
            if len(self.grid[i]) > x:
                x = len(self.grid[i])
        return x




# Classe permettant l'affichage de la fenetre pygame et son actualisation en fonction des déplacements :
class PygView(object):
    WIDTH = Grid().widhtGrid() * Grid().SIZE + 50
    HEIGHT = Grid().heightGrid() * Grid().SIZE + 50
    ICON = "img/icon.png"

    def __init__(self):
        pygame.init()
        pygame.display.set_caption('SOKOBAN LAMA')

        self.width = PygView.WIDTH
        self.height = PygView.HEIGHT
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.DOUBLEBUF)

        self.icon = pygame.image.load(self.ICON)
        pygame.display.set_icon(self.icon)

        self.background = pygame.Surface(self.screen.get_size()).convert()
        self.background.fill((255, 255, 255))

        self.grid = Grid()

    # les méthodes up, down, left, right appellent les formules du même nom dans la classe Grid(). Elle redessine ensuite la position de chaque élément dans la fenêtre :
    def up(self):
        self.grid.up()
        self.grid.paint(self.screen)
    def down(self):
        self.grid.down()
        self.grid.paint(self.screen)
    def left(self):
        self.grid.left()
        self.grid.paint(self.screen)
    def right(self):
        self.grid.right()
        self.grid.paint(self.screen)

    # La méthode gère la restitution du chemin calculé par l'A*
    def doAstarPath(self, path, time):
        clock = pygame.time.Clock()
        running = True
        while running:
            clock.tick(5)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            if self.grid.endGame() == True:
                print("\nL'A* a résolu le niveau en", self.grid.nbrDeplacement, 'déplacements et en', time, 'secondes.')
                running = False
            if len(path) > 0:
                if path[0] == 'u' or path[0] == 'U':
                    self.left()
                elif path[0] == 'd' or path[0] == 'D':
                    self.right()
                elif path[0] == 'l' or path[0] == 'L':
                    self.up()
                elif path[0] == 'r' or path[0] == 'R':
                    self.down()
                path.remove(path[0])
            pygame.display.flip()
            self.grid.paint(self.screen)

    # la méthode run gère les évenements a l'intérieur de la fenêtre ainsi que la fermeture de cette dernière :
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_UP:
                        self.up()
                    elif event.key == pygame.K_DOWN:
                        self.down()
                    elif event.key == pygame.K_LEFT:
                        self.left()
                    elif event.key == pygame.K_RIGHT:
                        self.right()
                if self.grid.endGame() == True:
                    print ('\nBravo !')
                    print ('Le niveau a été résolu en', self.grid.nbrDeplacement, 'déplacements.')
                    running = False

            pygame.display.flip()
            self.grid.paint(self.screen)
