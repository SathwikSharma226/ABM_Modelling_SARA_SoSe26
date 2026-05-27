"""Central configuration for the Waste-in-the-City ABM.

All tunable simulation parameters are gathered here so experiments are
reproducible and every "lever" of the model is visible in one place.
"""

# Grid / layout
GRID_WIDTH = 30
GRID_HEIGHT = 30
DEFAULT_LAYOUT_FILE = "city_layouts/default.txt"

# Population
NUM_LOCALS = 25
NUM_TOURISTS = 10
NUM_CLEANERS = 3
NUM_TRANSPORTERS = 1

# Behaviour
LOCAL_WASTE_PROB = 0.05
TOURIST_WASTE_PROB = 0.15
HUMAN_BIN_SEARCH_RADIUS = 5
BIN_CAPACITY = 10
CONTAINER_CAPACITY = 50
TRANSPORTER_FULL_THRESHOLD = 0.7

# Cleaning strategies
CLEANER_STRATEGIES = ("nearest_waste", "random_patrol", "fixed_route", "heatmap")
DEFAULT_CLEANER_STRATEGY = "nearest_waste"

# Heatmap (creative extension)
HEATMAP_DECAY = 0.97
HEATMAP_INCREMENT = 1.0

# Scheduling
NUM_STEPS = 300
RANDOM_SEED = 42
TRANSPORTER_INTERVAL = 25
