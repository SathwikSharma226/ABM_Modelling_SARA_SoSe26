"""Agent classes for the Waste-in-the-City ABM.

Five agent types mirror the lecture specification:

* :class:`LocalHumanAgent`      -- residents with regular movement.
* :class:`TouristAgent`         -- visitors drifting toward attractions.
* :class:`CleaningServiceAgent` -- rule-based street cleaners.
* :class:`DustBinAgent`         -- fixed bin / container infrastructure.
* :class:`DustTransporterAgent` -- empties full bins, drives to disposal.
"""

import mesa

from pathfinding import bfs_nearest, bfs_shortest_path
import config


def make_walkable(model, allow_public=True):
    """Build a predicate that decides whether a cell can be entered.

    Buildings (``#``) always block movement. Bin / container / disposal
    cells stay walkable so agents can stand on them.
    """
    width, height = model.grid.width, model.grid.height
    cells = model.cell_types

    def walkable(pos):
        x, y = pos
        if not (0 <= x < width and 0 <= y < height):
            return False
        ch = cells[y][x]
        if ch == "#":
            return False
        if ch == "P" and not allow_public:
            return False
        return True

    return walkable


class DustBinAgent(mesa.Agent):
    """A static bin or container that stores waste up to a fixed capacity."""

    def __init__(self, unique_id, model, capacity, kind="bin"):
        super().__init__(unique_id, model)
        self.capacity = capacity
        self.load = 0
        self.kind = kind
        self.overflow_count = 0

    @property
    def is_full(self):
        return self.load >= self.capacity

    @property
    def fill_ratio(self):
        return self.load / self.capacity if self.capacity else 0.0

    def add_waste(self, amount=1):
        """Try to add ``amount`` waste; return the leftover that overflowed."""
        free = max(0, self.capacity - self.load)
        accepted = min(free, amount)
        self.load += accepted
        leftover = amount - accepted
        if leftover > 0:
            self.overflow_count += 1
        return leftover

    def empty(self):
        """Empty the bin and return the amount removed."""
        removed = self.load
        self.load = 0
        return removed

    def step(self):
        # Passive infrastructure; method kept so Mesa can schedule uniformly.
        return


class _MovingAgent(mesa.Agent):
    """Base class with movement helpers shared by all mobile agents."""

    def random_walk(self):
        """Move to a random walkable 4-neighbour, if any exists."""
        walkable = make_walkable(self.model)
        x, y = self.pos
        candidates = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        candidates = [c for c in candidates if walkable(c)]
        if not candidates:
            return
        self.model.grid.move_agent(self, self.model.random.choice(candidates))

    def step_along_path(self, path):
        """Advance one cell along ``path``; return True on successful move.

        ``path`` is expected to start at the current cell, so the next move
        target is at index 1.
        """
        if not path or len(path) < 2:
            return False
        next_cell = path[1]
        if make_walkable(self.model)(next_cell):
            self.model.grid.move_agent(self, next_cell)
            return True
        return False


class LocalHumanAgent(_MovingAgent):
    """Resident commuting between home and work, occasionally littering."""

    def __init__(self, unique_id, model, home, work):
        super().__init__(unique_id, model)
        self.home = home
        self.work = work
        self.target = work
        self._path = None

    def _ensure_path(self):
        """Recompute the cached path when missing or stale."""
        if self._path and len(self._path) > 1 and self._path[0] == self.pos:
            return
        self._path = bfs_shortest_path(
            self.pos, self.target, make_walkable(self.model)
        )

    def _maybe_drop_waste(self):
        """With probability ``LOCAL_WASTE_PROB`` dispose of one waste unit.

        Prefers a nearby non-full bin within ``HUMAN_BIN_SEARCH_RADIUS``;
        otherwise litters on the current cell.
        """
        if self.model.random.random() >= config.LOCAL_WASTE_PROB:
            return

        bin_positions = [b.pos for b in self.model.bins if not b.is_full]
        nearest, path = bfs_nearest(self.pos, bin_positions, make_walkable(self.model))
        if nearest is not None and path is not None and len(path) - 1 <= config.HUMAN_BIN_SEARCH_RADIUS:
            for b in self.model.bins:
                if b.pos == nearest:
                    b.add_waste(1)
                    self.model.metrics["waste_into_bins"] += 1
                    return
        self.model.add_ground_waste(self.pos, 1)

    def step(self):
        # Flip the destination once the current target has been reached.
        if self.pos == self.target:
            self.target = self.home if self.target == self.work else self.work
            self._path = None

        self._ensure_path()
        if not self.step_along_path(self._path):
            self.random_walk()
        else:
            self._path = self._path[1:]

        self._maybe_drop_waste()


class TouristAgent(_MovingAgent):
    """Visitor that drifts toward attractions and litters more freely."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.target = self._pick_attraction()
        self._path = None

    def _pick_attraction(self):
        if self.model.attractions:
            return self.model.random.choice(self.model.attractions)
        return self.model.random.choice(self.model.walkable_cells)

    def step(self):
        # Occasionally switch attraction to capture unpredictable behaviour.
        if self.model.random.random() < 0.05 or self.pos == self.target:
            self.target = self._pick_attraction()
            self._path = None

        if not self._path or self._path[0] != self.pos:
            self._path = bfs_shortest_path(
                self.pos, self.target, make_walkable(self.model)
            )

        # 30% chance of meandering instead of following the planned path.
        if self.model.random.random() < 0.3 or not self._path:
            self.random_walk()
        else:
            if self.step_along_path(self._path):
                self._path = self._path[1:]

        if self.model.random.random() < config.TOURIST_WASTE_PROB:
            self.model.add_ground_waste(self.pos, 1)


class CleaningServiceAgent(_MovingAgent):
    """Street cleaner that picks waste using a rule-based strategy."""

    def __init__(self, unique_id, model, strategy=config.DEFAULT_CLEANER_STRATEGY, route=None):
        super().__init__(unique_id, model)
        if strategy not in config.CLEANER_STRATEGIES:
            raise ValueError(f"Unknown cleaner strategy: {strategy}")
        self.strategy = strategy
        self.route = route or []
        self._route_idx = 0
        self.cleaned_units = 0

    def _choose_target_nearest_waste(self):
        waste_cells = list(self.model.ground_waste.keys())
        return bfs_nearest(self.pos, waste_cells, make_walkable(self.model))

    def _choose_target_random_patrol(self):
        return None, None

    def _choose_target_fixed_route(self):
        if not self.route:
            return None, None
        target = self.route[self._route_idx % len(self.route)]
        path = bfs_shortest_path(self.pos, target, make_walkable(self.model))
        if self.pos == target:
            self._route_idx += 1
        return target, path

    def _choose_target_heatmap(self):
        """Creative-extension strategy: head for the strongest hotspot.

        Uses the model's decaying observation heatmap so cleaners exploit
        memory of where waste has recently appeared.
        """
        hotspot = self.model.heatmap_argmax()
        if hotspot is None:
            return None, None
        return hotspot, bfs_shortest_path(self.pos, hotspot, make_walkable(self.model))

    def step(self):
        # Priority action: clean waste already at the current cell.
        if self.pos in self.model.ground_waste:
            removed = self.model.ground_waste.pop(self.pos)
            self.cleaned_units += removed
            self.model.metrics["waste_cleaned"] += removed
            return

        if self.strategy == "nearest_waste":
            _, path = self._choose_target_nearest_waste()
        elif self.strategy == "random_patrol":
            _, path = self._choose_target_random_patrol()
        elif self.strategy == "fixed_route":
            _, path = self._choose_target_fixed_route()
        elif self.strategy == "heatmap":
            _, path = self._choose_target_heatmap()
        else:
            path = None

        if path and self.step_along_path(path):
            return
        self.random_walk()


class DustTransporterAgent(_MovingAgent):
    """Truck-style agent that empties full bins into the disposal point."""

    def __init__(self, unique_id, model, depot):
        super().__init__(unique_id, model)
        self.depot = depot
        self.cargo = 0
        self._target_bin = None
        self._path = None
        self.bins_emptied = 0

    def _pick_target_bin(self):
        """Select the closest bin above the fullness threshold."""
        threshold = config.TRANSPORTER_FULL_THRESHOLD
        candidates = [b.pos for b in self.model.bins if b.fill_ratio >= threshold]
        return bfs_nearest(self.pos, candidates, make_walkable(self.model))

    def step(self):
        # Drop cargo when standing on the depot.
        if self.pos == self.depot and self.cargo > 0:
            self.model.metrics["waste_disposed"] += self.cargo
            self.cargo = 0
            self._target_bin = None
            self._path = None
            return

        # Empty the bin we are standing on, then plan return to depot.
        if self._target_bin is not None and self.pos == self._target_bin:
            for b in self.model.bins:
                if b.pos == self.pos:
                    self.cargo += b.empty()
                    self.bins_emptied += 1
                    break
            self._target_bin = None
            self._path = bfs_shortest_path(self.pos, self.depot, make_walkable(self.model))
            return

        # Plan a new path when none is active.
        if self._path is None or len(self._path) < 2:
            if self.cargo > 0:
                self._path = bfs_shortest_path(self.pos, self.depot, make_walkable(self.model))
            else:
                target, path = self._pick_target_bin()
                self._target_bin = target
                self._path = path

        if self._path and self.step_along_path(self._path):
            self._path = self._path[1:]
