import math
import pandas as pd
import numpy as np
import sys
import time
import random
import json

from IPython.display import display
import matplotlib.pyplot as plt

from datetime import datetime

import logging

# Save logs to file
file_handler = logging.basicConfig(filename="experiment_log.txt",
                    filemode='a',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO)

# Also output to stdout
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

from robot_controller import gantry_controller, pipette_controller

class experiment:
    def __init__(self, device_name):
        # Read device data JSON
        device_data = self.read_json(device_name)

        # Only record mass balance readings if Pipette active
        self.SIM = not device_data["Pipette_Active"]

        # Establish serial connections
        self.gantry = gantry_controller.gantry(device_data["Gantry_Address"], not device_data["Gantry_Active"])
        self.pipette = pipette_controller.pipette(device_data["Pipette_Address"], self.SIM)

        # Pot locations 1 -> 10 (mm)
        self.pot_locations = [[41, 0], [75, 0], 
                              [109, 0], [143, 0], 
                              [58, 34], [92, 34], 
                              [126, 34], [75,68], 
                              [109, 68], [143, 68]
                            ]
        
        self.pot_base_height = -74 - 0.5 # CAD value minus tunable value to ensure submersion
        self.pot_area = math.pi * 2.78**2 / 4 #cm2

        self.chamber_location = [12, 110] # mm
        self.mass_balance_location = [12, 110] # mm
        self.dispense_height = -15 #mm

        # Declare variables for CSV read
        self.column_names = None
        self.df = None

    def read_json(self, device_name):
        json_file = 'data/devices/mixing_stations.json'

        with open(json_file) as json_data:
            device_data = json.load(json_data)

        for i, device in enumerate(device_data["Mixing Stations"]):
            if device['ID'] == device_name:
                index = i 
                logging.info("Located device data for " + device_name + ".")

                return device_data["Mixing Stations"][index]

        logging.error("Device data for " + device_name + " could not be located.")
        sys.exit()

    def read_csv(self, CSV_PATH):
        # Open CSV as dataframe
        logging.info("Reading CSV file..")
        self.column_names = ["Name", "Volume (uL)", "Starting Volume (mL)", "Density (g/mL)", "Aspirate Constant (mbar/mL)", "Aspirate Speed (uL/s)"]
        # Using dictionary to convert specific columns
        convert_dict = {'Name': str,
                        'Volume (uL)': float,
                        'Starting Volume (mL)': float,
                        'Density (g/mL)': float,
                        'Aspirate Constant (mbar/mL)': float,
                        'Aspirate Speed (uL/s)': float,
                        }
        
        self.df = pd.read_csv(CSV_PATH, names=self.column_names).astype(convert_dict)
        display(self.df)

        logging.info(f'Recipe will result in a total electrolyte volume of {self.df["Volume (uL)"].sum()/1000}mL')
        
        now = datetime.now()
        logging.info("Experiment ready to begin: " + now.strftime("%d/%m/%Y %H:%M:%S"))

    def get_poly_equation(self, xi, diff, T, N):
        time = np.linspace(0, T, N)

        # polynomial coefficients
        C_0 = xi
        C_1 = 0
        C_3 = diff * 10 / pow(T, 3)
        C_4 = diff * -15 / pow(T, 4)
        C_5 = diff * 6 / pow(T, 5)

        return C_0 + C_3 * np.power(time, 3) + C_4 * np.power(time, 4) + C_5 * np.power(time, 5)

    def aspirate_at_speed(self, charge_pressure, aspirate_volume, aspirate_constant, aspirate_speed, pressure_resolution, poly=True):
        diff = aspirate_constant * aspirate_volume
        aspirate_pressure = diff + charge_pressure # Pressure diff is from charge pressure
        rise_time = aspirate_volume / aspirate_speed # Seconds

        logging.info(f"Rising to aspiration pressure of {aspirate_pressure}mbar in {rise_time}s, from charged pressure of {charge_pressure}mbar.")
        N = math.floor(diff / pressure_resolution) + 2 # Ideal resolution of sensor (1.7bar range with 12bit value), N >= 2
        dT = rise_time / (N-1)

        if poly==False:
            path = np.linspace(charge_pressure, aspirate_pressure, N)
        else:
            path = self.get_poly_equation(charge_pressure, diff, rise_time, N)

        for set_point in path:
            self.pipette.set_pressure(set_point)
            time.sleep(dT)

        return aspirate_pressure
    
    def aspiration_test(self, pressure_resolution=0.415):
        # Used for testing only => No logging

        try:
            charge_pressure = float(input("Enter charge pressure (mbar): "))
        except:
            charge_pressure = 50 
            print(f"Charge Pressure set to {charge_pressure}mbar.")

        # Charge pipette
        self.pipette.set_pressure(charge_pressure)
        print("Pipette charged.")

        try:
            aspirate_volume = float(input("Enter Aspirate Volume (uL): "))
        except:
            aspirate_volume = 10
            print(f"Aspirate Volume set to {aspirate_volume}uL.")

        try:
            aspirate_constant = float(input("Enter Aspirate Constant (mbar/uL): "))
        except:
            aspirate_constant = 0.5
            print(f"Aspirate Constant set to {aspirate_constant}mbar/uL.")

        try:
            aspirate_speed = float(input("Enter Aspirate Speed (uL/s): "))
        except:
            aspirate_speed = 10
            print(f"Aspirate Speed set to {aspirate_speed}uL/s.")

        # Aspirate pipette
        aspirate_pressure = self.aspirate_at_speed(charge_pressure, aspirate_volume, aspirate_constant, aspirate_speed, pressure_resolution)

        print("Aspiration complete.")
        print(f"{aspirate_volume}uL extracted.")

        # Delay to let system settle
        time.sleep(2)

        # Report final readings (charge + aspirate)
        reading = self.pipette.get_pressure()
        error = reading - aspirate_pressure
        if abs(error) > 1.5 * pressure_resolution:
            print(f"Aspriate pressure off target by {error}mbar for requested {aspirate_pressure}mbar.")
        else:
            print(f"Pressure reading of {reading}mbar achieved for requested {aspirate_pressure}mbar.")
        print(f"Pump power at {self.pipette.get_power()}mW.")

        _ = input("Press any key to Dispense")

         # Dispense pipette
        self.pipette.set_pressure(0) # To dispense as quickly as possible to remove all liquid
        print("Dispense complete.")

    def aspirate(self, aspirate_volume, starting_volume, name, x, y, aspirate_constant, aspirate_speed, charge_pressure=50, pressure_resolution=0.415):
        new_volume = starting_volume - aspirate_volume * 1e-3 #ml

        # Move above pot
        logging.info("Moving to " + name + "..")
        self.gantry.move(x, y, 0)

        # Charge pipette
        self.pipette.set_pressure(charge_pressure)
        logging.info("Pipette charged.")

        # Drop into fluid (based on starting volume)
        z = self.pot_base_height + 10 * new_volume / self.pot_area
        logging.info(f"Dropping Pipette to {z}mm..")
        self.gantry.move(x, y, z)

        # Aspirate pipette
        aspirate_pressure = self.aspirate_at_speed(charge_pressure, aspirate_volume, aspirate_constant, aspirate_speed, pressure_resolution)

        logging.info("Aspiration complete.")
        logging.info(f"{aspirate_volume}uL extracted, {new_volume}mL remaining..")

        # Delay to let system settle
        time.sleep(2)

        # Report final readings (charge + aspirate)
        reading = self.pipette.get_pressure()
        error = reading - aspirate_pressure
        if abs(error) > 1.5 * pressure_resolution:
            logging.error(f"Aspriate pressure off target by {error}mbar for requested {aspirate_pressure}mbar.")
        else:
            logging.info(f"Pressure reading of {reading}mbar achieved for requested {aspirate_pressure}mbar.")
        logging.info(f"Pump power at {self.pipette.get_power()}mW.")

        # Move out of fluid
        logging.info("Lifting Pipette..")
        self.gantry.move(x, y, 0)
        
        return new_volume
    
    def dispense(self, name, x, y):
        logging.info("Moving to " + name + "..")
        self.gantry.move(x, y, 0)
        
        logging.info(f"Dropping Pipette to {self.dispense_height}mm..")
        self.gantry.move(x, y, self.dispense_height)

        # Dispense pipette
        self.pipette.set_pressure(0) # To dispense as quickly as possible to remove all liquid
        logging.info("Dispense complete.")

        logging.info("Lifting Pipette..")
        self.gantry.move(x, y, 0)

    def run(self, N=1):
        for n in range(0, N):
            logging.info(f"Creating electrolyte mixture #{n}..")

            try:
                non_zero = self.df[self.df["Volume (uL)"] > 0]
            except:
                logging.error(f"No CSV loaded.")
                sys.exit()

            # Loop through all non zero constituents
            for i in non_zero.index.to_numpy(dtype=int):
    
                # Extract relevant df row
                relevant_row = non_zero.loc[i]

                # Aspirate using data from relevant df row, increment pot co ordinates
                new_volume = self.aspirate(relevant_row["Volume (uL)"], relevant_row["Starting Volume (mL)"], relevant_row["Name"], self.pot_locations[i][0], self.pot_locations[i][1], relevant_row["Aspirate Constant (mbar/mL)"], relevant_row["Aspirate Speed (uL/s)"])

                # Set new starting volume for next repeat
                self.df.loc[i, "Starting Volume (mL)"] = new_volume

                # Move to mixing chamber
                self.dispense("Mixing Chamber", self.chamber_location[0], self.chamber_location[1])

            # Trigger servo to mix electrolyte
            self.gantry.mix()

            # Let mixture settle
            time.sleep(2)

            # Pump electrolyte to next stage
            total_vol = self.df["Volume (uL)"].sum()/1000
            self.gantry.pump(total_vol)

        logging.info(f"Experiment complete after {N} repeat(s).")

        logging.info("Remaining volumes..")
        display(self.df)

        self.gantry.softHome()

    def plot_aspiration_variables(self, name, results, speeds, constants):
        plt.title('Tuning of Aspiration Variables: ' + name)

        for n in range(0, len(speeds)):
            plt.plot(constants, results[n,:], label = f"{speeds[n]}uL/s")
    
        plt.legend()
        plt.xlabel("Aspirate Constant mbar/mL")
        plt.ylabel("Error ml")
        plt.grid(visible=True, which="both", axis="both")
        plt.show()

    def tune(self, name, pot_number=1, aspirate_volume=10, starting_volume=50, density=1, asp_const_range=[1, 1], asp_speed_range=[1, 1], N=5):
        now = datetime.now()
        logging.info("Tuning of aspiration variables for " + name + ": " + now.strftime("%d/%m/%Y %H:%M:%S"))
        logging.info(f"Tuning will perform a total of {N*N} aspirations..")

        errors = np.empty((N,N))
        speeds = np.linspace(asp_speed_range[0], asp_speed_range[1], N)
        constants = np.linspace(asp_const_range[0], asp_const_range[1], N)

        for i, speed in enumerate(speeds):
            for j, const in enumerate(constants):
                logging.info(f"Aspirating using parameters {const}mbar/mL and {speed}uL/s..")

                starting_volume = self.aspirate(aspirate_volume, starting_volume, name, self.pot_locations[pot_number-1][0], self.pot_locations[pot_number-1][1], const, speed)
                self.dispense("Mass Balance", self.mass_balance_location[0], self.mass_balance_location[1])

                if self.SIM == False:
                    errors[i, j] = ( 1000 * float(input("Input mass balance data in g: ")) / density ) - aspirate_volume
                else:
                    errors[i, j] = random.uniform(-0.2, 0.2)

        self.plot_aspiration_variables(name, errors, speeds, constants)

        # Get minimum error variables
        i_min, j_min = np.unravel_index(np.absolute(errors).argmin(), errors.shape)
        logging.info(f"RESULT: Minimum error of {errors[i_min, j_min]}uL for " + name + f" using {constants[j_min]}mbar/mL and {speeds[i_min]}uL/s.")

        self.gantry.softHome()
        


