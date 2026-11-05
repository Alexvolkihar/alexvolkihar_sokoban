from collections.abc import Iterator

import pygame
import pytest

from alexvolkihar_sokoban.core.geometry import Direction
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.ui.board_renderer import BoardLayout, BoardRenderer, tile_kind_at
from alexvolkihar_sokoban.ui.themes.base import TileKind
from alexvolkihar_sokoban.ui.themes.fallback import FallbackTheme

LEVEL = Level.from_rows(
    [
        "#######",
        "#.@$  #",
        "#  * ##",
        "#$  # #",  # (3, 5) is a floor pocket the player cannot reach
        "#.  ###",
        "######",  # (5, 6) is blank, outside the walls
    ]
)


@pytest.fixture(autouse=True)
def _pygame() -> Iterator[None]:
    pygame.init()
    yield


def big_level(n: int) -> Level:
    rows = ["#" * n] + ["#" + " " * (n - 2) + "#" for _ in range(n - 2)] + ["#" * n]
    rows[1] = "#@$." + " " * (n - 5) + "#"
    return Level.from_rows(rows)


def test_tile_kind_at() -> None:
    boxes = LEVEL.boxes
    assert tile_kind_at(LEVEL, (2, 3), LEVEL.player, boxes) is TileKind.BOX_ON_GOAL
    assert tile_kind_at(LEVEL, (1, 3), LEVEL.player, boxes) is TileKind.BOX
    assert tile_kind_at(LEVEL, (1, 1), LEVEL.player, boxes) is TileKind.GOAL
    assert tile_kind_at(LEVEL, (1, 2), LEVEL.player, boxes) is TileKind.PLAYER
    assert tile_kind_at(LEVEL, (1, 1), (1, 1), boxes) is TileKind.PLAYER_ON_GOAL
    assert tile_kind_at(LEVEL, (1, 4), LEVEL.player, boxes) is TileKind.FLOOR
    assert tile_kind_at(LEVEL, (1, 4), LEVEL.player, boxes | {(1, 4)}) is TileKind.BOX  # state, not level
    assert tile_kind_at(LEVEL, (0, 2), LEVEL.player, boxes) is TileKind.WALL
    assert tile_kind_at(LEVEL, (5, 6), LEVEL.player, boxes) is TileKind.OUTSIDE
    assert tile_kind_at(LEVEL, (3, 5), LEVEL.player, boxes) is TileKind.OUTSIDE
    assert tile_kind_at(LEVEL, (50, 50), LEVEL.player, boxes) is TileKind.OUTSIDE


def test_cell_rect_uses_row_col() -> None:
    layout = BoardLayout(tile=10, origin=(5, 7))
    # (row, col): row moves down (y), col moves right (x) — the original game drew it transposed.
    assert layout.cell_rect((2, 3)) == pygame.Rect(5 + 30, 7 + 20, 10, 10)


def test_layout_fits_and_centres() -> None:
    renderer = BoardRenderer(FallbackTheme())
    area = pygame.Rect(10, 20, 200, 100)
    layout = renderer.layout(LEVEL, area)  # 7 wide, 6 high
    assert layout.tile == 100 // 6
    board = pygame.Rect(layout.origin, (layout.tile * LEVEL.width, layout.tile * LEVEL.height))
    assert area.contains(board)
    assert abs((board.left - area.left) - (area.right - board.right)) <= 1
    assert abs((board.top - area.top) - (area.bottom - board.bottom)) <= 1


def test_layout_caps_tile_size() -> None:
    layout = BoardRenderer(FallbackTheme()).layout(LEVEL, pygame.Rect(0, 0, 5000, 5000))
    assert layout.tile == BoardRenderer.MAX_TILE


def test_huge_level_in_min_window() -> None:
    level = big_level(60)
    renderer = BoardRenderer(FallbackTheme())
    surface = pygame.Surface((640, 480))
    layout = renderer.draw(surface, level, level.player, level.boxes, pygame.Rect(0, 40, 640, 440))
    assert layout.tile >= 4


def test_tile_floor_and_clipping_in_a_tiny_area() -> None:
    level = big_level(60)
    renderer = BoardRenderer(FallbackTheme())
    surface = pygame.Surface((300, 300))
    surface.fill((1, 2, 3))
    area = pygame.Rect(100, 100, 50, 50)
    layout = renderer.draw(surface, level, level.player, level.boxes, area)
    assert layout.tile == 4
    assert surface.get_at((99, 99))[:3] == (1, 2, 3)
    assert surface.get_at((151, 151))[:3] == (1, 2, 3)
    assert surface.get_clip() == surface.get_rect()


def test_draw_puts_tiles_at_their_cells() -> None:
    theme = FallbackTheme()
    renderer = BoardRenderer(theme)
    surface = pygame.Surface((400, 400))
    layout = renderer.draw(surface, LEVEL, LEVEL.player, LEVEL.boxes, surface.get_rect())
    for pos, kind in [((1, 2), TileKind.PLAYER), ((2, 3), TileKind.BOX_ON_GOAL), ((0, 2), TileKind.WALL)]:
        rect = layout.cell_rect(pos)
        expected = pygame.image.tobytes(theme.tile(kind, layout.tile), "RGB")
        assert pygame.image.tobytes(surface.subsurface(rect), "RGB") == expected


def test_highlight_and_arrow_draw_over_cells() -> None:
    theme = FallbackTheme()
    renderer = BoardRenderer(theme)
    plain = pygame.Surface((400, 400))
    marked = pygame.Surface((400, 400))
    renderer.draw(plain, LEVEL, LEVEL.player, LEVEL.boxes, plain.get_rect())
    layout = renderer.draw(
        marked,
        LEVEL,
        LEVEL.player,
        LEVEL.boxes,
        marked.get_rect(),
        highlight=[(1, 4)],
        arrow=((1, 3), Direction.RIGHT),
    )
    for pos in [(1, 4), (1, 3)]:
        rect = layout.cell_rect(pos)
        assert pygame.image.tobytes(plain.subsurface(rect), "RGB") != pygame.image.tobytes(
            marked.subsurface(rect), "RGB"
        )
    untouched = layout.cell_rect((4, 2))
    assert pygame.image.tobytes(plain.subsurface(untouched), "RGB") == pygame.image.tobytes(
        marked.subsurface(untouched), "RGB"
    )
