"""
visualize.py
------------
Matplotlib-based renderer for the Waste-in-the-City model.

Two entry points:
* ``draw_city(model)`` – static snapshot of the current state.
* ``animate(model, steps)`` – animated simulation that runs the model and
  draws each step using ``matplotlib.animation``.

We avoid Mesa's web-based visualisation server because it changes between
Mesa releases. Matplotlib gives a stable, dependency-light alternative.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation


# Colour mapping for static cell types -> rendered as the background grid.
# Numbers double as integer codes used inside the numpy display array.
CELL_CODE = {
    "#": 0,  # building
    ".": 1,  # street
    "P": 2,  # public area
    "A": 3,  # attraction
    "B": 4,  # bin
    "C": 5,  # container
    "D": 6,  # disposal
}

# Discrete colour palette aligned with the codes above.
CELL_COLOURS = [
    "#3a3a3a",  # building – dark gray
    "#dddddd",  # street – light gray
    "#c5e1a5",  # public area – light green
    "#fff176",  # attraction – yellow
    "#42a5f5",  # bin – blue
    "#1565c0",  # container – dark blue
    "#8d6e63",  # disposal – brown
]


def _cells_to_array(cells):
    """Convert the model's character grid into an int numpy array for imshow."""
    # Building gets code 0 (lowest) so unknown cells default safely to it.
    h = len(cells)
    w = len(cells[0])
    arr = np.zeros((h, w), dtype=int)
    for y, row in enumerate(cells):
        for x, ch in enumerate(row):
            arr[y, x] = CELL_CODE.get(ch, 0)
    return arr


def draw_city(model, ax=None, show_waste=True, show_agents=True):
    """Render the current state of the city on ``ax`` (or a new figure)."""
    # Create our own axes if the caller didn't pass one (handy for one-shot).
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 8))

    # Background = static cells from the layout.
    grid_img = _cells_to_array(model.cell_types)
    cmap = plt.matplotlib.colors.ListedColormap(CELL_COLOURS)
    ax.imshow(grid_img, cmap=cmap, vmin=0, vmax=len(CELL_COLOURS) - 1, origin="upper")

    # Overlay: ground waste as red squares with size proportional to amount.
    if show_waste and model.ground_waste:
        xs = [pos[0] for pos in model.ground_waste]
        ys = [pos[1] for pos in model.ground_waste]
        sizes = [12 * model.ground_waste[p] for p in model.ground_waste]
        ax.scatter(xs, ys, s=sizes, c="red", marker="s", alpha=0.7, label="Waste")

    # Overlay: bin fill levels as a number on top of each bin cell.
    for b in model.bins:
        x, y = b.pos
        ax.text(
            x, y, f"{b.load}",
            ha="center", va="center",
            fontsize=6, color="white", weight="bold",
        )

    # Overlay: mobile agents drawn with distinct markers / colours.
    if show_agents:
        # Import here to avoid circular import at module load time.
        from agents import (
            CleaningServiceAgent,
            DustTransporterAgent,
            LocalHumanAgent,
            TouristAgent,
        )
        groups = {
            LocalHumanAgent: ("o", "#1b5e20", "Local"),
            TouristAgent: ("^", "#ef6c00", "Tourist"),
            CleaningServiceAgent: ("D", "#6a1b9a", "Cleaner"),
            DustTransporterAgent: ("s", "#b71c1c", "Transporter"),
        }
        for cls, (marker, colour, label) in groups.items():
            xs, ys = [], []
            # Walk the schedule to find every mobile agent of this class.
            for ag in model.schedule.agents:
                if isinstance(ag, cls):
                    xs.append(ag.pos[0])
                    ys.append(ag.pos[1])
            if xs:
                ax.scatter(xs, ys, marker=marker, c=colour, s=40, label=label,
                           edgecolors="black", linewidths=0.5)

    # Cosmetic axis tweaks: hide ticks, keep aspect ratio square.
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Step {model.schedule.steps} | Ground waste: {sum(model.ground_waste.values())}")

    # Build a legend for the static cell types so readers can decode colours.
    static_legend = [
        mpatches.Patch(color=CELL_COLOURS[code], label=name)
        for name, code in [
            ("Building", 0), ("Street", 1), ("Public", 2),
            ("Attraction", 3), ("Bin", 4), ("Container", 5), ("Disposal", 6),
        ]
    ]
    ax.legend(handles=static_legend, loc="upper right",
              bbox_to_anchor=(1.32, 1.0), fontsize=7, framealpha=0.9)

    return ax


def animate(model, steps=200, interval_ms=80, save_path=None):
    """Run the model for ``steps`` steps and animate each frame.

    If ``save_path`` is provided, an mp4/gif is written instead of being
    shown interactively. Otherwise a Matplotlib window opens.
    """
    fig, ax = plt.subplots(figsize=(9, 8))

    def update(_frame_idx):
        # Each animation frame: clear the axes, advance the model, redraw.
        ax.clear()
        model.step()
        draw_city(model, ax=ax)
        return ()

    # FuncAnimation drives the simulation. We disable blit because we redraw
    # everything (legends, scatter sizes change between frames).
    anim = FuncAnimation(fig, update, frames=steps, interval=interval_ms, blit=False, repeat=False)

    if save_path:
        # Pillow writer keeps it dependency-light (no ffmpeg requirement).
        anim.save(save_path, writer="pillow", fps=max(1, 1000 // interval_ms))
        plt.close(fig)
    else:
        plt.show()

    return anim


def plot_metrics(model, save_path=None):
    """Plot the time series collected by the model's DataCollector."""
    df = model.datacollector.get_model_vars_dataframe()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))

    # Each subplot focuses on a single research-question metric for clarity.
    df["GroundWaste"].plot(ax=axes[0, 0], title="Total waste on streets", color="red")
    df["OverflowingBins"].plot(ax=axes[0, 1], title="Overflowing bins", color="orange")
    df["AvgBinFill"].plot(ax=axes[1, 0], title="Average bin fill ratio", color="blue")
    # Compare cleaning vs disposal vs into-bin throughput on a single chart.
    df[["WasteCleaned", "WasteDisposed", "WasteIntoBins"]].plot(
        ax=axes[1, 1], title="Waste throughput (cumulative)"
    )

    for ax in axes.flat:
        ax.set_xlabel("Simulation step")
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=120)
        plt.close(fig)
    else:
        plt.show()
    return df
