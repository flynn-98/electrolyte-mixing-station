import argparse

from robot_controller import admiral, pipette_controller, scheduler


def run_experiment() -> None:
    parser=argparse.ArgumentParser(description="Run single experiment.")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID.")
    parser.add_argument("--resume", default=False, help="Continue from last state. Defaults to false to restart.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--home", default=False, help="Set true to home gantry on start up. Defaults to false.", type=bool, action=argparse.BooleanOptionalAction)

    args=parser.parse_args()

    if args.resume is False:
        instance = scheduler.experiment(device_name=args.device_name, csv_filename="electrolyte_recipe.csv", home=args.home)
    else:
        instance = scheduler.experiment(device_name=args.device_name, csv_filename="current_state.csv", home=args.home)
    
    instance.run()

def test_pipette() -> None:
    parser=argparse.ArgumentParser(description="Try out Pipette variables for aspiration and dispense.")
    parser.add_argument("--port", help="Smart Pump Module COM port address.")

    args=parser.parse_args()

    instance = pipette_controller.pipette(COM=args.port) 
    instance.aspiration_test()

def squidstat_example() -> None:
    parser=argparse.ArgumentParser(description="Run Squidstat experiement and plot results.")
    parser.add_argument("--port", help="Squidstat COM port address.")

    args=parser.parse_args()

    measurement = admiral.squidstat(COM=args.port)
    measurement.build_EIS_potentiostatic_experiment()

    measurement.run_experiment()
    ac_data, dc_data = measurement.close_experiment()

    print(ac_data)
    print(dc_data)
