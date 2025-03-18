import argparse
import json
import logging
import random
import sys

from sdlabs_wrapper.wrapper import initialize_optimization

from robot_controller import admiral, hardware_scheduler, pipette_controller

#config_file = "data/config/conductivity_optimiser.json"
config_file = "data/config/integration_test.json"

API_KEY = "eyJhbGciOiJIUzUxMiIsImtpZCI6ImtleV9lMmJiY2M4ZWVhMjU0MjU2ODVmZDUzMWE2ZTJmOTE1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2F1dGguYXRpbmFyeS5jb20iLCJjb2duaXRvOmdyb3VwcyI6WyJDQVBlWF9QaW9uZWVyX0NlbnRlciJdLCJpYXQiOjE3NDE3MTE4OTUsIm5iZiI6MTc0MTcxMTg5NSwidXNlcm5hbWUiOiJmMmM2ZDBiYy01OTQ1LTRiM2UtYjA3Mi0yMzc5ZTI1YmI0NjgifQ.caBOaBaSHE-IS-1zgcbGb7jzR05jry_X1i5gArasfSR_k5qy8BDx4tSDz8JTfCXMDMmVtjl4KoNU9LcDykk0HA"

logging.basicConfig(level = logging.INFO)

def run_campaign() -> None:
    parser=argparse.ArgumentParser(description="Begin or resume an Atinary campaign.")
    parser.add_argument("--device", help="Used to locate the device data by matching with Device ID.", type=str)
    parser.add_argument("--resume", default=False, help="Continue from saved state. Defaults to false to restart.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--home", default=False, help="Set true to home gantry on start up. Defaults to false.", type=bool, action=argparse.BooleanOptionalAction)
    parser.add_argument("--sleep", default=30, help="Sleep time (in seconds) between attempts to get new suggestions from Atinary. Defaults to 30s.", type=int)
    parser.add_argument("--temp", default=25, help="Temperature set point for electrolyte analysis. Defaults to 25C.", type=float)

    args=parser.parse_args()

    device = hardware_scheduler.scheduler(device_name=args.device, resume=args.resume, home=args.home)
    
    # load config as dict
    with open(config_file, "rb") as f:
        config_dict = json.load(f)

    wrapper = initialize_optimization(
        api_key=API_KEY,
        spec_file_content=config_dict,
        inherit_data=False, 
        always_restart=not args.resume,
    )

    for iteration in range(wrapper.config.budget):

        logging.info(f"Iteration {iteration+1}: Fetching new suggestions..")

        # Atinary will return suggestions until measurements received - useful in case of resume
        suggestions = wrapper.get_new_suggestions(max_retries=10, sleep_time_s=args.sleep)

        if not suggestions:
            logging.error(f"No suggestions received on iteration {iteration+1}.")
            sys.exit()

        for suggestion in suggestions:
            logging.info(f"New suggestion received for iteration {iteration+1}: {suggestion.param_values}.")

            # Get required temperature either from parser or optimiser
            target_temp = extract_temperature(suggestion.param_values)
            
            if target_temp is None:
                target_temp = args.temp

            # Update csv from suggestions
            device.update_dose_volumes(suggestion.param_values)
            
            # Calculate cost of new mixture
            cost = device.calculate_cost()

            # Set temperature early on to reduce effective time to reach
            device.test_cell.peltier.set_temperature(target_temp)

            # Synthesise and analyse at target_temp
            device.synthesise()
            impedance_results = device.analyse(target_temp)

            # Build table of measurements to send e.g. [conductivity, cost]
            results = [impedance_results[1], cost]

            for i, obj in enumerate(wrapper.config.objectives):
                # e.g. {'conductivity': 0.06925926902246848, 'cost': 0.9500057653400364}
                suggestion.measurements[obj.name] = results[i] # Send data here

            wrapper.send_measurements(suggestions)
            logging.info(f"Iteration {iteration+1} measurements sent.")

            # Clean test cell whilst optimiser calculates next suggestions
            device.clean()

    device.close_all_ports()
    sys.exit()

def extract_temperature(values: dict) -> float | None:
    for name in values:
        # Loop through all and check if Temperature
        if name == "Temperature":
            new_value = values[name]
            logging.info(f"New temperature found in received suggestions: {new_value}C.")
            return new_value

    return None

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
