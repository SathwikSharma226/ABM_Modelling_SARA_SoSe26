"""
city_model.py
-------------
The Mesa ``Model`` class that ties everything together.

Responsibilities:
* Parse the ASCII city layout into a 2D character grid.
* Place fixed infrastructure (bins, containers, disposal point).
* Spawn the desired population of locals, tourists, cleaners and a transporter.
* Track simulation-wide state (ground waste, heatmap, metrics).
* Drive the per-step update via Mesa's scheduler and DataCollector.
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


# ---------------------------------------------------------------------------
# Layout parsing
# ---------------------------------------------------------------------------

def load_layout(path):
    """Read an ASCII layout file and return (grid, width, height).

    The grid is returned as a list of strings (rows), one row per line of
    the file. Trailing newlines are stripped, but inner whitespace is kept.
    """
    # Open the file with utf-8 to support any future unicode characters.
    with open(path, "r", encoding="utf-8") as f:
        # Strip the newline of every line so we can index by [y][x] cleanly.
        rows = [line.rstrip("\n") for line in f if line.strip()]
    height = len(rows)
    # Width is the maximum line length – pad shorter lines with buildings ('#').
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, "#") for r in rows]
    return rows, width, height


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

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
        # Initialise the Mesa base class; passing the seed makes runs reproducible.
        super().__init__()
        self._seed_value = seed
        if seed is not None:
            self.random.seed(seed)

        # Resolve the layout path relative to this file so working directory
        # doesn't break the import (important when running from a notebook).
        base_dir = os.path.dirname(os.path.abspath(__file__))
        layout_path = layout_file
        if not os.path.isabs(layout_path):
            layout_path = os.path.join(base_dir, layout_file)

        # Parse layout into a row-major character grid + dimensions.
        self.cell_types, width, height = load_layout(layout_path)

        # Mesa space: MultiGrid lets multiple agents share a single cell
        # (e.g. a cleaner standing next to a bin) and supports torus=False so
        # the city has hard borders.
        self.grid = mesa.space.MultiGrid(width, height, torus=False)

        # Random activation = each step every agent acts once in random order.
        self.schedule = mesa.time.RandomActivation(self)

        # Bookkeeping containers populated below.
        self.bins = []                    # all DustBinAgent instances
        self.attractions = []             # 'A' cells used by tourists
        self.walkable_cells = []          # cells humans/tourists can spawn on
        self.disposal_points = []         # 'D' cells (transporter target)
        self.ground_waste = {}            # pos -> int amount of litter
        self.heatmap = [[0.0] * width for _ in range(height)]  # creative ext.

        # Per-run aggregate counters (saved in DataCollector each step).
        self.metrics = {
            "waste_into_bins": 0,
            "waste_cleaned": 0,
            "waste_disposed": 0,
        }

        # Place the static infrastructure & remember walkable / attraction cells.
        self._scan_layout()

        # Spawn mobile agents according to the requested population mix.
        self._spawn_humans(num_locals)
        self._spawn_tourists(num_tourists)
        self._spawn_cleaners(num_cleaners, cleaner_strategy)
        self._spawn_transporters(num_transporters)

        # DataCollector: lambda accessors keep the model the single source of truth.
        # Each value is sampled once per step and stored for later plotting.
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

        # Convenience: keep the running flag so external loops can stop early.
        self.running = True

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _scan_layout(self):
        """Walk the parsed grid and instantiate fixed infrastructure."""
        # ``unique_id`` namespace: start high so we never clash with mobile agents.
        next_id = 100000

        for y, row in enumerate(self.cell_types):
            for x, ch in enumerate(row):
                if ch == "#":
                    # Building – not walkable, no agent placed.
                    continue
                # Track attractions and walkable cells for later use.
                if ch == "A":
                    self.attractions.append((x, y))
                if ch in ".PABCD":
                    self.walkable_cells.append((x, y))

                if ch == "B":
                    # Small dust bin agent placed on the cell.
                    bin_agent = DustBinAgent(next_id, self, config.BIN_CAPACITY, "bin")
                    next_id += 1
                    self.grid.place_agent(bin_agent, (x, y))
                    self.schedule.add(bin_agent)
                    self.bins.append(bin_agent)
                elif ch == "C":
                    # Larger container.
                    cont = DustBinAgent(next_id, self, config.CONTAINER_CAPACITY, "container")
                    next_id += 1
                    self.grid.place_agent(cont, (x, y))
                    self.schedule.add(cont)
                    self.bins.append(cont)
                elif ch == "D":
                    # Disposal points – just remember coordinates.
                    self.disposal_points.append((x, y))

        # Guarantee at least one disposal point – fall back to (0, 0) if missing.
        if not self.disposal_points:
            self.disposal_points.append((0, 0))

    def _spawn_humans(self, n):
        """Create ``n`` LocalHumanAgent instances with random home/work pairs."""
        for i in range(n):
            # Pick two distinct walkable cells as the human's home and work.
            home = self.random.choice(self.walkable_cells)
            work = self.random.choice(self.walkable_cells)
            # Re-roll once if home == work to give every human a real commute.
            if home == work:
                work = self.random.choice(self.walkable_cells)
            agent = LocalHumanAgent(i, self, home, work)
            # Spawn at home so the daily pattern starts cleanly.
            self.grid.place_agent(agent, home)
            self.schedule.add(agent)

    def _spawn_tourists(self, n):
        """Create ``n`` TouristAgent instances at random walkable cells."""
        # Use an offset so unique_ids never clash with locals.
        offset = config.NUM_LOCALS + 1
        for i in range(n):
            agent = TouristAgent(offset + i, self)
            spawn = self.random.choice(self.walkable_cells)
            self.grid.place_agent(agent, spawn)
            self.schedule.add(agent)

    def _spawn_cleaners(self, n, strategy):
        """Create ``n`` cleaners. For 'fixed_route', generate a perimeter route."""
        offset = config.NUM_LOCALS + config.NUM_TOURISTS + 1
        # Pre-compute a simple fixed route from key intersections (for variety).
        # Use bin cells as natural waypoints on the patrol.
        fixed_route = [b.pos for b in self.bins[: max(4, len(self.bins) // 2)]]

        for i in range(n):
            agent = CleaningServiceAgent(
                offset + i, self, strategy=strategy, route=fixed_route
            )
            spawn = self.random.choice(self.walkable_cells)
            self.grid.place_agent(agent, spawn)
            self.schedule.add(agent)

    def _spawn_transporters(self, n):
        """Create ``n`` transporters that base out of the first disposal point."""
        offset = (
            config.NUM_LOCALS + config.NUM_TOURISTS + config.NUM_CLEANERS + 1
        )
        depot = self.disposal_points[0]
        for i in range(n):
            agent = DustTransporterAgent(offset + i, self, depot)
            self.grid.place_agent(agent, depot)
            self.schedule.add(agent)

    # ------------------------------------------------------------------
    # Public helpers used by agents
    # ------------------------------------------------------------------

    def add_ground_waste(self, pos, amount=1):
        """Increment the litter count at ``pos`` and update the heatmap."""
        # Mutating the dict in-place is fine because Mesa runs single-threaded.
        self.ground_waste[pos] = self.ground_waste.get(pos, 0) + amount
        # Reinforce the heatmap so cleaners can detect this hotspot.
        x, y = pos
        self.heatmap[y][x] += config.HEATMAP_INCREMENT

    def heatmap_argmax(self):
        """Return the cell with the highest heatmap value (or None if empty)."""
        # Linear scan is fine for the grid sizes used in class.
        best_val = 0.0
        best_pos = None
        for y, row in enumerate(self.heatmap):
            for x, v in enumerate(row):
                if v > best_val:
                    best_val = v
                    best_pos = (x, y)
        return best_pos

    # ------------------------------------------------------------------
    # Per-step update
    # ------------------------------------------------------------------

    def step(self):
        """Advance the simulation by one tick."""
        # 1. Sample all reporters BEFORE agents act so step 0 reflects init state.
        self.datacollector.collect(self)
        # 2. Decay the heatmap so old hotspots fade -> creative extension.
        decay = config.HEATMAP_DECAY
        for row in self.heatmap:
            for x in range(len(row)):
                row[x] *= decay
        # 3. Activate all agents (random order).
        self.schedule.step()
