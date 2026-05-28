import mesa

from pathfinding import bfs_nearest, bfs_shortest_path
import config


def make_walkable(model, allow_public=True):
    """This is a helper funtion that decides whether a cell is walkable or not for the agents based on the layout.

    Buildings (``#``) always block movement. Bin / container / disposal  cells stay walkable so agents can stand on them.
    """
    width, height = model.grid.width, model.grid.height
    cells = model.cell_types

    def walkable(pos):
        x, y = pos
        if not (0 <= x < width and 0 <= y < height): # make sure that the postion is within the bounds of the grid.
            return False
        ch = cells[y][x]
        if ch == "#": # buildings are not walkable.
            return False
        if ch == "P" and not allow_public: # check if the cell is public area and make sure public is allowed.
            return False
        return True

    return walkable


class DustBinAgent(mesa.Agent):
    """A static bin or container that stores waste up to a fixed capacity. Represents regular bins as well as large containers."""

    def __init__(self, unique_id, model, capacity, kind="bin"):
        super().__init__(unique_id, model)
        self.capacity = capacity
        self.load = 0
        self.kind = kind
        self.overflow_count = 0

    @property
    # property decorator because it represents a state and not an action.
    def is_full(self):
        return self.load >= self.capacity

    @property
    # property decorator because it represents a state and not an action.
    def fill_ratio(self): # Specially for transportors to decide when to empty the bin.
        return self.load / self.capacity if self.capacity else 0.0

    def add_waste(self, amount=1):
        """Try to add ``amount`` waste; return the leftover that overflowed."""
        free = max(0, self.capacity - self.load) # calculate remaining free capacity
        accepted = min(free, amount)             # accept as much waste as possible
        self.load += accepted                    # update current load of the bin
        leftover = amount - accepted             # compute what did not fit 
        if leftover > 0:                         # if overflow occured, measure the overflow and return the leftover
            self.overflow_count += 1
        return leftover

    def empty(self):
        """Empty the bin and return the amount removed."""
        removed = self.load
        self.load = 0
        return removed

    def step(self):
        # bins are passive but having step() allows to be scheduled uniformly with other agents
        return

# provides common movement helper methods so they do not have to be repeated in every mobile agent class
# starts with _ since it is only used as a helper class and not to be used publically
class _MovingAgent(mesa.Agent):
    """Base class with movement helpers shared by all moving agents."""

    def random_walk(self):
        """Move to a random walkable 4-neighbour, if any exists."""
        
        walkable = make_walkable(self.model)
        x, y = self.pos
        possible_destinations = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        possible_destinations = [c for c in possible_destinations if walkable(c)]
        if not possible_destinations:
            return
        self.model.grid.move_agent(self, self.model.random.choice(possible_destinations))

    def step_along_path(self, path):
        """Advance one cell along ``path``; return True on successful move.
        ``path`` is expected to start at the current cell, so the next move target is at index 1.
        """
        if not path or len(path) < 2: # If the path is missing or too short, return False
            return False
        next_cell = path[1]
        if make_walkable(self.model)(next_cell):
            self.model.grid.move_agent(self, next_cell)
            return True
        return False


class LocalHumanAgent(_MovingAgent):
    """Resident commuting between home and work, occasionally littering."""

    def __init__(self, unique_id, model, home, work):
        super().__init__(unique_id, model) # calling super constructor to initialize the agent with unique_id and model as our parameters and not mesa agent's default parameters
        self.home = home
        self.work = work
        self.target = work
        self._path = None

    def _ensure_path(self):
        """Make sure the cached path to the current target exists and is still valid."""
        if self._path and len(self._path) > 1 and self._path[0] == self.pos: # If there is already a usable path starting from the current position, keep it
            return
        self._path = bfs_shortest_path(self.pos, self.target, make_walkable(self.model)) # Otherwise compute a new path to the target and cache it

    def _maybe_drop_waste(self):
        """With probability ``LOCAL_WASTE_PROB`` dispose of one waste unit.
        Prefers a nearby non-full bin within ``HUMAN_BIN_SEARCH_RADIUS``, otherwise litters on the current cell.
        """
        if self.model.random.random() >= config.LOCAL_WASTE_PROB:
            return

        bin_positions = []
        for b in self.model.bins:
            if b.is_full == False:
                bin_positions.append(b.pos)

        nearest, path = bfs_nearest(self.pos, bin_positions, make_walkable(self.model))
        if nearest is not None and path is not None and len(path) - 1 <= config.HUMAN_BIN_SEARCH_RADIUS: # path length in nodes includes the starting cell. The number of movement steps is one less.
            for b in self.model.bins:
                if b.pos == nearest:
                    b.add_waste(1)
                    self.model.metrics["waste_into_bins"] += 1
                    return
        self.model.add_ground_waste(self.pos, 1) # If no suitable bin was found, add waste to the ground at the current position.

    def step(self):
        
        if self.pos == self.target: # Flip the destination once the current target has been reached.
            self.target = self.home if self.target == self.work else self.work
            self._path = None

        self._ensure_path() # Ensure there is a valid path.
        if not self.step_along_path(self._path): # If unable to follow the path do a random walk.
            self.random_walk()
        else:
            self._path = self._path[1:] # If movement succeeds remove the first step from the cached path.

        self._maybe_drop_waste() # After moving, drop waste.


class TouristAgent(_MovingAgent):
    """Visitor that drifts toward attractions and litters more freely."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.target = self._pick_attraction()
        self._path = None

    def _pick_attraction(self):
        return self.model.random.choice(self.model.walkable_cells)

    def step(self):
        # Occasionally switch attraction to capture unpredictable behaviour.
        if self.model.random.random() < 0.05 or self.pos == self.target:
            self.target = self._pick_attraction()
            self._path = None

        if not self._path or self._path[0] != self.pos:
            self._path = bfs_shortest_path(self.pos, self.target, make_walkable(self.model))

        # 30% chance of wandering aimlessly instead of following the planned path.
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
        self.strategy = strategy
        self.route = route or []
        self._route_idx = 0
        self.cleaned_units = 0

    # All the functions starting with _ below are strategy based. They return a target cell and a path to it, or (None, None) if no target is currently chosen.

    def _choose_target_nearest_waste(self):
        """find the nearest cell that currently contains waste on the ground.
        target selection logic for the nearest_waste strategy"""

        waste_cells = list(self.model.ground_waste.keys()) # ground_waste is a dictionary with positions as keys and waste amounts as values. We want only the positions, so we take only the keys.
        return bfs_nearest(self.pos, waste_cells, make_walkable(self.model))

    # no function, only for uniformity, anyway in step(), finally it will go to random if path is none
    def _choose_target_random_patrol(self):
        return None, None

    def _choose_target_fixed_route(self):
        """Follow a fixed cyclic route through the city"""

        if not self.route: # If no route is defined, do nothing.
            return None, None
        target = self.route[self._route_idx % len(self.route)] # Get the current target from the route using modulo to cycle through the route, meaning after the last target, it will come back to the first one.
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
        # Priority to clean waste already at the current cell.
        if self.pos in self.model.ground_waste:
            removed = self.model.ground_waste.pop(self.pos)
            self.cleaned_units += removed
            self.model.metrics["waste_cleaned"] += removed
            return

        if self.strategy == "nearest_waste":
            _, path = self._choose_target_nearest_waste() #  the _choose_target_* functions give two values but we only need the path, so using _ to ignore target value.
        elif self.strategy == "random_patrol":
            _, path = self._choose_target_random_patrol()
        elif self.strategy == "fixed_route":
            _, path = self._choose_target_fixed_route()
        elif self.strategy == "heatmap":
            _, path = self._choose_target_heatmap()
        else:
            path = None

        if path and self.step_along_path(path): # If a path exists and movement along it succeeds, keep following it in subsequent steps.
            return
        self.random_walk() # If no path or movement fails, do a random walk this turn and reconsider strategy next turn.


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

        candidates = []
        for bin_agent in self.model.bins:
            if bin_agent.fill_ratio >= threshold:
                candidates.append(bin_agent.pos)

        return bfs_nearest(self.pos, candidates, make_walkable(self.model))

    def step(self):
        # Drop cargo when standing on the depot.
        if self.pos == self.depot and self.cargo > 0:
            self.model.metrics["waste_disposed"] += self.cargo
            self.cargo = 0
            self._target_bin = None
            self._path = None
            return

        # Empty the bin where it is standing on, then plan return to depot.
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
