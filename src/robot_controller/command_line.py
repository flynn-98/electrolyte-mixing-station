import argparse
import json
import sys

from sdlabs_wrapper.wrapper import initialize_optimization

from robot_controller import admiral, hardware_scheduler, pipette_controller

file_path = "data/config/conductivity_optimiser.json"
API_KEY = "eyJhbGciOiJIUzUxMiIsImtpZCI6ImtleV8yOGY0OWNiNDkyNzI0MGJmYjQ4YzQ2MDRlYWY2YzI5ZCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2F1dGguYXRpbmFyeS5jb20iLCJjb2duaXRvOmdyb3VwcyI6WyJhY2FkZW1pYyJdLCJpYXQiOjE3NDEzNTEyODgsIm5iZiI6MTc0MTM1MTI4OCwidXNlcm5hbWUiOiJiYjc2MDk4My1mM2IwLTQ3YTEtOGY3Ny05ZGY0OGFiNjU1ODEifQ.wBEigYeKco5e9gYNT_b17VZRztwLw-no1ae8k3HpG96r06LPSFVIb73VkA1eg2AFjUs_T9vAumhFtXTOzfq5Wg"

def run_campaign() -> None:
    parser=argparse.ArgumentParser(description="Begin or resume an Atinary campaign.")
    parser.add_argument("--device_name", help="Used to locate the device data by matching with Device ID.", type=str)
    parser.add_argument("--resume", default=False, help="Continue from last state. Defaults to false to restart.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--home", default=False, help="Set true to home gantry on start up. Defaults to false.", type=bool, action=argparse.BooleanOptionalAction)

    args=parser.parse_args()

    if args.resume is False:
        device = hardware_scheduler.experiment(device_name=args.device_name, csv_filename="electrolyte_recipe.csv", home=args.home)
    else:
        device = hardware_scheduler.experiment(device_name=args.device_name, csv_filename="current_state.csv", home=args.home)
    
    # load config as dict
    with open(file_path, "rb") as f:
        config_dict = json.load(f)
    wrapper = initialize_optimization(
        api_key=API_KEY,
        spec_file_content=config_dict,
        inherit_data=False, 
    )

    for iteration in range(wrapper.config.budget):

        print("***********************ATINARY***********************")
        print(f"Iteration {iteration+1}: Fetching new suggestions")
        suggestions = wrapper.get_new_suggestions(max_retries=6, sleep_time_s=30)
        print(f"Iteration {iteration+1} New suggestions: {suggestions}")
        print("*****************************************************")

        for suggestion in suggestions:
            # Update csv with new volumes
            device.read_csv()

            # Run experiment here (temperature requried?)
            impedance_results = device.run()

            for i, obj in enumerate(wrapper.config.objectives):
                suggestion.measurements[obj.name] = impedance_results[i] # Send data here

        if suggestions:
            wrapper.send_measurements(suggestions)
            print("***********************ATINARY***********************")
            print(f"Iteration {iteration+1} measurements sent")
            print("*****************************************************")

    device.close_all_ports()
    sys.exit()

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
