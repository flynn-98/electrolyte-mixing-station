import argparse

from robot_controller import experiment_setup


def accelerated_life_test():
    parser=argparse.ArgumentParser(description="Input variables for Accelerated Life Test")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID")
    parser.add_argument("--repeats", default=20, help="Number of experiment repeats, defaults to 20.", type=int)

    args=parser.parse_args()

    experiment = experiment_setup.experiment(device_name=args.device_name, csv_path="data/CSVs/accelerated_life_test.csv")
    experiment.run(args.repeats)

def run_experiment():
    parser=argparse.ArgumentParser(description="Input variables for Experiment")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID")
    parser.add_argument("--repeats", default=1, help="Number of experiment repeats, defaults to 1.", type=int)

    args=parser.parse_args()

    experiment = experiment_setup.experiment(device_name=args.device_name, csv_path="data/CSVs/electrolyte_recipe.csv")
    experiment.run(args.repeats)

def test_pipette():
    parser=argparse.ArgumentParser(description="Input variables for Pipette Test")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID")

    args=parser.parse_args()

    experiment = experiment_setup.experiment(device_name=args.device_name, csv_path=None)
    experiment.aspiration_test()
