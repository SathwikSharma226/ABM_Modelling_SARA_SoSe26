"""
config.py
---------
Central configuration for the "Waste in the City" Agent-Based Model.

All tunable simulation parameters live here so that experiments can be
reproduced and so that students reading the code can quickly see which
"levers" exist in the model.
"""

# ---------------------------------------------------------------------------
# Grid and layout configuration
# ---------------------------------------------------------------------------

# Width of the grid world in cells. Bigger -> richer dynamics, slower runs.
GRID_WIDTH = 30

# Height of the grid world in cells.
GRID_HEIGHT = 30

# Path to the default city layout file. Each character represents one cell.
# Legend used when parsing the layout file (see city_layouts/default.txt):
#   '.' -> street / walkable path
#   '#' -> wall / building (blocks movement)
#   'P' -> public area (waste tends to accumulate here)
#   'B' -> dust bin   (small fixed infrastructure)
#   'C' -> dust container (large fixed infrastructure)
#   'D' -> disposal point at edge of city (transporter destination)
#   'A' -> "attractive" point of interest (tourists gravitate here)
DEFAULT_LAYOUT_FILE = "city_layouts/default.txt"

# ---------------------------------------------------------------------------
# Population / agent counts
# ---------------------------------------------------------------------------

# Number of local human agents that follow regular daily patterns.
NUM_LOCALS = 25

# Number of tourist agents that move less predictably toward attractions.
NUM_TOURISTS = 10

# Number of cleaning-service agents (street cleaners).
NUM_CLEANERS = 3

# Number of dust transporter agents that empty bins/containers.
NUM_TRANSPORTERS = 1

# ---------------------------------------------------------------------------
# Behavioural parameters
# ---------------------------------------------------------------------------

# Probability per step that a local human drops a piece of waste on a
# walkable cell when no nearby bin is available.
LOCAL_WASTE_PROB = 0.05

# Probability per step that a tourist drops waste (higher than locals,
# because tourists are less waste-aware in the model).
TOURIST_WASTE_PROB = 0.15

# Search radius (in Chebyshev / Manhattan steps) within which a human
# will look for a bin before deciding to drop waste on the ground.
HUMAN_BIN_SEARCH_RADIUS = 5

# Capacity of a small dust bin (units of waste). Overflow is counted.
BIN_CAPACITY = 10

# Capacity of a large dust container.
CONTAINER_CAPACITY = 50

# Threshold (fraction of capacity) above which a transporter considers a
# bin "full enough" to be worth visiting.
TRANSPORTER_FULL_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Cleaning strategy options
# ---------------------------------------------------------------------------

# Allowed strategies for the cleaning service. Used by the model to pick
# behaviour at runtime. Documented in agents.CleaningServiceAgent.
CLEANER_STRATEGIES = ("nearest_waste", "random_patrol", "fixed_route", "heatmap")

# Default cleaner strategy if not overridden in an experiment.
DEFAULT_CLEANER_STRATEGY = "nearest_waste"

# ---------------------------------------------------------------------------
# Heatmap (creative extension) parameters
# ---------------------------------------------------------------------------

# Per-step decay factor of the cleaning-heatmap memory. Each step every
# cell value is multiplied by this factor so old hotspots fade.
HEATMAP_DECAY = 0.97

# Amount added to a cell's heatmap value whenever waste is observed there.
HEATMAP_INCREMENT = 1.0

# ---------------------------------------------------------------------------
# Scheduling / simulation control
# ---------------------------------------------------------------------------

# Total number of simulation steps for a single run.
NUM_STEPS = 300

# Random seed for reproducible runs. Set to None for non-deterministic.
RANDOM_SEED = 42

# How often (in steps) a transporter is "scheduled" to leave the depot.
# Larger -> rarer transporter visits.
TRANSPORTER_INTERVAL = 25
