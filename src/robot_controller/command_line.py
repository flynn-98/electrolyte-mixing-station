import argparse

from robot_controller import mixing_station


def run_experiment() -> None:
    parser=argparse.ArgumentParser(description="Input variables for Experiment")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID")
    parser.add_argument("--repeats", default=1, help="Number of experiment repeats, defaults to 1.", type=int)
    parser.add_argument("--resume", default=False, help="Continue from last state. Defaults to false to restart.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--home", default=False, help="Set true to home gantry on start up. Defaults to false.", type=bool, action=argparse.BooleanOptionalAction)

    args=parser.parse_args()

    if args.resume is False:
        instance = mixing_station.scheduler(device_name=args.device_name, csv_filename="electrolyte_recipe.csv", home=args.home)
    else:
        instance = mixing_station.scheduler(device_name=args.device_name, csv_filename="current_state.csv", home=args.home)
    
    instance.run(args.repeats)

def test_pipette() -> None:
    parser=argparse.ArgumentParser(description="Input variables for Pipette Test")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID")

    args=parser.parse_args()

    instance = mixing_station.scheduler(device_name=args.device_name, csv_filename=None) 
    instance.aspiration_test()
