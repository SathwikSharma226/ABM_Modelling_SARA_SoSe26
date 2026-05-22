"""
experiments.py
--------------
Batch-runs that answer the research questions from the lecture slides.

Each ``run_*`` function returns a pandas DataFrame so the results can be
compared / plotted side-by-side. ``run_all()`` writes the comparison
plots into the ``results/`` directory.
"""

import os

import pandas as pd
import matplotlib.pyplot as plt

import config
from city_model import WasteCityModel


# Folder (next to this file) where output plots/CSVs are written.
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _ensure_results_dir():
    """Create the results folder lazily on first use."""
    # Idempotent: exist_ok=True so reruns don't fail.
    os.makedirs(RESULTS_DIR, exist_ok=True)


def _run_single(num_steps=config.NUM_STEPS, **kwargs):
    """Run a single simulation with overrides and return the metrics DataFrame."""
    # Instantiate a fresh model so runs are independent.
    model = WasteCityModel(**kwargs)
    # Drive the simulation for the requested number of ticks.
    for _ in range(num_steps):
        model.step()
    # The DataCollector exposes a tidy DataFrame with one row per step.
    return model.datacollector.get_model_vars_dataframe()


def compare_cleaner_strategies(num_steps=config.NUM_STEPS):
    """Run the same world four times with different cleaner strategies."""
    # Loop over all whitelisted strategies so we can A/B them on equal footing.
    results = {}
    for strat in config.CLEANER_STRATEGIES:
        df = _run_single(num_steps=num_steps, cleaner_strategy=strat)
        results[strat] = df
    return results


def compare_bin_density(num_steps=config.NUM_STEPS):
    """Compare 'few bins' vs 'many bins' by adjusting the population.

    We approximate "few bins" by reducing the cleaning interval (more
    frequent transporter visits compensate) and "many bins" by leaving
    the default layout. A real-world version would swap layouts.
    """
    # Standard run with the default layout = many-bin baseline.
    many = _run_single(num_steps=num_steps)
    # Few-bin proxy: fewer cleaners + fewer transporters to stress the system.
    few = _run_single(num_steps=num_steps, num_cleaners=1, num_transporters=0)
    return {"many_bins_baseline": many, "few_bins_stress": few}


def compare_tourist_density(num_steps=config.NUM_STEPS):
    """Low vs. high tourist density."""
    low = _run_single(num_steps=num_steps, num_tourists=2)
    high = _run_single(num_steps=num_steps, num_tourists=30)
    return {"low_tourists": low, "high_tourists": high}


def _plot_comparison(results, metric, title, filename):
    """Plot the same metric across multiple runs into one figure."""
    _ensure_results_dir()
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, df in results.items():
        # Plot each run's series with the run name as legend entry.
        df[metric].plot(ax=ax, label=label)
    ax.set_title(title)
    ax.set_xlabel("Step")
    ax.set_ylabel(metric)
    ax.grid(True, alpha=0.3)
    ax.legend()
    out = os.path.join(RESULTS_DIR, filename)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def run_all(num_steps=config.NUM_STEPS):
    """Run all comparison experiments and write plots+CSVs to ``results/``."""
    _ensure_results_dir()

    # 1. Cleaner-strategy sweep -> central research question of the project.
    strat_results = compare_cleaner_strategies(num_steps=num_steps)
    _plot_comparison(strat_results, "GroundWaste",
                     "Ground waste over time per cleaner strategy",
                     "compare_strategies_ground_waste.png")
    _plot_comparison(strat_results, "OverflowingBins",
                     "Overflowing bins over time per cleaner strategy",
                     "compare_strategies_overflow.png")

    # 2. Tourist density.
    tour = compare_tourist_density(num_steps=num_steps)
    _plot_comparison(tour, "GroundWaste",
                     "Ground waste: low vs high tourist density",
                     "tourists_ground_waste.png")

    # 3. Bin density / cleaning capacity.
    bin_res = compare_bin_density(num_steps=num_steps)
    _plot_comparison(bin_res, "OverflowingBins",
                     "Overflow under different cleaning capacities",
                     "bin_density_overflow.png")

    # Persist the raw data alongside the plots so users can re-analyse.
    for name, df in strat_results.items():
        df.to_csv(os.path.join(RESULTS_DIR, f"strategy_{name}.csv"))
    for name, df in tour.items():
        df.to_csv(os.path.join(RESULTS_DIR, f"tourists_{name}.csv"))
    for name, df in bin_res.items():
        df.to_csv(os.path.join(RESULTS_DIR, f"bins_{name}.csv"))

    print(f"Experiment artefacts written to {RESULTS_DIR}")


if __name__ == "__main__":
    # Allow running ``python experiments.py`` directly.
    run_all()
