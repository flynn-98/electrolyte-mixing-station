import argparse
from robot_controller import experiment_setup

def run_test():
    parser=argparse.ArgumentParser(description="Input variables for Accelerated Life Test")
    parser.add_argument("--gantry", help="USB address for Gantry")
    parser.add_argument("--pipette", help="USB address for Pipette")
    parser.add_argument("--repeats", default=50, help="Number of experiment repeats, defaults to 50.", type=int)
    parser.add_argument("--gantry_sim", action="store_true", default=False, help="Turn on to simulate communication with Gantry.")
    parser.add_argument("--pipette_sim", action="store_true", default=False, help="Turn on to simulate communication with Pipette.")

    args=parser.parse_args()

    experiment = experiment_setup.experiment(GANTRY_COM=args.gantry, PIPETTE_COM=args.pipette, GANTRY_SIM=args.gantry_sim, PIPETTE_SIM=args.pipette_sim)
    experiment.read_csv(CSV_PATH="data/CSVs/accelerated_life_test.csv")
    experiment.run(args.repeats)
