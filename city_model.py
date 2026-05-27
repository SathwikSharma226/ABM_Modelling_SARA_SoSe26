"""The Mesa ``Model`` class that ties the simulation together.

Parses the ASCII city layout, places fixed infrastructure, spawns the
mobile agent population, tracks ground waste and heatmap state, and
drives per-step updates through Mesa's scheduler and ``DataCollector``.
"""

import os

import mesa

import config
from agents import (
    CleaningServiceAgent,
    DustBinAgent,
    DustTransporterAgent,
    LocalHumanAgent,
    TouristAgent,
)


def load_layout(path):
    """Read an ASCII layout file and return ``(rows, width, height)``.

    Rows are returned as a list of equal-length strings padded with ``#``
    so the grid is a clean rectangle indexable as ``rows[y][x]``.
    """
    with open(path, "r", encoding="utf-8") as f:
        rows = [line.rstrip("\n") for line in f if line.strip()]
    height = len(rows)
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, "#") for r in rows]
    return rows, width, height


class WasteCityModel(mesa.Model):
    """Top-level Mesa model orchestrating the simulation."""

    def __init__(
        self,
        layout_file=config.DEFAULT_LAYOUT_FILE,
        num_locals=config.NUM_LOCALS,
        num_tourists=config.NUM_TOURISTS,
        num_cleaners=config.NUM_CLEANERS,
        num_transporters=config.NUM_TRANSPORTERS,
        cleaner_strategy=config.DEFAULT_CLEANER_STRATEGY,
        seed=config.RANDOM_SEED,
    ):
        super().__init__()
        self._seed_value = seed
        if seed is not None:
            self.random.seed(seed)

        # Resolve layout path relative to this file for notebook-friendliness.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        layout_path = layout_file
        if not os.path.isabs(layout_path):
            layout_path = os.path.join(base_dir, layout_file)

        self.cell_types, width, height = load_layout(layout_path)

        # MultiGrid: multiple agents per cell, hard borders (no torus).
        self.grid = mesa.space.MultiGrid(width, height, torus=False)
        self.schedule = mesa.time.RandomActivation(self)

        self.bins = []
        self.attractions = []
        self.walkable_cells = []
        self.disposal_points = []
        self.ground_waste = {}
        self.heatmap = [[0.0] * width for _ in range(height)]

        self.metrics = {
            "waste_into_bins": 0,
            "waste_cleaned": 0,
            "waste_disposed": 0,
        }

        self._scan_layout()
        self._spawn_humans(num_locals)
        self._spawn_tourists(num_tourists)
        self._spawn_cleaners(num_cleaners, cleaner_strategy)
        self._spawn_transporters(num_transporters)

        self.datacollector = mesa.datacollection.DataCollector(
            model_reporters={
                "GroundWaste": lambda m: sum(m.ground_waste.values()),
                "OverflowingBins": lambda m: sum(1 for b in m.bins if b.is_full),
                "AvgBinFill": lambda m: (
                    sum(b.fill_ratio for b in m.bins) / len(m.bins)
                    if m.bins else 0.0
                ),
                "WasteDisposed": lambda m: m.metrics["waste_disposed"],
                "WasteCleaned": lambda m: m.metrics["waste_cleaned"],
                "WasteIntoBins": lambda m: m.metrics["waste_into_bins"],
            }
        )

        self.running = True

    def _scan_layout(self):
        """Walk the parsed grid and instantiate fixed infrastructure."""
        # Start IDs high so they never collide with mobile-agent IDs.
        next_id = 100000

        for y, row in enumerate(self.cell_types):
            for x, ch in enumerate(row):
                if ch == "#":
                    continue
                if ch == "A":
                    self.attractions.append((x, y))
                if ch in ".PABCD":
                    self.walkable_cells.append((x, y))

                if ch == "B":
                    bin_agent = DustBinAgent(next_id, self, config.BIN_CAPACITY, "bin")
                    next_id += 1
                    self.grid.place_agent(bin_agent, (x, y))
                    self.schedule.add(bin_agent)
                    self.bins.append(bin_agent)
                elif ch == "C":
                    cont = DustBinAgent(next_id, self, config.CONTAINER_CAPACITY, "container")
                    next_id += 1
                    self.grid.place_agent(cont, (x, y))
                    self.schedule.add(cont)
                    self.bins.append(cont)
                elif ch == "D":
                    self.disposal_points.append((x, y))

        if not self.disposal_points:
            self.disposal_points.append((0, 0))

    def _spawn_humans(self, n):
        """Create ``n`` locals with random distinct home/work cells."""
        for i in range(n):
            home = self.random.choice(self.walkable_cells)
            work = self.random.choice(self.walkable_cells)
            if home == work:
                work = self.random.choice(self.walkable_cells)
            agent = LocalHumanAgent(i, self, home, work)
            self.grid.place_agent(agent, home)
            self.schedule.add(agent)

    def _spawn_tourists(self, n):
        """Create ``n`` tourists at random walkable cells."""
        offset = config.NUM_LOCALS + 1
        for i in range(n):
            agent = TouristAgent(offset + i, self)
            spawn = self.random.choice(self.walkable_cells)
            self.grid.place_agent(agent, spawn)
            self.schedule.add(agent)

    def _spawn_cleaners(self, n, strategy):
        """Create ``n`` cleaners using the given strategy.

        For ``fixed_route`` we synthesise a simple patrol from bin cells
        so the route has natural waypoints.
        """
        offset = config.NUM_LOCALS + config.NUM_TOURISTS + 1
        fixed_route = [b.pos for b in self.bins[: max(4, len(self.bins) // 2)]]
        for i in range(n):
            agent = CleaningServiceAgent(
                offset + i, self, strategy=strategy, route=fixed_route
            )
            spawn = self.random.choice(self.walkable_cells)
            self.grid.place_agent(agent, spawn)
            self.schedule.add(agent)

    def _spawn_transporters(self, n):
        """Create ``n`` transporters based at the first disposal point."""
        offset = (
            config.NUM_LOCALS + config.NUM_TOURISTS + config.NUM_CLEANERS + 1
        )
        depot = self.disposal_points[0]
        for i in range(n):
            agent = DustTransporterAgent(offset + i, self, depot)
            self.grid.place_agent(agent, depot)
            self.schedule.add(agent)

    def add_ground_waste(self, pos, amount=1):
        """Increment litter at ``pos`` and reinforce the heatmap there."""
        self.ground_waste[pos] = self.ground_waste.get(pos, 0) + amount
        x, y = pos
        self.heatmap[y][x] += config.HEATMAP_INCREMENT

    def heatmap_argmax(self):
        """Return the cell with the highest heatmap value, or ``None``."""
        best_val = 0.0
        best_pos = None
        for y, row in enumerate(self.heatmap):
            for x, v in enumerate(row):
                if v > best_val:
                    best_val = v
                    best_pos = (x, y)
        return best_pos

    def step(self):
        """Advance the simulation by one tick."""
        # Collect first so step 0 records the initial state.
        self.datacollector.collect(self)
        decay = config.HEATMAP_DECAY
        for row in self.heatmap:
            for x in range(len(row)):
                row[x] *= decay
        self.schedule.step()
