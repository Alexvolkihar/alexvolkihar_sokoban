"""Push-based A* search with deadlock pruning and hard limits (spec 7.4).

A state is the box set plus the player's normalised cell (the smallest cell index of the region the player
can walk to). Successors are single pushes. Keys are exact integers: the box bitmask (one bit per floor
cell, updated by XOR on each push) shifted left, plus the normalised player cell.

Memory stays proportional to the states, never to path lengths: an expanded state keeps its key, its
parent's id and its push in flat arrays, and an open-list entry is one integer that encodes its priority,
its parent and its push, from which the child state is rebuilt when it is popped. Duplicates are removed
when popped (the normalised cell needs the walk that the expansion does anyway).
"""

from __future__ import annotations

import heapq
import time
from array import array
from collections.abc import Callable

from alexvolkihar_sokoban.core.geometry import Pos
from alexvolkihar_sokoban.core.level import Level
from alexvolkihar_sokoban.solver.api import Mode, ProgressCallback, SolveLimits, SolveResult, SolveStatus
from alexvolkihar_sokoban.solver.deadlocks import FreezeChecker
from alexvolkihar_sokoban.solver.heuristics import box_costs, lower_bound
from alexvolkihar_sokoban.solver.reachability import DIRECTIONS, OPPOSITE, Board

CHECK_EVERY = 16
"""Expansions between two polls of ``should_stop`` and of the clock (the spec asks for at most 1,000)."""
PROGRESS_EVERY = 1024
"""Expansions between two ``on_progress`` calls; one more call is always made when the search ends."""

_F32 = 0xFFFFFFFF


def _bits(mask: int) -> list[int]:
    cells = []
    while mask:
        low = mask & -mask
        cells.append(low.bit_length() - 1)
        mask ^= low
    return cells


class _Search:
    def __init__(
        self,
        level: Level,
        boxes: frozenset[Pos],
        player: Pos,
        limits: SolveLimits,
        mode: Mode,
        should_stop: Callable[[], bool] | None,
        on_progress: ProgressCallback | None,
    ) -> None:
        self.started = time.monotonic()
        self.deadline = self.started + limits.time_s
        self.max_nodes = limits.max_nodes
        self.optimal = mode == "optimal"
        self.should_stop = should_stop
        self.on_progress = on_progress
        self.board = Board(level)
        self.costs = box_costs(self.board)
        self.dead = bytearray(1 if c < 0 else 0 for c in self.costs)
        self.freeze = FreezeChecker(self.board, self.dead)
        self.start_boxes = [self.board.index[b] for b in boxes]
        self.start_player = self.board.index[player]
        self.goal_mask = sum(1 << g for g in self.board.goals)
        self.player_bits = max(1, self.board.size.bit_length())
        self.push_bits = (self.board.size * 4).bit_length()
        self.expanded = 0
        self.generated = 0

    # -- results -----------------------------------------------------------------------------------------

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    def _result(self, status: SolveStatus, lurd: str | None = None) -> SolveResult:
        elapsed = self._elapsed_ms()
        if self.on_progress is not None:
            self.on_progress(self.expanded, elapsed)
        pushes = None if lurd is None else sum(c.isupper() for c in lurd)
        moves = None if lurd is None else len(lurd)
        return SolveResult(status, lurd, pushes, moves, self.expanded, self.generated, elapsed)

    def _stopped(self, status: SolveStatus) -> SolveResult:
        """A limit status, unless the caller asked to stop meanwhile (cancellation wins)."""
        if self.should_stop is not None and self.should_stop():
            status = SolveStatus.CANCELLED
        return self._result(status)

    def _lurd(self, pushes: list[int]) -> str:
        """Rebuild the full LURD (walks between pushes included) from the push codes ``box * 4 + d``."""
        board = self.board
        occ = board.occupancy(self.start_boxes)
        player = self.start_player
        out: list[str] = []
        for code in pushes:
            box, d = divmod(code, 4)
            behind = board.nbr[box * 4 + OPPOSITE[d]]
            out.extend(DIRECTIONS[k].char for k in self._path(occ, player, behind))
            out.append(DIRECTIONS[d].char.upper())
            target = board.nbr[box * 4 + d]
            occ[box], occ[target] = 0, 1
            player = box
        return "".join(out)

    def _path(self, occ: bytearray, start: int, goal: int) -> list[int]:
        """Directions of a shortest walk from ``start`` to ``goal`` that pushes nothing."""
        nbr = self.board.nbr
        came: dict[int, tuple[int, int]] = {start: (start, -1)}
        queue = [start]
        for cell in queue:
            if cell == goal:
                break
            for d in range(4):
                n = nbr[cell * 4 + d]
                if n >= 0 and not occ[n] and n not in came:
                    came[n] = (cell, d)
                    queue.append(n)
        dirs: list[int] = []
        cell = goal
        while cell != start:
            cell, d = came[cell]
            dirs.append(d)
        dirs.reverse()
        return dirs

    # -- search ------------------------------------------------------------------------------------------

    def run(self) -> SolveResult:
        board, costs, dead, nbr = self.board, self.costs, self.dead, self.board.nbr
        occ0 = board.occupancy(self.start_boxes)
        if any(dead[b] for b in self.start_boxes) or any(
            self.freeze.is_deadlock(occ0, b) for b in self.start_boxes
        ):
            return self._result(SolveStatus.UNSOLVABLE)

        # every push a box on each cell could make: (push code, target, cell the player pushes from),
        # leaving out pushes onto walls and dead squares
        push_moves = tuple(
            tuple(
                (cell * 4 + d, nbr[cell * 4 + d], nbr[cell * 4 + OPPOSITE[d]])
                for d in range(4)
                if nbr[cell * 4 + d] >= 0 and not dead[nbr[cell * 4 + d]] and nbr[cell * 4 + OPPOSITE[d]] >= 0
            )
            for cell in range(board.size)
        )
        is_deadlock = self.freeze.is_deadlock
        push_bits, player_bits = self.push_bits, self.player_bits
        push_mask = (1 << push_bits) - 1
        start_mask = sum(1 << b for b in self.start_boxes)
        # expanded states, by id: key (box mask << player_bits | normalised player), parent id, push, pushes
        keys: list[int] = []
        parents = array("i")
        push_codes = array("i")
        gs = array("i")
        closed: set[int] = set()
        # one integer per open entry: p1 | p2 | moves | parent id + 1 (0 = start) | push code
        heap: list[int] = [0]
        popped = 0
        next_check = 0
        next_progress = PROGRESS_EVERY
        should_stop = self.should_stop

        while heap:
            if popped >= next_check:  # counted on pops: duplicates cost a walk too
                next_check = popped + CHECK_EVERY
                if should_stop is not None and should_stop():
                    return self._result(SolveStatus.CANCELLED)
                if time.monotonic() >= self.deadline:
                    return self._stopped(SolveStatus.LIMIT_TIME)
            if self.expanded >= self.max_nodes:
                return self._stopped(SolveStatus.LIMIT_NODES)
            if self.on_progress is not None and self.expanded >= next_progress:
                next_progress = self.expanded + PROGRESS_EVERY
                self.on_progress(self.expanded, self._elapsed_ms())

            entry = heapq.heappop(heap)
            popped += 1
            code = entry & push_mask
            entry >>= push_bits
            parent = (entry & _F32) - 1
            moves = (entry >> 32) & _F32
            if parent < 0:
                mask, player, g = start_mask, self.start_player, 0
            else:
                box, d = divmod(code, 4)
                mask = (keys[parent] >> player_bits) ^ (1 << box) ^ (1 << nbr[box * 4 + d])
                player, g = box, gs[parent] + 1

            boxes = _bits(mask)
            occ = board.occupancy(boxes)
            walk, norm = board.region(occ, player)
            key = mask << player_bits | norm
            if key in closed:
                continue
            closed.add(key)
            node = len(keys)
            keys.append(key)
            parents.append(parent)
            push_codes.append(code if parent >= 0 else -1)
            gs.append(g)
            self.expanded += 1

            h = lower_bound(costs, boxes)
            for box in boxes:
                for child_code, target, behind in push_moves[box]:
                    if occ[target] or walk[behind] < 0:
                        continue
                    occ[box], occ[target] = 0, 1
                    frozen = is_deadlock(occ, target)
                    occ[box], occ[target] = 1, 0
                    if frozen:
                        continue
                    self.generated += 1
                    child_mask = mask ^ (1 << box) ^ (1 << target)
                    if child_mask == self.goal_mask:
                        return self._result(
                            SolveStatus.SOLVED,
                            self._lurd(self._pushes(node, parents, push_codes) + [child_code]),
                        )
                    child_h = h - costs[box] + costs[target]
                    child_moves = moves + walk[behind] + 1
                    if self.optimal:
                        p1, p2 = g + 1 + child_h, child_moves
                    else:
                        p1, p2 = child_h, g + 1
                    heapq.heappush(
                        heap,
                        ((((p1 << 32 | p2) << 32 | child_moves) << 32 | node + 1) << push_bits) | child_code,
                    )
        return self._result(SolveStatus.UNSOLVABLE)

    @staticmethod
    def _pushes(node: int, parents: array[int], push_codes: array[int]) -> list[int]:
        out: list[int] = []
        while node >= 0:
            if push_codes[node] >= 0:
                out.append(push_codes[node])
            node = parents[node]
        out.reverse()
        return out


def run_search(
    level: Level,
    boxes: frozenset[Pos],
    player: Pos,
    limits: SolveLimits,
    mode: Mode,
    should_stop: Callable[[], bool] | None,
    on_progress: ProgressCallback | None,
) -> SolveResult:
    """Search from an already validated, unsolved state. Called by ``solver.api.solve`` only."""
    return _Search(level, boxes, player, limits, mode, should_stop, on_progress).run()
