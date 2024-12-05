import argparse
from robot_controller import experiment_setup

def accelerated_life_test():
    parser=argparse.ArgumentParser(description="Input variables for Accelerated Life Test")
    parser.add_argument("--device_name", help="USB address for Gantry")
    parser.add_argument("--repeats", default=50, help="Number of experiment repeats, defaults to 50.", type=int)

    args=parser.parse_args()

    experiment = experiment_setup.experiment(device_name=args.device_name)
    experiment.read_csv(CSV_PATH="data/CSVs/accelerated_life_test.csv")
    experiment.run(args.repeats)

def run_experiment():
    parser=argparse.ArgumentParser(description="Input variables for Experiment")
    parser.add_argument("--device_name", help="USB address for Gantry")
    parser.add_argument("--repeats", default=1, help="Number of experiment repeats, defaults to 1.", type=int)

    args=parser.parse_args()

    experiment = experiment_setup.experiment(device_name=args.device_name)
    experiment.read_csv(CSV_PATH="data/CSVs/electrolye_recipe.csv")
    experiment.run(args.repeats)
