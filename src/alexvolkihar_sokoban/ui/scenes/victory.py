"""Victory overlay (spec 7.9): moves, pushes, time, stars, record badges; next level, replay, level select.

``back`` goes to the level select, like the last item.
"""

from __future__ import annotations

import pygame

from alexvolkihar_sokoban.core.pack import Pack, Par
from alexvolkihar_sokoban.scoring.records import RecordUpdate, RunResult
from alexvolkihar_sokoban.ui.hud import draw_overlay_panel, draw_star, format_time
from alexvolkihar_sokoban.ui.i18n import t
from alexvolkihar_sokoban.ui.input import Action
from alexvolkihar_sokoban.ui.scene import Scene
from alexvolkihar_sokoban.ui.scenes.game import leave_game
from alexvolkihar_sokoban.ui.widgets import MenuItem, MenuList, fit_text

MAX_STARS = 3
SUMMARY_SEPARATOR = "    "


class VictoryScene(Scene):
    is_overlay = True
    pack: Pack
    level_id: str
    record_update: RecordUpdate  # ``update`` would hide Scene.update()
    run: RunResult
    par: Par | None

    def on_enter(self, **params: object) -> None:
        pack, level_id = params.get("pack"), params.get("level_id")
        update, run, par = params.get("update"), params.get("run"), params.get("par")
        if not (
            isinstance(pack, Pack)
            and isinstance(level_id, str)
            and isinstance(update, RecordUpdate)
            and isinstance(run, RunResult)
            and (par is None or isinstance(par, Par))
        ):
            raise TypeError("victory scene needs pack, level_id, update, run and par")
        self.pack, self.level_id, self.record_update, self.run, self.par = pack, level_id, update, run, par
        self.next_id = pack.next_id(level_id)
        items = []
        if self.next_id is not None:
            items.append(MenuItem(lambda: t("Next level", "Niveau suivant"), self._next))
        items.append(MenuItem(lambda: t("Replay", "Rejouer"), self._replay))
        items.append(MenuItem(lambda: t("Level select", "Choix du niveau"), self._level_select))
        self.menu = MenuList(items)

    # -- texts -------------------------------------------------------------------------------------------

    def summary_lines(self) -> list[str]:
        run = self.run
        return [
            t(f"Moves {run.moves}", f"Pas {run.moves}"),
            t(f"Pushes {run.pushes}", f"Poussées {run.pushes}"),
            t(f"Time {format_time(run.elapsed_ms)}", f"Temps {format_time(run.elapsed_ms)}"),
        ]

    def badges(self) -> list[str]:
        """New records and the "better than par" badge; an assisted run only says it earned nothing."""
        if self.run.assisted:
            return [t("Assisted: no stars or records", "Aidé : ni étoiles ni records")]
        update = self.record_update
        badges = []
        if update.new_best_moves:
            badges.append(t("New best: moves", "Nouveau record : pas"))
        if update.new_best_pushes:
            badges.append(t("New best: pushes", "Nouveau record : poussées"))
        if update.new_best_time:
            badges.append(t("New best: time", "Nouveau record : temps"))
        if update.beats_par_moves:
            badges.append(t("Better than par!", "Mieux que le par !"))
        return badges

    # -- actions -----------------------------------------------------------------------------------------

    def _play(self, level_id: str) -> None:
        self.app.pop()  # back to the finished game, which is then replaced
        self.app.replace("game", pack=self.pack, level_id=level_id)

    def _next(self) -> None:
        if self.next_id is not None:
            self._play(self.next_id)

    def _replay(self) -> None:
        self._play(self.level_id)

    def _level_select(self) -> None:
        leave_game(self.app, "level_select", pack_id=self.pack.id)

    def handle_action(self, action: Action) -> None:
        if action is Action.BACK:
            self._level_select()
            return
        self.menu.handle_action(action)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.menu.handle_event(event)

    # -- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        palette = self.app.theme.palette
        fonts = self.app.fonts
        line = fonts.normal.get_linesize()
        small_line = fonts.small.get_linesize()
        title_text = t("Level complete!", "Niveau terminé !")
        summary = SUMMARY_SEPARATOR.join(self.summary_lines())
        badges = self.badges()
        star_r = max(12, fonts.title.get_height() // 2)
        menu_h = len(self.menu.items) * line * 9 // 5

        width = max(
            fonts.title.size(title_text)[0],
            fonts.normal.size(summary)[0],
            *(fonts.small.size(b)[0] for b in badges),
            (2 * star_r + line) * MAX_STARS,
        )
        width += 4 * line
        height = (
            line // 2
            + fonts.title.get_linesize()
            + 2 * star_r
            + line // 2
            + line
            + line // 4
            + small_line * len(badges)
            + line // 2
            + menu_h
            + line // 2
        )
        box = draw_overlay_panel(surface, palette, (width, height), border=palette.good)
        inner_w = box.width - 2 * line

        y = box.top + line // 2
        title = fonts.title.render(fit_text(title_text, fonts.title, inner_w), True, palette.good)
        surface.blit(title, title.get_rect(midtop=(box.centerx, y)))
        y += fonts.title.get_linesize()

        stars = self.record_update.stars_earned
        step = 2 * star_r + line
        x0 = box.centerx - step * (MAX_STARS - 1) // 2
        for i in range(MAX_STARS):
            draw_star(
                surface,
                (x0 + i * step, y + star_r),
                star_r,
                filled=i < stars,
                fill=palette.accent,
                outline=palette.muted,
            )
        y += 2 * star_r + line // 2

        text = fonts.normal.render(fit_text(summary, fonts.normal, inner_w), True, palette.text)
        surface.blit(text, text.get_rect(midtop=(box.centerx, y)))
        y += line + line // 4
        for badge in badges:
            colour = palette.muted if self.run.assisted else palette.good
            text = fonts.small.render(fit_text(badge, fonts.small, inner_w), True, colour)
            surface.blit(text, text.get_rect(midtop=(box.centerx, y)))
            y += small_line
        y += line // 2
        menu_rect = pygame.Rect(box.left, y, box.width, max(1, box.bottom - y - line // 2))
        self.menu.draw(surface, menu_rect, fonts.normal, palette)


SCENE = VictoryScene
