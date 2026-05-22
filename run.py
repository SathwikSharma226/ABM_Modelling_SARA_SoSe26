"""
run.py
------
Command-line entry point for the simulation.

Examples:
    # Run a default simulation and pop up the live animation window.
    python run.py

    # Run head-less for 500 steps, save metrics plot, no animation.
    python run.py --steps 500 --no-animate --save-metrics metrics.png

    # Save a GIF of the animation instead of opening a window.
    python run.py --save-animation city.gif --steps 200

    # Run all comparison experiments (writes results/ folder).
    python run.py --experiments
"""

import argparse  # standard library CLI parser - no extra dependency

import config
from city_model import WasteCityModel


def parse_args():
    """Define and parse the command-line arguments."""
    parser = argparse.ArgumentParser(description="Waste-in-the-City ABM")
    # Number of simulation ticks for a single run.
    parser.add_argument("--steps", type=int, default=config.NUM_STEPS,
                        help="Number of simulation steps")
    # Cleaner strategy override – mirrors the lecture's experimental sweep.
    parser.add_argument("--strategy", choices=config.CLEANER_STRATEGIES,
                        default=config.DEFAULT_CLEANER_STRATEGY,
                        help="Cleaning service strategy")
    # Random seed override for reproducibility.
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                        help="Random seed (omit to randomise)")
    # Population overrides so users can experiment without editing config.py.
    parser.add_argument("--locals", type=int, default=config.NUM_LOCALS, dest="num_locals")
    parser.add_argument("--tourists", type=int, default=config.NUM_TOURISTS, dest="num_tourists")
    parser.add_argument("--cleaners", type=int, default=config.NUM_CLEANERS, dest="num_cleaners")
    parser.add_argument("--transporters", type=int, default=config.NUM_TRANSPORTERS,
                        dest="num_transporters")
    # Visualisation toggles.
    parser.add_argument("--no-animate", action="store_true",
                        help="Skip the animation window (head-less run)")
    parser.add_argument("--save-animation", type=str, default=None,
                        help="If set, write the animation to this .gif path")
    parser.add_argument("--save-metrics", type=str, default=None,
                        help="If set, write the metrics figure to this path")
    # Convenience flag to run the full experiment battery.
    parser.add_argument("--experiments", action="store_true",
                        help="Run the experiment battery (overrides other flags)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Branch 1: run the experiment battery and exit.
    if args.experiments:
        # Imported lazily so head-less runs don't always pull pandas/plt.
        from experiments import run_all
        run_all(num_steps=args.steps)
        return

    # Branch 2: build a single model based on CLI overrides.
    model = WasteCityModel(
        num_locals=args.num_locals,
        num_tourists=args.num_tourists,
        num_cleaners=args.num_cleaners,
        num_transporters=args.num_transporters,
        cleaner_strategy=args.strategy,
        seed=args.seed,
    )

    # Branch 2a: animated run (default for interactive sessions).
    if not args.no_animate or args.save_animation:
        from visualize import animate, plot_metrics
        animate(model, steps=args.steps, save_path=args.save_animation)
        # After the animation finishes the model contains all the data.
        if args.save_metrics:
            plot_metrics(model, save_path=args.save_metrics)
        return

    # Branch 2b: pure head-less mode (just step the model and dump metrics).
    for _ in range(args.steps):
        model.step()
    if args.save_metrics:
        from visualize import plot_metrics
        plot_metrics(model, save_path=args.save_metrics)
    # Print a short summary so CLI users see *something* even without plots.
    df = model.datacollector.get_model_vars_dataframe()
    print(df.tail())


if __name__ == "__main__":
    main()
