import argparse
import config
from city_model import WasteCityModel


def parse_args():
    """Define and parse the command-line arguments."""
    parser = argparse.ArgumentParser(description="Waste-in-the-City ABM")
    parser.add_argument("--strategy", choices=config.CLEANER_STRATEGIES,
                        default=config.DEFAULT_CLEANER_STRATEGY,
                        help="Cleaning service strategy")
    parser.add_argument("--experiments", action="store_true",
                        help="Run the experiment battery and exit")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.experiments:
        from experiments import run_all
        run_all()
        return

    from city_model import WasteCityModel
    import config
    model = WasteCityModel(
        num_locals=config.NUM_LOCALS,
        num_tourists=config.NUM_TOURISTS,
        num_cleaners=config.NUM_CLEANERS,
        num_transporters=config.NUM_TRANSPORTERS,
        cleaner_strategy=args.strategy,
        seed=config.RANDOM_SEED,
    )

    from visualize import animate, plot_metrics
    animate(model, steps=config.NUM_STEPS)
    # Save metrics plot and CSV automatically
    import os
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    metrics_plot_path = os.path.join(results_dir, "metrics.png")
    metrics_csv_path = os.path.join(results_dir, "metrics.csv")
    df = plot_metrics(model, save_path=metrics_plot_path)
    df.to_csv(metrics_csv_path)
    print(f"Metrics plot saved to {metrics_plot_path}\nMetrics CSV saved to {metrics_csv_path}")


if __name__ == "__main__":
    main()
