import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation

# mapping opf cell char to int for imshow rendering
CELL_CODE = {
    "#": 0,
    ".": 1,
    "P": 2,
    "A": 3,
    "B": 4,
    "C": 5,
    "D": 6,
}

CELL_COLOURS = [
    "#3a3a3a",  # building
    "#dddddd",  # street
    "#c5e1a5",  # public area
    "#fff176",  # attraction
    "#42a5f5",  # bin
    "#1565c0",  # container
    "#8d6e63",  # disposal
]


def _cells_to_array(cells):
    """Convert the character grid into an int numpy array for imshow."""
    h = len(cells)
    w = len(cells[0])
    arr = np.zeros((h, w), dtype=int)
    for y, row in enumerate(cells):
        for x, ch in enumerate(row):
            arr[y, x] = CELL_CODE.get(ch, 0)
    return arr


def draw_city(model, ax=None, show_waste=True, show_agents=True):
    """Render the current state of the city on ax (or a new figure). 
    Overlays ground waste (red squares scaled by amount), bin loads(numeric label) and mobile agents with distinct markers per type.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 8))

    grid_img = _cells_to_array(model.cell_types)
    cmap = plt.matplotlib.colors.ListedColormap(CELL_COLOURS)
    ax.imshow(grid_img, cmap=cmap, vmin=0, vmax=len(CELL_COLOURS) - 1, origin="upper")

    if show_waste and model.ground_waste:
        xs = [pos[0] for pos in model.ground_waste]
        ys = [pos[1] for pos in model.ground_waste]
        sizes = [12 * model.ground_waste[p] for p in model.ground_waste]
        ax.scatter(xs, ys, s=sizes, c="black", marker="s", alpha=0.7, label="Waste")

    for b in model.bins:
        x, y = b.pos
        ax.text(x, y, f"{b.load}", ha="center", va="center",
                fontsize=6, color="white", weight="bold")

    if show_agents:
        # Local import avoids a circular dependency at module load.
        from agents import (
            CleaningServiceAgent,
            DustTransporterAgent,
            LocalHumanAgent,
            TouristAgent,
        )
        groups = {
            LocalHumanAgent: ("o", "#1b5e20", "Local"),
            TouristAgent: ("^", "red", "Tourist"),
            CleaningServiceAgent: ("D", "#6a1b9a", "Cleaner"),
            DustTransporterAgent: ("s", "white", "Transporter"),
        }
        for cls, (marker, colour, label) in groups.items():
            xs, ys = [], []
            for ag in model.schedule.agents:
                if isinstance(ag, cls):
                    xs.append(ag.pos[0])
                    ys.append(ag.pos[1])
            if xs:
                ax.scatter(xs, ys, marker=marker, c=colour, s=40, label=label,
                           edgecolors="black", linewidths=0.5)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Step {model.schedule.steps} | Ground waste: {sum(model.ground_waste.values())}")

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
    """Animate steps ticks of the model.

    When save_path is given the animation is written using the Pillow
    writer (GIF); otherwise an interactive Matplotlib window opens.
    """
    fig, ax = plt.subplots(figsize=(9, 8))

    def update(_frame_idx):
        ax.clear()
        model.step()
        draw_city(model, ax=ax)
        return ()

    

    # Make the animation slower for easier interpretation
    slow_interval_ms = max(200, interval_ms)  # at least 200ms per frame
    anim = FuncAnimation(fig, update, frames=steps, interval=slow_interval_ms,
                         blit=False, repeat=False)

    if save_path:
        anim.save(save_path, writer="pillow", fps=max(1, 1000 // interval_ms))
        plt.close(fig)
    else:
        plt.show()
    return anim


def plot_metrics(model, save_path=None):
    """Plot the metric time series collected by the model's DataCollector."""
    df = model.datacollector.get_model_vars_dataframe()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))

    df["GroundWaste"].plot(ax=axes[0, 0], title="Total waste on streets", color="red")
    df["OverflowingBins"].plot(ax=axes[0, 1], title="Overflowing bins", color="orange")
    df["AvgBinFill"].plot(ax=axes[1, 0], title="Average bin fill ratio", color="blue")
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
