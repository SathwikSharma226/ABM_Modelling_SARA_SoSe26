"""Command-line entry point for the Waste-in-the-City simulation.

Examples
--------
    python run.py                                   # default animated run
    python run.py --steps 500 --no-animate          # head-less
    python run.py --save-animation city.gif         # write GIF
    python run.py --strategy heatmap                # creative extension
    python run.py --experiments                     # batch experiments
"""

import argparse

import config
from city_model import WasteCityModel


def parse_args():
    """Define and parse the command-line arguments."""
    parser = argparse.ArgumentParser(description="Waste-in-the-City ABM")
    parser.add_argument("--steps", type=int, default=config.NUM_STEPS,
                        help="Number of simulation steps")
    parser.add_argument("--strategy", choices=config.CLEANER_STRATEGIES,
                        default=config.DEFAULT_CLEANER_STRATEGY,
                        help="Cleaning service strategy")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                        help="Random seed (omit to randomise)")
    parser.add_argument("--locals", type=int, default=config.NUM_LOCALS, dest="num_locals")
    parser.add_argument("--tourists", type=int, default=config.NUM_TOURISTS, dest="num_tourists")
    parser.add_argument("--cleaners", type=int, default=config.NUM_CLEANERS, dest="num_cleaners")
    parser.add_argument("--transporters", type=int, default=config.NUM_TRANSPORTERS,
                        dest="num_transporters")
    parser.add_argument("--no-animate", action="store_true",
                        help="Skip the animation window (head-less run)")
    parser.add_argument("--save-animation", type=str, default=None,
                        help="Write the animation to this .gif path")
    parser.add_argument("--save-metrics", type=str, default=None,
                        help="Write the metrics figure to this path")
    parser.add_argument("--experiments", action="store_true",
                        help="Run the experiment battery and exit")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.experiments:
        # Lazy import keeps the head-less path free of pandas/matplotlib.
        from experiments import run_all
        run_all(num_steps=args.steps)
        return

    model = WasteCityModel(
        num_locals=args.num_locals,
        num_tourists=args.num_tourists,
        num_cleaners=args.num_cleaners,
        num_transporters=args.num_transporters,
        cleaner_strategy=args.strategy,
        seed=args.seed,
    )

    if not args.no_animate or args.save_animation:
        from visualize import animate, plot_metrics
        animate(model, steps=args.steps, save_path=args.save_animation)
        if args.save_metrics:
            plot_metrics(model, save_path=args.save_metrics)
        return

    for _ in range(args.steps):
        model.step()
    if args.save_metrics:
        from visualize import plot_metrics
        plot_metrics(model, save_path=args.save_metrics)
    df = model.datacollector.get_model_vars_dataframe()
    print(df.tail())


if __name__ == "__main__":
    main()
