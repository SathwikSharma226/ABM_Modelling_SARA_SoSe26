"""
agents.py
---------
Agent classes for the Waste-in-the-City ABM.

The model uses Mesa (https://mesa.readthedocs.io). All agents inherit from
``mesa.Agent`` and implement a ``step()`` method that defines what they do
on each simulation tick.

Five agent types are defined here, mirroring the lecture description:

1. ``LocalHumanAgent``   – residents with regular movement.
2. ``TouristAgent``      – visitors that drift toward attractions.
3. ``CleaningServiceAgent`` – street cleaners (rule-based strategies).
4. ``DustBinAgent``      – fixed bins / containers (infrastructure).
5. ``DustTransporterAgent`` – empties full bins, drives to disposal.
"""

import random  # local random calls fall back to model.random for reproducibility

import mesa  # ABM framework required by the assignment

from pathfinding import bfs_nearest, bfs_shortest_path
import config


# ---------------------------------------------------------------------------
# Helper: walkability predicate factory
# ---------------------------------------------------------------------------

def make_walkable(model, allow_public=True):
    """Return a predicate that decides whether a cell can be entered.

    Buildings (``#``) always block movement. Bins/containers/disposal
    cells are walkable so cleaners and humans can stand on / next to them.
    """
    width, height = model.grid.width, model.grid.height
    cells = model.cell_types  # 2D list with characters from the layout

    def walkable(pos):
        x, y = pos
        # Reject coordinates that fall outside the grid bounds.
        if not (0 <= x < width and 0 <= y < height):
            return False
        ch = cells[y][x]
        # '#' is a building and blocks movement.
        if ch == "#":
            return False
        # Optionally treat public squares as walkable (true by default).
        if ch == "P" and not allow_public:
            return False
        return True

    return walkable


# ---------------------------------------------------------------------------
# Fixed infrastructure
# ---------------------------------------------------------------------------

class DustBinAgent(mesa.Agent):
    """A static bin or container that stores waste up to a capacity."""

    def __init__(self, unique_id, model, capacity, kind="bin"):
        # Pass identification + model to the Mesa base class.
        super().__init__(unique_id, model)
        # Remember the maximum amount of waste the bin can hold.
        self.capacity = capacity
        # Current load; starts empty.
        self.load = 0
        # 'bin' (small) or 'container' (large) – useful for stats / drawing.
        self.kind = kind
        # Cumulative count of overflow events for analytics.
        self.overflow_count = 0

    @property
    def is_full(self):
        # Convenience check used by humans deciding whether to use the bin.
        return self.load >= self.capacity

    @property
    def fill_ratio(self):
        # Fraction of capacity currently used (0..1+).
        return self.load / self.capacity if self.capacity else 0.0

    def add_waste(self, amount=1):
        """Try to add waste. Returns the amount that did NOT fit (overflow)."""
        # Compute how much we can still accept before hitting capacity.
        free = max(0, self.capacity - self.load)
        accepted = min(free, amount)
        self.load += accepted
        leftover = amount - accepted
        if leftover > 0:
            # Track that we overflowed at least once for the metrics.
            self.overflow_count += 1
        return leftover

    def empty(self):
        """Empty the bin and return how much waste was removed."""
        # Save current load, reset, return the amount the transporter takes.
        removed = self.load
        self.load = 0
        return removed

    def step(self):
        # Bins are passive infrastructure – nothing to do per tick.
        # We still implement step() so Mesa can schedule them uniformly.
        return


# ---------------------------------------------------------------------------
# Mobile agents – shared movement helpers
# ---------------------------------------------------------------------------

class _MovingAgent(mesa.Agent):
    """Base class with helpers shared by all moving agents."""

    def random_walk(self):
        """Move one step to a random walkable neighbour, if any."""
        # Use the model's RNG so runs are reproducible with a seed.
        walkable = make_walkable(self.model)
        # Get all 4-neighbour cells around current position.
        x, y = self.pos
        candidates = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        # Filter to walkable cells only.
        candidates = [c for c in candidates if walkable(c)]
        if not candidates:
            return  # surrounded by walls -> stay put
        new_pos = self.model.random.choice(candidates)
        # Mesa's MultiGrid handles agent move + neighbour bookkeeping.
        self.model.grid.move_agent(self, new_pos)

    def step_along_path(self, path):
        """Advance one cell along a precomputed path; returns True if moved."""
        # ``path`` includes current cell at index 0; index 1 is next step.
        if not path or len(path) < 2:
            return False
        next_cell = path[1]
        # Re-validate walkability in case world changed (defensive).
        if make_walkable(self.model)(next_cell):
            self.model.grid.move_agent(self, next_cell)
            return True
        return False


# ---------------------------------------------------------------------------
# Local human
# ---------------------------------------------------------------------------

class LocalHumanAgent(_MovingAgent):
    """A resident with a daily home<->work pattern who occasionally litters."""

    def __init__(self, unique_id, model, home, work):
        super().__init__(unique_id, model)
        # Persistent endpoints -> generate a daily oscillation between them.
        self.home = home
        self.work = work
        # Current target the agent is heading toward.
        self.target = work
        # Cached path so we don't recompute BFS every step.
        self._path = None

    def _ensure_path(self):
        # Recompute a path when we don't have one or have arrived at next target.
        if self._path and len(self._path) > 1 and self._path[0] == self.pos:
            return  # path still valid and starts at current cell
        self._path = bfs_shortest_path(
            self.pos, self.target, make_walkable(self.model)
        )

    def _maybe_drop_waste(self):
        """With some probability, dispose of waste – preferring bins."""
        # Probability gate first to keep the simulation cheap.
        if self.model.random.random() >= config.LOCAL_WASTE_PROB:
            return

        # Look for a nearby bin within HUMAN_BIN_SEARCH_RADIUS using BFS.
        bin_positions = [b.pos for b in self.model.bins if not b.is_full]
        nearest, path = bfs_nearest(self.pos, bin_positions, make_walkable(self.model))
        if nearest is not None and path is not None and len(path) - 1 <= config.HUMAN_BIN_SEARCH_RADIUS:
            # Use the bin (we abstract away physically walking there for speed).
            for b in self.model.bins:
                if b.pos == nearest:
                    b.add_waste(1)
                    self.model.metrics["waste_into_bins"] += 1
                    return
        # No bin reachable nearby -> drop on the ground at current cell.
        self.model.add_ground_waste(self.pos, 1)

    def step(self):
        # 1. Decide whether we should swap targets (arrived at home/work).
        if self.pos == self.target:
            # Toggle between home and work to mimic daily commuting.
            self.target = self.home if self.target == self.work else self.work
            self._path = None  # force recomputation for new target

        # 2. Make sure we have a current path then walk one step along it.
        self._ensure_path()
        if not self.step_along_path(self._path):
            # Path failed (e.g. blocked) -> fall back to a random walk.
            self.random_walk()
        else:
            # Drop the consumed cell from the cached path.
            self._path = self._path[1:]

        # 3. Possibly produce waste this step.
        self._maybe_drop_waste()


# ---------------------------------------------------------------------------
# Tourist
# ---------------------------------------------------------------------------

class TouristAgent(_MovingAgent):
    """A visitor that drifts toward attractions and litters more freely."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        # Pick a random attraction as the initial point of interest.
        self.target = self._pick_attraction()
        self._path = None

    def _pick_attraction(self):
        # Choose uniformly among attraction cells if there are any.
        if self.model.attractions:
            return self.model.random.choice(self.model.attractions)
        # Fallback: pick a random walkable cell so the tourist still moves.
        return self.model.random.choice(self.model.walkable_cells)

    def step(self):
        # With small probability, switch to a new attraction (less predictable).
        if self.model.random.random() < 0.05 or self.pos == self.target:
            self.target = self._pick_attraction()
            self._path = None

        # Recompute path when needed (cache invalidation kept simple).
        if not self._path or self._path[0] != self.pos:
            self._path = bfs_shortest_path(
                self.pos, self.target, make_walkable(self.model)
            )

        # Tourists sometimes meander -> 30% chance of random walk instead.
        if self.model.random.random() < 0.3 or not self._path:
            self.random_walk()
        else:
            if self.step_along_path(self._path):
                self._path = self._path[1:]

        # Tourists drop waste with a higher probability than locals.
        if self.model.random.random() < config.TOURIST_WASTE_PROB:
            # Tourists are less likely to use bins -> always drop on the ground.
            self.model.add_ground_waste(self.pos, 1)


# ---------------------------------------------------------------------------
# Cleaning service
# ---------------------------------------------------------------------------

class CleaningServiceAgent(_MovingAgent):
    """Street cleaner that picks waste using a rule-based strategy."""

    def __init__(self, unique_id, model, strategy=config.DEFAULT_CLEANER_STRATEGY, route=None):
        super().__init__(unique_id, model)
        # Validate the strategy against the whitelisted set in config.
        if strategy not in config.CLEANER_STRATEGIES:
            raise ValueError(f"Unknown cleaner strategy: {strategy}")
        self.strategy = strategy
        # Optional fixed patrol route (list of cells); used for 'fixed_route'.
        self.route = route or []
        self._route_idx = 0
        # Total cells cleaned -> used to compute efficiency in metrics.
        self.cleaned_units = 0

    # -- strategies ---------------------------------------------------------

    def _choose_target_nearest_waste(self):
        # Look at all known ground-waste cells and BFS to the closest one.
        waste_cells = list(self.model.ground_waste.keys())
        target, path = bfs_nearest(self.pos, waste_cells, make_walkable(self.model))
        return target, path

    def _choose_target_random_patrol(self):
        # No global plan; just wander on the street network.
        return None, None

    def _choose_target_fixed_route(self):
        # Cycle through preassigned waypoints (if any provided).
        if not self.route:
            return None, None
        target = self.route[self._route_idx % len(self.route)]
        path = bfs_shortest_path(self.pos, target, make_walkable(self.model))
        # Advance route index when arrived to ensure we keep moving forward.
        if self.pos == target:
            self._route_idx += 1
        return target, path

    def _choose_target_heatmap(self):
        """Creative-extension strategy: head for the highest heatmap score.

        The model keeps a decaying heatmap of where waste was observed.
        Cleaners exploit this memory by going to the strongest hotspot.
        """
        hotspot = self.model.heatmap_argmax()
        if hotspot is None:
            return None, None
        path = bfs_shortest_path(self.pos, hotspot, make_walkable(self.model))
        return hotspot, path

    # -- main step ----------------------------------------------------------

    def step(self):
        # 1. If standing on waste, clean it immediately (priority action).
        if self.pos in self.model.ground_waste:
            removed = self.model.ground_waste.pop(self.pos)
            self.cleaned_units += removed
            self.model.metrics["waste_cleaned"] += removed
            return  # one action per step (cleaning then idle)

        # 2. Otherwise pick a movement plan based on the configured strategy.
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

        # 3. Execute the plan (or random-walk as a graceful fallback).
        if path and self.step_along_path(path):
            return
        self.random_walk()


# ---------------------------------------------------------------------------
# Dust transporter
# ---------------------------------------------------------------------------

class DustTransporterAgent(_MovingAgent):
    """Big truck-style agent: empties full bins/containers into disposal."""

    def __init__(self, unique_id, model, depot):
        super().__init__(unique_id, model)
        # Depot = disposal point we return to in order to "process" waste.
        self.depot = depot
        # Onboard cargo waiting to be dropped at the depot.
        self.cargo = 0
        # Current bin we're heading toward; None if idle / returning.
        self._target_bin = None
        # Cached path to current target (bin or depot).
        self._path = None
        # Workload counter -> incremented each time we visit a bin.
        self.bins_emptied = 0

    def _pick_target_bin(self):
        """Choose the closest sufficiently-full bin."""
        # Filter bins above the "full enough" threshold to avoid pointless trips.
        threshold = config.TRANSPORTER_FULL_THRESHOLD
        candidates = [b.pos for b in self.model.bins if b.fill_ratio >= threshold]
        target, path = bfs_nearest(self.pos, candidates, make_walkable(self.model))
        return target, path

    def step(self):
        # 1. If standing on the depot with cargo, dump it (waste terminates).
        if self.pos == self.depot and self.cargo > 0:
            self.model.metrics["waste_disposed"] += self.cargo
            self.cargo = 0
            self._target_bin = None
            self._path = None
            return

        # 2. If standing on the target bin, empty it onto our truck.
        if self._target_bin is not None and self.pos == self._target_bin:
            for b in self.model.bins:
                if b.pos == self.pos:
                    self.cargo += b.empty()
                    self.bins_emptied += 1
                    break
            # After emptying, head back to the depot.
            self._target_bin = None
            self._path = bfs_shortest_path(self.pos, self.depot, make_walkable(self.model))
            return

        # 3. If we have no target, plan a new one (next bin or depot).
        if self._path is None or len(self._path) < 2:
            if self.cargo > 0:
                # Returning to depot to unload before continuing.
                self._path = bfs_shortest_path(self.pos, self.depot, make_walkable(self.model))
            else:
                target, path = self._pick_target_bin()
                self._target_bin = target
                self._path = path

        # 4. Walk one step along the current plan, or fall back to staying.
        if self._path and self.step_along_path(self._path):
            self._path = self._path[1:]
