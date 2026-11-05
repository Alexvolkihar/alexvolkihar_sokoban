Jeu Sokoban crée par le groupe LAMA: Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN et Martin PACARY

Le projet inclut aussi un solveur automatique base sur l'algorithme A* (aStar.py), capable de
trouver une solution optimale pour un niveau donne.

Langage utilise: Python
Version: 3.9.0 64-bits

Bibliotheque necessaire: Pygame
Version: 2.0


Installation:
- Pygame ne fournit pas toujours de wheel precompile pour les versions tres recentes de Python
  (ex: 3.14). Si `pip install pygame` echoue a charger les images (erreur "File is not a Windows
  BMP file"), utiliser une version de Python pour laquelle un wheel existe (ex: 3.10):
        python3.10 -m pip install pygame

Notice d'utilisation:
- Lancer une console de commande dans le dossier du jeu
- Utiliser une des deux commandes suivantes afin de:
    Resoudre le niveau:
        python main.py solve level/testX.txt

    Jouer le niveau:
        python main.py play level/testX.txt

    Ou X est un nombre entre 1 et 14.
        Les niveaux 12, 13 et 14 n'ont pas de fin. L'algorithme A doit le remarquer tout seul.
        testX est le nom utilise pour nos niveaux de jeu, cependant n'importe quel fichier .txt
        comportant un niveau exploitable par le programme peut etre joue.
        ATTENTION: Le solveur peut parfois ne pas trouver la solution d'un niveau et se bloquer dans
        une boucle infinie, ce qui a pour effet de surcharger la RAM, utiliser les fichiers avec
        precaution.

Controles de jeu:
Fleches directionnelles: Deplacements du personnage

Format des niveaux:
Un niveau est un fichier texte ou chaque caractere represente une case de la grille:
    X          Mur
    (espace)   Sol vide
    *          Caisse
    .          Point d'arrivee
    @          Personnage

Exemple (level/test1.txt):
    XXXXXX
    X.  .X
    X    X
    X ** X
    X@   X
    XXXXXX

Le but est de pousser chaque caisse (*) sur un point d'arrivee (.) en deplacant le personnage (@),
sans pouvoir tirer les caisses.

Structure du projet:
    main.py            Point d'entree (modes play / solve)
    sokoban.py         Affichage Pygame et logique de jeu / deplacements
    aStar.py           Modelisation du niveau et solveur A*
    PriorityQueue.py   File de priorite utilisee par l'algorithme A*
    level/             Niveaux de jeu (.txt)
    img/               Sprites du jeu
