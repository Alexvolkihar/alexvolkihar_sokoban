from importlib.resources import files

import pygame
import pytest

from alexvolkihar_sokoban.ui.themes._draw import contrast_ratio, first_distinct, hex_rgb, readable_on
from alexvolkihar_sokoban.ui.themes.base import RGB, CachedTheme, Theme, TileKind
from alexvolkihar_sokoban.ui.themes.classic import ClassicTheme
from alexvolkihar_sokoban.ui.themes.contrast import ContrastTheme
from alexvolkihar_sokoban.ui.themes.kenney import KenneyTheme
from alexvolkihar_sokoban.ui.themes.neon import NeonTheme
from alexvolkihar_sokoban.ui.themes.palettes import PALETTES, PaletteTheme
from alexvolkihar_sokoban.ui.themes.registry import (
    DEFAULT_THEME_ID,
    THEME_IDS,
    available_themes,
    get_theme,
)

# Mood palettes adapted from the author's Dobble 3D project (colours only), besides "classic".
MOOD_IDS = (
    "meadow",
    "arcade",
    "storybook",
    "frost-keep",
    "candlelight",
    "runestone",
    "comic",
    "autumn",
    "high-seas",
    "afterglow",
    "picnic",
    "pixel",
    "deep-space",
    "ember",
    "brickyard",
    "woodland",
)

ALL_THEMES: list[Theme] = available_themes()
THEME_PARAMS = [pytest.param(t, id=t.id) for t in ALL_THEMES]


def _rgba(surface: pygame.Surface) -> bytes:
    return pygame.image.tobytes(surface, "RGBA")


def _on(theme: Theme, kind: TileKind, size: int = 32) -> pygame.Surface:
    """The tile as the renderer shows it: blitted over the theme background (tiles may be translucent)."""
    out = pygame.Surface((size, size))
    out.fill(theme.background)
    out.blit(theme.tile(kind, size), (0, 0))
    return out


def _differing_fraction(a: pygame.Surface, b: pygame.Surface, *, grey: bool = False) -> float:
    pa, pb = _rgba(a), _rgba(b)
    n = len(pa) // 4
    count = 0
    for i in range(n):
        ra, ga, ba = pa[4 * i], pa[4 * i + 1], pa[4 * i + 2]
        rb, gb, bb = pb[4 * i], pb[4 * i + 1], pb[4 * i + 2]
        if grey:
            la = 0.299 * ra + 0.587 * ga + 0.114 * ba
            lb = 0.299 * rb + 0.587 * gb + 0.114 * bb
            if abs(la - lb) > 24:
                count += 1
        elif abs(ra - rb) + abs(ga - gb) + abs(ba - bb) > 48:
            count += 1
    return count / n


def _mean(surface: pygame.Surface) -> RGB:
    data = _rgba(surface)
    n = len(data) // 4
    return (
        sum(data[0::4]) // n,
        sum(data[1::4]) // n,
        sum(data[2::4]) // n,
    )


def test_registry_lists_the_plan_themes_first_then_the_mood_palettes() -> None:
    assert THEME_IDS[:4] == ("kenney", "classic", "neon", "contrast")
    assert set(THEME_IDS[4:]) == set(MOOD_IDS)
    assert len(set(THEME_IDS)) == len(THEME_IDS)
    assert [t.id for t in available_themes()] == list(THEME_IDS)


def test_theme_classes() -> None:
    assert isinstance(get_theme("kenney"), KenneyTheme)
    assert isinstance(get_theme("classic"), ClassicTheme)
    assert isinstance(get_theme("neon"), NeonTheme)
    assert isinstance(get_theme("contrast"), ContrastTheme)
    for theme_id in MOOD_IDS:
        assert isinstance(get_theme(theme_id), PaletteTheme)
    assert all(isinstance(t, CachedTheme) for t in available_themes())


def test_get_theme_finds_every_registered_theme() -> None:
    for theme_id in THEME_IDS:
        assert get_theme(theme_id).id == theme_id


def test_unknown_theme_falls_back_to_kenney() -> None:
    assert DEFAULT_THEME_ID == "kenney"
    assert get_theme("no-such-theme").id == "kenney"
    assert get_theme("").id == "kenney"


def test_themes_have_english_names() -> None:
    names = {t.id: t.name for t in available_themes()}
    assert names["classic"] == "Classic"
    assert names["contrast"] == "High contrast"
    assert names["picnic"] == "Picnic" and names["frost-keep"] == "Frost Keep"
    for theme_id in MOOD_IDS:  # neutral names that say the mood, nothing else
        assert names[theme_id] == theme_id.replace("-", " ").title()
    assert all(names.values())


def test_palettes_cover_classic_and_the_mood_themes() -> None:
    assert {p.id for p in PALETTES} == {"classic", *MOOD_IDS}


@pytest.mark.parametrize("theme", THEME_PARAMS)
def test_every_theme_draws_every_kind_at_sizes(theme: Theme) -> None:
    for size in (4, 16, 48, 64):
        for kind in TileKind:
            assert theme.tile(kind, size).get_size() == (size, size)


@pytest.mark.parametrize("theme", THEME_PARAMS)
def test_tiles_are_cached(theme: Theme) -> None:
    for kind in TileKind:
        assert theme.tile(kind, 32) is theme.tile(kind, 32)


@pytest.mark.parametrize("theme", THEME_PARAMS)
def test_every_tile_kind_looks_different(theme: Theme) -> None:
    drawn = {k: _rgba(_on(theme, k)) for k in TileKind if k is not TileKind.OUTSIDE}
    assert len(set(drawn.values())) == len(drawn)


@pytest.mark.parametrize("theme", THEME_PARAMS)
def test_board_elements_are_legible(theme: Theme) -> None:
    def tile(kind: TileKind) -> pygame.Surface:
        return _on(theme, kind)

    floor, wall, goal = tile(TileKind.FLOOR), tile(TileKind.WALL), tile(TileKind.GOAL)
    box, done = tile(TileKind.BOX), tile(TileKind.BOX_ON_GOAL)
    player, player_goal = tile(TileKind.PLAYER), tile(TileKind.PLAYER_ON_GOAL)
    assert _differing_fraction(floor, wall) > 0.5
    assert _differing_fraction(floor, goal) > 0.05
    assert _differing_fraction(floor, box) > 0.3
    assert _differing_fraction(box, done) > 0.2
    assert _differing_fraction(floor, player) > 0.15
    assert _differing_fraction(player, player_goal) > 0.03
    assert _differing_fraction(wall, box) > 0.2
    assert _differing_fraction(wall, done) > 0.2


@pytest.mark.parametrize("theme", THEME_PARAMS)
def test_ui_palette_is_readable(theme: Theme) -> None:
    p = theme.palette
    assert contrast_ratio(p.text, theme.background) >= 4.5
    assert contrast_ratio(p.text, p.panel) >= 4.5
    assert contrast_ratio(p.muted, p.panel) >= 3.0
    assert contrast_ratio(p.accent, p.panel) >= 3.0
    assert contrast_ratio(p.good, p.panel) >= 3.0
    assert contrast_ratio(p.bad, p.panel) >= 3.0


def test_contrast_theme_is_shape_coded() -> None:
    theme = ContrastTheme()
    box, done = _on(theme, TileKind.BOX), _on(theme, TileKind.BOX_ON_GOAL)
    floor, goal = _on(theme, TileKind.FLOOR), _on(theme, TileKind.GOAL)
    assert _differing_fraction(box, done, grey=True) > 0.05
    assert _differing_fraction(floor, goal, grey=True) > 0.05


def test_contrast_theme_uses_the_okabe_ito_palette() -> None:
    theme = ContrastTheme()
    assert theme.background == (0, 0, 0)
    box = theme.tile(TileKind.BOX, 32)
    orange = sum(1 for x in range(32) for y in range(32) if box.get_at((x, y))[:3] == (230, 159, 0))
    assert orange > 0.3 * 32 * 32


def _kenney_sprite(name: str) -> pygame.Surface:
    resource = files("alexvolkihar_sokoban.data") / "themes" / "kenney" / f"{name}.png"
    assert resource.is_file()
    with resource.open("rb") as fh:
        return pygame.image.load(fh, f"{name}.png")


def test_kenney_assets_load_via_importlib_resources() -> None:
    theme = KenneyTheme()
    wall, crate = (_kenney_sprite(n) for n in ("WallRound_Brown", "Crate_Brown"))
    assert crate.get_size() == (64, 64)
    assert _rgba(theme.tile(TileKind.WALL, 64)) == _rgba(wall)
    floor = theme.tile(TileKind.FLOOR, 64)  # procedural sand ground (the legacy empty.png is all black)
    assert _rgba(floor) != _rgba(_kenney_sprite("empty"))
    expected = pygame.Surface((64, 64))
    expected.blit(floor, (0, 0))
    expected.blit(crate, (0, 0))
    drawn = _rgba(_on(theme, TileKind.BOX, 64))
    assert max(abs(a - b) for a, b in zip(drawn, _rgba(expected), strict=True)) <= 2


def test_kenney_tiles_scale() -> None:
    theme = KenneyTheme()
    assert theme.tile(TileKind.BOX, 20).get_size() == (20, 20)
    assert _differing_fraction(_on(theme, TileKind.FLOOR), _on(theme, TileKind.BOX)) > 0.3


def test_kenney_outside_is_transparent() -> None:
    tile = KenneyTheme().tile(TileKind.OUTSIDE, 16)
    assert all(tile.get_at((x, y)).a == 0 for x in range(16) for y in range(16))


def test_kenney_box_on_goal_is_a_tinted_crate() -> None:
    theme = KenneyTheme()
    box, done = _mean(theme.tile(TileKind.BOX, 64)), _mean(theme.tile(TileKind.BOX_ON_GOAL, 64))
    assert done[1] > box[1] and done[1] - done[0] > box[1] - box[0]


def test_dark_mood_themes_get_light_text() -> None:
    by_id = {p.id: p for p in PALETTES}
    assert by_id["deep-space"].dark and not by_id["classic"].dark
    assert sum(get_theme("deep-space").palette.text) > sum(get_theme("classic").palette.text)


def test_contrast_ratio() -> None:
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert contrast_ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)
    assert contrast_ratio((119, 119, 119), (119, 119, 119)) == pytest.approx(1.0)


def test_hex_rgb() -> None:
    assert hex_rgb("#357660") == (53, 118, 96)
    assert hex_rgb("ffffff") == (255, 255, 255)
    with pytest.raises(ValueError):
        hex_rgb("#fff")


def test_first_distinct_prefers_order_then_distance() -> None:
    red, dark_red, blue = (200, 30, 30), (150, 20, 20), (30, 30, 200)
    assert first_distinct([red, blue], [(0, 0, 0)], 100) == red
    assert first_distinct([dark_red, blue], [(160, 20, 20)], 100) == blue
    assert first_distinct([dark_red, red], [(160, 20, 20)], 500) == red  # none far enough: most distinct


def test_readable_on_reaches_the_requested_contrast() -> None:
    panel = (251, 246, 234)
    assert contrast_ratio(readable_on(panel, (242, 201, 76), 3.0), panel) >= 3.0
    assert readable_on(panel, (36, 97, 79), 3.0) == (36, 97, 79)  # already readable: unchanged
