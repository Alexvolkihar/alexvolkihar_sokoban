# Sokoban-LAMA

Jeu Sokoban créé par le groupe LAMA : Antoine LAROCHE, Alexis MABANZA, Logan VIVIEN et Martin PACARY.

Le projet inclut aussi un solveur automatique basé sur l'algorithme A* (`aStar.py`), capable de trouver
une solution optimale pour un niveau donné.

## Prérequis

- Python 3.9+
- Pygame 2.0+

## Installation

```bash
pip install pygame
```

> **Note :** Pygame ne fournit pas toujours de wheel précompilé pour les versions très récentes de
> Python (ex: 3.14). Si `pip install pygame` échoue à charger les images au lancement
> (erreur `pygame.error: File is not a Windows BMP file`), c'est que pip a compilé pygame depuis les
> sources sans le support SDL_image. Utiliser une version de Python pour laquelle un wheel précompilé
> existe (ex: 3.10) résout le problème :
>
> ```bash
> python3.10 -m pip install pygame
> python3.10 main.py play level/test1.txt
> ```

## Utilisation

Depuis le dossier du jeu :

```bash
# Jouer un niveau
python main.py play level/testX.txt

# Faire résoudre un niveau par l'algorithme A*
python main.py solve level/testX.txt
```

Où `testX` est l'un des niveaux fournis dans `level/` (`test1` à `test14`, `lvlultime`, `wiki`, ...),
ou plus généralement le chemin vers n'importe quel fichier `.txt` décrivant un niveau valide
(voir [Format des niveaux](#format-des-niveaux)).

- Les niveaux `test12`, `test13` et `test14` n'ont pas de solution : l'algorithme A* doit le
  détecter tout seul et le signaler.
- **Attention :** le solveur peut parfois ne pas trouver la solution d'un niveau et se bloquer dans
  une boucle infinie, ce qui peut surcharger la RAM. Utiliser les fichiers avec précaution.

## Contrôles

| Touche | Action |
|---|---|
| Flèches directionnelles | Déplacer le personnage |

## Format des niveaux

Un niveau est un fichier texte où chaque caractère représente une case de la grille :

| Symbole | Élément |
|---|---|
| `X` | Mur |
| ` ` (espace) | Sol vide |
| `*` | Caisse |
| `.` | Point d'arrivée |
| `@` | Personnage |

Exemple (`level/test1.txt`) :

```
XXXXXX
X.  .X
X    X
X ** X
X@   X
XXXXXX
```

Le but est de pousser chaque caisse (`*`) sur un point d'arrivée (`.`) en déplaçant le personnage
(`@`), sans pouvoir tirer les caisses.

## Structure du projet

```
main.py           Point d'entrée (modes play / solve)
sokoban.py         Affichage Pygame et logique de jeu / déplacements
aStar.py            Modélisation du niveau et solveur A*
PriorityQueue.py    File de priorité utilisée par l'algorithme A*
level/              Niveaux de jeu (.txt)
img/                Sprites du jeu
```
