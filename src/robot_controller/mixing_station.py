import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display

from robot_controller import fluid_controller, gantry_controller, mass_balance, pipette_controller

# Save logs to file
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO,
                    force=True,
                    handlers=[logging.FileHandler("mixing_station.log", mode="a"), logging.StreamHandler(sys.stdout)])

class scheduler:
    def __init__(self, device_name: str, csv_filename: str | None = None, home: bool = True) -> None:
        # Read device data JSON
        self.json_file = "data/devices/mixing_stations.json"
        device_data = self.read_json(device_name)

        # Only record mass balance readings if Pipette active
        self.SIM = not device_data["Pipette_Active"]

        # Establish serial connections
        self.gantry = gantry_controller.gantry(device_data["Gantry_Address"], not device_data["Gantry_Active"])            
        self.pipette = pipette_controller.pipette(device_data["Pipette_Address"], self.SIM)
        self.fluid_handler = fluid_controller.fluid_handler(device_data["Fluid_Address"], not device_data["Fluid_Active"])
        self.mass_balance = mass_balance.mass_reader(device_data["Mass_Address"], not device_data["Mass_Active"])

        # Pot locations 1 -> 10 (mm), pot 10 is for washing
        self.pot_locations = [[41, 0], [75, 0], 
                              [109, 0], [143, 0], 
                              [58, 34], [92, 34], 
                              [126, 34], [75,68], 
                              [109, 68], [143, 68]
                            ]
        
        # Pipette locations 1 -> 9 (mm)
        pipette_x_location = 15 #mm
        self.pipette_locations = [[pipette_x_location, 135], [pipette_x_location, 119], 
                              [pipette_x_location, 103], [pipette_x_location, 87], 
                              [pipette_x_location, 71], [pipette_x_location, 55], 
                              [pipette_x_location, 39], [pipette_x_location,23], 
                              [pipette_x_location, 7]
                            ]
        self.pipette_pick_height = -48 #mm from CAD - to be tuned
        self.pipette_lead_in = 12.5 #mm to position pipette to the right of rack when returning pipette (avoid clash)
        start_x_location = pipette_x_location + self.pipette_lead_in # to avoid pipette rack clash

        # File to store last known active pipette for recovery
        self.pipette_file = "data/variables/active_pipette.txt" # 1-9, 0 = not active        
        
        self.pot_base_height = -69.5 # CAD value (minus a little to ensure submersion)
        self.pot_area = math.pi * 2.78**2 / 4 #cm2

        self.chamber_location = [125, 97.7] # mm
        self.dispense_height = -10 #mm

        # Mass balance checks
        self.max_mass_error = 0.2 # grams, error if exceeded

        # Declare variables for CSV read
        self.df = pd.DataFrame()
        self.csv_path = "data/CSVs"
        self.csv_filename = csv_filename

        # Retrieve any requried variables from controllers
        self.max_dose = self.pipette.get_max_dose()
        self.charge_pressure = self.pipette.get_charge_pressure()
        self.location_file = self.gantry.get_file() # For pipette number recovery

        # Convert CSV file to df
        if self.csv_filename is not None:
            self.read_csv()

        # Send recovery msg to gantry (will correct if power off event)
        if os.path.exists(self.location_file):
            with open(self.location_file, 'r') as filehandler:
                xyz = filehandler.read()

            self.gantry.recover(xyz)

        # Home if requested (will also happen during recovery)
        if home is True:
            self.gantry.softHome()

        # Move to start/end position
        self.gantry.move(start_x_location, 0, 0)

        # Check if pipette is active, return if so.
        if os.path.exists(self.pipette_file):
            with open(self.pipette_file, 'r') as filehandler:
                active_pipette = int(filehandler.read())

            if active_pipette != 0:
                self.return_pipette()

    def read_json(self, device_name: str) -> dict:
        with open(self.json_file) as json_data:
            device_data = json.load(json_data)

        for i, device in enumerate(device_data["Mixing Stations"]):
            if device['ID'] == device_name:
                index = i 
                logging.info("Located device data for " + device_name + ".")

                return device_data["Mixing Stations"][index]

        logging.error("Device data for " + device_name + " could not be located.")
        sys.exit()

    def show_df(self) -> None:
        display(self.df.to_string(index=False))

    def read_csv(self) -> None:
        # Open CSV as dataframe
        logging.info("Reading CSV file..")
        csv_location = os.path.join(self.csv_path, self.csv_filename)

        # Using dictionary to convert specific columns
        df_columns = {  '#': int,
                        'Name': str,
                        'Dose Volume (uL)': float,
                        'Container Volume (mL)': float,
                        'Density (g/mL)': float,
                        'Aspirate Constant (mbar/uL)': float,
                        'Aspirate Speed (uL/s)': float,
                    }
        
        self.df = pd.read_csv(csv_location, header=0, names=df_columns.keys(), index_col=False).astype(df_columns)
        self.df.set_index("#")
        #self.show_df()

        logging.info(f'Recipe will result in a total electrolyte volume of {self.df["Dose Volume (uL)"].sum()/1000}mL.')
        
        now = datetime.now()
        logging.info("Experiment ready to begin: " + now.strftime("%d/%m/%Y %H:%M:%S"))

    def save_csv(self, filename: str = "current_state.csv") -> None:
        logging.info("Saving volume changes to CSV.")
        self.df.to_csv(os.path.join(self.csv_path, filename), index=False)

    def update_dose_volumes(self) -> None:
        # Place holder for API integration
        for i in self.df.index.to_numpy(dtype=int):
            vol = input("Input new Dose Volume (uL) for " + self.df.loc[i, "Name"] + ": ")
            
            self.df.loc[i, "Dose Volume (uL)"] = vol
            logging.info(self.df.loc[i, "Name"] + f" Dose Volume updated to {vol}uL")

        self.save_csv()

    def pick_pipette(self, pipette_no: int) -> None:
        # Turn pump off just in case
        self.pipette.pump_off(check=False)

        x, y = self.pipette_locations[pipette_no-1][0], self.pipette_locations[pipette_no-1][1]

        # Move above pipette rack
        logging.info(f"Moving to Pipette #{pipette_no}..")
        self.gantry.move(x + self.pipette_lead_in, y, 0)
        self.gantry.move(x, y, 0)

        # Move into pipette rack
        logging.info("Dropping to collect pipette..")
        self.gantry.move(x, y, self.pipette_pick_height)

        # Move into pipette rack
        logging.info(f"Raising Pipette #{pipette_no}..")
        self.gantry.move(x, y, 0)

        # Move into pipette rack
        logging.info("Moving away from pipette rack..")
        self.gantry.move(x + self.pipette_lead_in, y, 0)

        # Update active pipette variable 
        with open(self.pipette_file, 'w') as filehandler:
                filehandler.write(f"{pipette_no}")

    def return_pipette(self) -> None:
        # Turn pump off just in case
        self.pipette.pump_off(check=False)

        # Return active pipette
        file_exists = os.path.exists(self.pipette_file)
        if file_exists:
            with open(self.pipette_file, 'r') as filehandler:
                active_pipette = int(filehandler.read())
        
        if active_pipette == 0 or not file_exists:
            logging.error("Return pipette requested whilst no pipette is active.")
            return

        x, y = self.pipette_locations[active_pipette-1][0], self.pipette_locations[active_pipette-1][1]

        # Move above pipette rack (first to lead in location to avoid clash)
        logging.info(f"Moving to Pipette #{active_pipette}..")
        self.gantry.move(x + self.pipette_lead_in, y, 0)
        self.gantry.move(x, y, 0)

        # Move into pipette rack
        logging.info(f"Delivering Pipette #{active_pipette} to rack..")
        self.gantry.move(x, y, self.pipette_pick_height)

        # Move into pipette rack
        self.gantry.pinch()
        logging.info("Pipette ready for removal..")

        # Move above pipette rack
        logging.info("Raising pipette module..")
        self.gantry.move(x, y, 0)
        self.gantry.release()

        with open(self.pipette_file, 'w') as filehandler:
                filehandler.write("0")
    
    def aspiration_test(self) -> None:
        # Used for testing only => No logging

        try:
            charge_pressure = float(input("Enter charge pressure (mbar): "))
        except Exception as ex:
            charge_pressure = self.charge_pressure
            print(ex)
            print(f"Charge Pressure set to {charge_pressure}mbar.")

        # Charge pipette
        self.pipette.pump_on()
        self.pipette.set_pressure(charge_pressure, check=True)
        print("Pipette charged.")

        try:
            aspirate_volume = float(input("Enter Aspirate Volume (uL): "))
        except Exception as ex:
            aspirate_volume = 10
            print(ex)
            print(f"Aspirate Volume set to {aspirate_volume}uL.")

        try:
            aspirate_constant = float(input("Enter Aspirate Constant (mbar/uL): "))
        except Exception as ex:
            aspirate_constant = 0.5
            print(ex)
            print(f"Aspirate Constant set to {aspirate_constant}mbar/uL.")

        try:
            aspirate_speed = float(input("Enter Aspirate Speed (uL/s): "))
        except Exception as ex:
            aspirate_speed = 10
            print(ex)
            print(f"Aspirate Speed set to {aspirate_speed}uL/s.")

        # Aspirate pipette
        self.pipette.aspirate(aspirate_volume, aspirate_constant, aspirate_speed, poly=False, check=True)

        print("Aspiration complete.")
        print(f"{aspirate_volume}uL extracted.")

        _ = input("Press any key to Dispense")

         # Dispense pipette
        self.pipette.dispense()
        print("Dispense complete.")

        self.pipette.close_ser()

    def collect_volume(self, aspirate_volume: float, starting_volume: float, name: str, pot_no: int, aspirate_constant: float, aspirate_speed: float) -> float:
        new_volume = round(starting_volume - aspirate_volume * 1e-3, 4) #ml

        x, y = self.pot_locations[pot_no-1][0], self.pot_locations[pot_no-1][1]

        # Move above pot
        logging.info("Moving to " + name + "..")
        self.gantry.move(x, y, 0)

        # Charge pipette
        self.pipette.pump_on()
        self.pipette.charge_pipette()
        logging.info("Pipette charged.")

        # Drop into fluid (based on starting volume)
        z = self.pot_base_height + 10 * new_volume / self.pot_area

        logging.info(f"Dropping Pipette to {z}mm..")
        self.gantry.move(x, y, z)

        # Aspirate pipette
        self.pipette.aspirate(aspirate_volume, aspirate_constant, aspirate_speed, poly=False, check=True)

        logging.info("Aspiration complete.")
        logging.info(f"{aspirate_volume}uL extracted, {new_volume}mL remaining..")

        # Move out of fluid
        logging.info("Lifting Pipette..")
        self.gantry.move(x, y, 0)
        
        return new_volume
    
    def deliver_volume(self) -> None:
        x, y = self.chamber_location[0], self.chamber_location[1]

        logging.info("Moving to Mixing Chamber..")
        self.gantry.move(x, y, 0)
        
        logging.info(f"Dropping Pipette to {self.dispense_height}mm..")
        self.gantry.move(x, y, self.dispense_height)

        # Dispense pipette
        self.pipette.dispense()
        logging.info("Dispense complete.")

        logging.info("Lifting Pipette..")
        self.gantry.move(x, y, 0)

    def check_mass_change(self, expected_mass: float, starting_mass: float) -> None:
        mass_change = self.mass_balance.get_mass() - starting_mass
        error = mass_change - expected_mass

        if abs(error) > self.max_mass_error:
            logging.error(f"Mass balance detected {mass_change}g added to Test Cell ({error}g error).")
        else:
            logging.info(f"Mass balance detected {mass_change}g added to Test Cell ({error}g error).")

    def run(self, N: int = 1) -> None:
        for n in range(N):
            logging.info(f"Creating electrolyte mixture #{n+1}..")

            try:
                non_zero = self.df[self.df["Dose Volume (uL)"] > 0]
            except Exception as ex:
                logging.error(ex + ": No CSV loaded.")
                sys.exit()
            
            # Loop through all non zero constituents
            for i in non_zero.index.to_numpy(dtype=int):
                # Collect pipette for desired chemical (pipette 1 for pot 1)
                self.pick_pipette(i+1)
    
                # Extract relevant df row
                relevant_row = non_zero.loc[i]
                required_volume = relevant_row["Dose Volume (uL)"]
                
                doses = math.floor(required_volume // self.max_dose) + 1
                last_dose = required_volume % self.max_dose

                # Extract starting volume in pot
                pot_volume = relevant_row["Container Volume (mL)"]

                # If larger than maximum required, perform multiple collections and deliveries until entire volume is transferred
                for j in range(doses):
                    if j == doses-1:
                        dose = last_dose
                    else:
                        dose = self.max_dose

                    # Aspirate using data from relevant df row, increment pot co ordinates
                    pot_volume = self.collect_volume(dose, pot_volume, relevant_row["Name"], i+1, relevant_row["Aspirate Constant (mbar/uL)"], relevant_row["Aspirate Speed (uL/s)"])

                    # Move to mixing chamber and dispense
                    self.deliver_volume()

                    # Set new starting volume for next repeat
                    self.df.loc[i, "Container Volume (mL)"] = pot_volume

                    # Save csv in current state (starting volumes up to date in case of unexpected interruption)
                    self.save_csv()

                # Return pipette
                self.return_pipette()

            # Trigger servo to mix electrolyte
            self.gantry.mix()

            # Let mixture settle
            time.sleep(1)

            # Take mass balance reading
            starting_mass = self.mass_balance.get_mass()

            # Pump electrolyte to next stage
            total_vol = self.df["Dose Volume (uL)"].sum()/1000
            self.fluid_handler.add_electrolyte(total_vol)

            # Mass Balance checks
            self.df["Temp Mass Values (1e3*g)"] =  self.df["Density (g/mL)"] * self.df["Dose Volume (uL)"]
            total_mass = self.df["Temp Mass Values (1e3*g)"].sum()/1000
            self.df = self.df.drop("Temp Mass Values (1e3*g)", axis=1)
            
            self.check_mass_change(total_mass, starting_mass)

            # Potentiostat / Temperature control functions

            # Empty cell once complete
            self.fluid_handler.empty_cell(total_vol)

            # Clean cell once complete
            self.fluid_handler.clean_cell()

        logging.info(f"Experiment complete after {N} repeat(s).")

        self.gantry.close_ser()
        self.pipette.close_ser()
        self.fluid_handler.close_ser()

    def plot_aspiration_variables(self, name: str, results: np.ndarray, speeds: np.ndarray, constants: np.ndarray) -> None:
        plt.title('Tuning of Aspiration Variables: ' + name)

        for n in range(len(speeds)):
            plt.plot(constants, results[n,:], label = f"{speeds[n]}uL/s")
    
        plt.legend()
        plt.xlabel("Aspirate Constant mbar/uL")
        plt.ylabel("Error ml")
        plt.grid(visible=True, which="both", axis="both")
        plt.show()

    def tune(self, name: str, pot_number: int = 1, aspirate_volume: float = 10, container_volume: float = 50, density: float = 1, asp_const_range: list[float] = [1.0, 1.0], asp_speed_range: list[float] = [1.0, 1.0], N: int = 5, collect_pipette: bool = True) -> None:
        now = datetime.now()
        logging.info("Tuning of aspiration variables for " + name + ": " + now.strftime("%d/%m/%Y %H:%M:%S"))
        logging.info(f"Tuning will perform a total of {N*N} aspirations..")

        errors = np.empty((N,N))
        speeds = np.linspace(asp_speed_range[0], asp_speed_range[1], N)
        constants = np.linspace(asp_const_range[0], asp_const_range[1], N)

        if collect_pipette is True:
            self.pick_pipette(pipette_no=0)

        for i, speed in enumerate(speeds):
            for j, const in enumerate(constants):
                logging.info(f"Aspirating using parameters {const}mbar/uL and {speed}uL/s..")

                doses = math.floor(aspirate_volume // self.max_dose) + 1
                last_dose = aspirate_volume % self.max_dose

                for k in range(doses):
                    if k == doses-1:
                        dose = last_dose
                    else:
                        dose = self.max_dose
                        
                    container_volume = self.collect_volume(dose, container_volume, name, pot_number, const, speed)
                    self.deliver_volume()

                if self.SIM is False:
                    errors[i, j] = ( 1000 * float(input("Input mass balance data in g: ")) / density ) - aspirate_volume
                else:
                    errors[i, j] = random.uniform(-0.2, 0.2)

        self.plot_aspiration_variables(name, errors, speeds, constants)

        # Get minimum error variables
        i_min, j_min = np.unravel_index(np.absolute(errors).argmin(), errors.shape)
        logging.info(f"RESULT: Minimum error of {errors[i_min, j_min]}uL for " + name + f" using {constants[j_min]}mbar/uL and {speeds[i_min]}uL/s.")

        if collect_pipette is True:
            self.return_pipette()

        self.gantry.close_ser()
        self.pipette.close_ser()
        


