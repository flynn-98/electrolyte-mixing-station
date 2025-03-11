import argparse
import json
import random
import logging
import sys

from sdlabs_wrapper.wrapper import initialize_optimization

from robot_controller import admiral, hardware_scheduler, pipette_controller

config_file = "data/config/conductivity_optimiser.json"
API_KEY = "eyJhbGciOiJIUzUxMiIsImtpZCI6ImtleV9lMmJiY2M4ZWVhMjU0MjU2ODVmZDUzMWE2ZTJmOTE1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2F1dGguYXRpbmFyeS5jb20iLCJjb2duaXRvOmdyb3VwcyI6WyJDQVBlWF9QaW9uZWVyX0NlbnRlciJdLCJpYXQiOjE3NDE3MTE4OTUsIm5iZiI6MTc0MTcxMTg5NSwidXNlcm5hbWUiOiJmMmM2ZDBiYy01OTQ1LTRiM2UtYjA3Mi0yMzc5ZTI1YmI0NjgifQ.caBOaBaSHE-IS-1zgcbGb7jzR05jry_X1i5gArasfSR_k5qy8BDx4tSDz8JTfCXMDMmVtjl4KoNU9LcDykk0HA"

logging.basicConfig(level = logging.INFO)

def run_campaign() -> None:
    parser=argparse.ArgumentParser(description="Begin or resume an Atinary campaign.")
    parser.add_argument("--device", help="Used to locate the device data by matching with Device ID.", type=str)
    parser.add_argument("--resume", default=False, help="Continue from last state. Defaults to false to restart.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--home", default=False, help="Set true to home gantry on start up. Defaults to false.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--sleep", default=30, help="Sleep time (in seconds) between attempts to get new suggestions from Atinary. Defaults to 30s.", type=int)
    parser.add_argument("--temp", default=25, help="Temperature set point for electrolyte analysis. Defaults to 25C.", type=float)
    parser.add_argument("--csv", default="electrolyte_recipe", help="Name of csv file to be updated by Atinary wrapper. Defaults to electrolyte_recipe, or current_state if resume is True.", type=str)

    args=parser.parse_args()

    if args.resume is False:
        device = hardware_scheduler.scheduler(device_name=args.device, csv_filename=args.csv + ".csv", home=args.home)
    else:
        device = hardware_scheduler.scheduler(device_name=args.device, csv_filename="current_state.csv", home=args.home)
    
    # load config as dict
    with open(config_file, "rb") as f:
        config_dict = json.load(f)

    wrapper = initialize_optimization(
        api_key=API_KEY,
        spec_file_content=config_dict,
        inherit_data=False, 
        always_restart=True,
    )

    for iteration in range(wrapper.config.budget):

        logging.info(f"Iteration {iteration+1}: Fetching new suggestions..")
        suggestions = wrapper.get_new_suggestions(max_retries=10, sleep_time_s=args.sleep)

        if not suggestions:
            logging.error(f"No suggestions received on iteration {iteration+1}.")
            sys.exit()

        for suggestion in suggestions:
            logging.info(f"Iteration {iteration+1} New suggestion: {suggestion.param_values}.")

            # Update df with new volumes and save to current state
            # e.g. {'Zn(ClO4)2': 5.0, 'ZnCl2': 5.0} - names must exactly match those in CSV
            device.update_dose_volumes(suggestion.param_values)

            # Run experiment here
            impedance_results = device.run(args.temp)

            # Build table of measurements to send e.g. [conductivity, cost]
            results = [impedance_results[1], device.calculate_cost()]

            for i, obj in enumerate(wrapper.config.objectives):
                # e.g. {'conductivity': 0.06925926902246848, 'cost': 0.9500057653400364}
                suggestion.measurements[obj.name] = results[i] # Send data here

            wrapper.send_measurements(suggestions)
            logging.info(f"Iteration {iteration+1} measurements sent.")

            # Clean test cell whilst optimiser calculates next suggestions
            device.clean()

    device.close_all_ports()
    sys.exit()

def test_atinary() -> None:
    # load config as dict
    with open(config_file, "rb") as f:
        config_dict = json.load(f)
    
    wrapper = initialize_optimization(
        api_key=API_KEY,
        spec_file_content=config_dict,
        inherit_data=False, 
        always_restart=True,
    )

    for iteration in range(wrapper.config.budget):
        print(f"Iteration {iteration+1}: Fetching new suggestions")
        suggestions = wrapper.get_new_suggestions(max_retries=10, sleep_time_s=30)

        print(f"Iteration {iteration+1} New Suggestions: {suggestions}")

        for suggestion in suggestions:
            print(suggestion.param_values)

            for obj in wrapper.config.objectives:
                suggestion.measurements[obj.name] = random.random()

        print(suggestion.measurements)

        if suggestions:
            wrapper.send_measurements(suggestions)
            print(f"Iteration {iteration+1} Measurements sent")

def test_pipette() -> None:
    parser=argparse.ArgumentParser(description="Try out Pipette variables for aspiration and dispense.")
    parser.add_argument("--port", help="Smart Pump Module COM port address.", type=str)

    args=parser.parse_args()

    device = pipette_controller.pipette(COM=args.port) 
    device.aspiration_test()

    sys.exit()

def squidstat_example() -> None:
    parser=argparse.ArgumentParser(description="Run Squidstat experiement and plot results.")
    parser.add_argument("--port", help="Squidstat COM port address.", type=str)
    parser.add_argument("--mode", help="Squidstat analysis mode (0-12)", type=int)

    args=parser.parse_args()

    measurement = admiral.squidstat(COM=args.port)
    measurement.mode = args.mode

    measurement.take_measurements()

    sys.exit()
