import os
import matplotlib.pyplot as plt
import config
from city_model import WasteCityModel


RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def _run_single(num_steps=config.NUM_STEPS, **kwargs):
    """Run a single simulation and return its metrics DataFrame."""
    model = WasteCityModel(**kwargs)
    for _ in range(num_steps):
        model.step()
    return model.datacollector.get_model_vars_dataframe()


def compare_cleaner_strategies(num_steps=config.NUM_STEPS):
    """Run the same world once per cleaner strategy in ``CLEANER_STRATEGIES``."""
    return {
        strat: _run_single(num_steps=num_steps, cleaner_strategy=strat)
        for strat in config.CLEANER_STRATEGIES
    }


def compare_bin_density(num_steps=config.NUM_STEPS):
    """Compare a baseline run against a stressed cleaning capacity.

    The "few bins" scenario is approximated by reducing cleaner and
    transporter counts so the system gets visibly strained.
    """
    many = _run_single(num_steps=num_steps)
    few = _run_single(num_steps=num_steps, num_cleaners=1, num_transporters=0)
    return {"many_bins_baseline": many, "few_bins_stress": few}


def compare_tourist_density(num_steps=config.NUM_STEPS):
    """Compare runs with low vs. high tourist density."""
    low = _run_single(num_steps=num_steps, num_tourists=2)
    high = _run_single(num_steps=num_steps, num_tourists=30)
    return {"low_tourists": low, "high_tourists": high}


def _plot_comparison(results, metric, title, filename):
    """Plot ``metric`` across all runs in ``results`` into one figure."""
    _ensure_results_dir()
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, df in results.items():
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
    """Run all comparison experiments and persist plots + CSVs."""
    _ensure_results_dir()

    strat_results = compare_cleaner_strategies(num_steps=num_steps)
    _plot_comparison(strat_results, "GroundWaste",
                     "Ground waste over time per cleaner strategy",
                     "compare_strategies_ground_waste.png")
    _plot_comparison(strat_results, "OverflowingBins",
                     "Overflowing bins over time per cleaner strategy",
                     "compare_strategies_overflow.png")

    tour = compare_tourist_density(num_steps=num_steps)
    _plot_comparison(tour, "GroundWaste",
                     "Ground waste: low vs high tourist density",
                     "tourists_ground_waste.png")

    bin_res = compare_bin_density(num_steps=num_steps)
    _plot_comparison(bin_res, "OverflowingBins",
                     "Overflow under different cleaning capacities",
                     "bin_density_overflow.png")

    for name, df in strat_results.items():
        df.to_csv(os.path.join(RESULTS_DIR, f"strategy_{name}.csv"))
    for name, df in tour.items():
        df.to_csv(os.path.join(RESULTS_DIR, f"tourists_{name}.csv"))
    for name, df in bin_res.items():
        df.to_csv(os.path.join(RESULTS_DIR, f"bins_{name}.csv"))

    print(f"Experiment artefacts written to {RESULTS_DIR}")


if __name__ == "__main__":
    run_all()
