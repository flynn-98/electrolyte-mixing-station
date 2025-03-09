import json
import logging
import math
import os
import sys
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from robot_controller import fluid_controller, mass_balance, mixing_station, test_cell

# Save logs to file
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO,
                    force=True,
                    handlers=[logging.FileHandler("mixing_station.log", mode="a"), logging.StreamHandler(sys.stdout)])

class scheduler:
    def __init__(self, device_name: str, csv_filename: str | None = None, home: bool = False) -> None:
        # Read device data JSON
        self.json_file = "data/devices/hardcoded_values.json"
        device_data = self.read_json(device_name)

        # Establish serial connections
        self.fluid_handler = fluid_controller.fluid_handler(device_data["Fluid_Address"], not device_data["Fluid_Active"])
        self.mass_balance = mass_balance.mass_reader(device_data["Mass_Address"], not device_data["Mass_Active"])
        
        self.test_cell = test_cell.measurements(squid_port=device_data["Squid_Address"], temp_port=device_data["Temp_Address"], squid_sim=not device_data["Squid_Active"], temp_sim=not device_data["Temp_Active"])
        self.mixer = mixing_station.electrolyte_mixer(gantry_port=device_data["Gantry_Address"], pipette_port=device_data["Pipette_Address"], gantry_sim=not device_data["Gantry_Active"], pipette_sim=not device_data["Pipette_Active"], home=home)

        # Retrieve any requried variables from controllers
        self.max_dose = self.mixer.pipette.max_dose()

        # Set any required variables for controllers
        self.mass_balance.correction = 50 #g

        # Retrieve hardcoded values and pass down
        self.mixer.gantry.x_correction = device_data["X_Gantry_Shift"]
        self.mixer.gantry.y_correction = device_data["Y_Gantry_Shift"]

        self.mixer.workspace_height_correction = device_data["Z_Workspace_Shift"]
        self.mixer.correct_workspace_heights()

        self.test_cell.squid.mode = device_data["Squid_Mode"]

        logging.info("Successfully passed hardcoded values for " + device_name + ".")

        # Declare variables for CSV read
        self.df = pd.DataFrame()
        self.csv_path = "data/recipes"
        self.csv_filename = csv_filename

        # Convert CSV file to df
        if self.csv_filename is not None:
            self.read_csv()

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
                        'Aspirate Scalar': float,
                        'Aspirate Speed (uL/s)': float,
                        'Cost (/uL)': float,
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

    def close_all_ports(self) -> None:
        if self.mixer.gantry.ser.isOpen() is True:
                self.mixer.gantry.close_ser()

        if self.mixer.pipette.ser.isOpen() is True:
                self.mixer.gantry.close_ser()

        if self.fluid_handler.ser.isOpen() is True:
                self.fluid_handler.close_ser()

        if self.test_cell.peltier.ser.isOpen() is True:
            self.test_cell.peltier.close_ser()

        if self.mass_balance.ser.isOpen() is True:
            self.mass_balance.close_ser()

    def update_dose_volumes(self, new_volumes: dict) -> None:
        #{'param_a': 5.0, 'param_b': 5.0, ..} dict formal provided by atinary

        for i in self.df.index.to_numpy(dtype=int):
            found = False

            for suggestion in new_volumes:
                # Loop through all and find correct name, in case of order mismatch
                target = self.df.loc[i, "Name"]
                new_value = new_volumes[suggestion]

                if target == suggestion:
                    self.df.loc[i, "Dose Volume (uL)"] = new_value
                    logging.info(target + f" dose volume updated to {new_value}uL.")
                    found = True

            if found is False:
                logging.error("No suggestion found for " + target + "!")
                sys.exit()

        # Save to current state
        self.save_csv()

    def run(self, temp: float | None = None) -> pd.DataFrame | tuple[float, float]:
        if temp is None:
            logging.info(f"Setting early temperature target of {temp}C..")
            self.test_cell.set_temperature_target(temp)
        else:
            # If no temperature provided, default to full cycle analysis
            self.test_cell.set_temperature_target(self.test_cell.start_temp)

        logging.info("Beginning electrolyte mixing..")
        self.mixer.move_to_start()

        # Check if pipette currently active, return if so
        self.mixer.return_pipette()

        try:
            non_zero = self.df[self.df["Dose Volume (uL)"] > 0]
        except Exception as ex:
            logging.error("No CSV loaded.")
            logging.error(ex)
            sys.exit()
            
        # Loop through all non zero constituents
        for i in non_zero.index.to_numpy(dtype=int):
            # Collect pipette for desired chemical (pipette 1 for pot 1)
            self.mixer.pick_pipette(i+1)
    
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

                if math.floor(dose) == 0:
                    continue

                # Aspirate using data from relevant df row, increment pot co ordinates
                pot_volume = self.mixer.collect_volume(dose, pot_volume, relevant_row["Name"], i+1, relevant_row["Aspirate Scalar"], relevant_row["Aspirate Speed (uL/s)"])

                # Move to mixing chamber and dispense
                self.mixer.deliver_volume()

                # Set new starting volume for next repeat
                self.df.loc[i, "Container Volume (mL)"] = pot_volume

                # Save csv in current state (starting volumes up to date in case of unexpected interruption)
                self.save_csv()

            # Return pipette
            self.mixer.return_pipette()

        # Trigger servo to mix electrolyte
        self.mixer.gantry.mix()

        # Let mixture settle
        time.sleep(1)

        # Take mass balance reading
        starting_mass = self.mass_balance.get_mass()

        # Pump electrolyte to next stage
        total_vol = self.df["Dose Volume (uL)"].sum()
        self.fluid_handler.add_electrolyte(total_vol)

        # Mass Balance checks
        self.df["Temp Mass Values (1e3*g)"] =  self.df["Density (g/mL)"] * self.df["Dose Volume (uL)"]
        total_mass = self.df["Temp Mass Values (1e3*g)"].sum()/1000
        self.df = self.df.drop("Temp Mass Values (1e3*g)", axis=1)
            
        self.mass_balance.check_mass_change(total_mass, starting_mass)

        # Potentiostat / Temperature control functions
        if temp is None:
            # returns df of multiple (ohmics res, ionic conductivity)
            impedance_results = self.test_cell.full_range_temperature_analysis() 
        else:
            # returns tuple (ohmics res, ionic conductivity)
            impedance_results = self.test_cell.single_temperature_analysis(temp) 
        
        # Empty cell
        self.fluid_handler.empty_cell(total_vol)

        # Clean cell
        self.fluid_handler.clean_cell()

        logging.info("Run complete.")

        return impedance_results

    def run_life_test(self, N: int = 1) -> None:
        logging.info(f"Beginning {N}X life test..")
        self.csv_filename = "life_test.csv"
        self.read_csv()

        for n in range(N):
            logging.info(f"Creating electrolyte mixture #{n+1}..")
            self.run()

    def plot_aspiration_results(self, path: str) -> None:
        df = pd.read_csv(path, index_col=0)
        results = df.to_numpy(dtype=float)

        volumes = df.columns.to_numpy(dtype=float)
        scalars = df.index.to_numpy(dtype=float)

        # Normalise error by number of doses
        normalised_results = np.copy(results)
        for i in range(len(volumes)):
            doses = math.floor(volumes[i] // self.max_dose) + 1
            normalised_results[:,i] = results[:,i] / doses

        fig, [ax1, ax2] = plt.subplots(1, 2, figsize=(12,6))
        fig.suptitle(f'Results of Aspiration Tuning: {volumes[0]} - {volumes[-1]}uL')

        for n in range(len(scalars)):
            print(results[n,:])
            ax1.plot(volumes, results[n,:], label = f"{scalars[n]}")
    
        ax1.legend()
        ax1.set_xlabel("Target Volume (uL)")
        ax1.set_ylabel("Accumulated Error (uL)")
        ax1.grid(visible=True, which="both", axis="both")

        for n in range(len(scalars)):
            print(normalised_results[n,:])
            ax2.plot(volumes, normalised_results[n,:], label = f"{scalars[n]}")
    
        ax2.legend()
        ax2.set_xlabel("Target Volume (uL)")
        ax2.set_ylabel("Dose Normalised Error (uL)")
        ax2.grid(visible=True, which="both", axis="both")

        plt.show()

    def tune(self, pot_number: int, aspirate_scalars: list[float], aspirate_volume: list[float], container_volume: float, density: float, N: int, M: int, aspirate_speed: float = 100.0, move_electrolyte: bool = False) -> None:
        now = datetime.now()
        logging.info(f"Tuning will perform a total of {N*M} aspirations: " + now.strftime("%d/%m/%Y %H:%M:%S"))
        self.mixer.move_to_start()

        path = "data/results/aspiration_tuning_results.csv"

        errors = np.zeros((N,M))
        scalars = np.linspace(aspirate_scalars[0], aspirate_scalars[1], N) # i -> N
        volumes = np.linspace(aspirate_volume[0], aspirate_volume[1], M) # j -> M

        for i, scalar in enumerate(scalars):
            for j, volume in enumerate(volumes):
                logging.info(f"Aspirating {volume}uL using parameter {scalar}..")
                
                doses = math.floor(volume // self.max_dose) + 1
                last_dose = volume % self.max_dose

                # Take mass balance reading
                starting_mass = self.mass_balance.get_mass()

                for k in range(doses):
                    if k == doses-1:
                        dose = last_dose
                    else:
                        dose = self.max_dose

                    if math.floor(dose) == 0:
                        continue 
                    
                    container_volume = self.mixer.collect_volume(dose, container_volume, "_", pot_number, scalar, aspirate_speed)
                    self.mixer.deliver_volume()

                if move_electrolyte is True: 
                    # Pump electrolyte to next stage
                    self.fluid_handler.add_electrolyte(volume, tube_length=500, overpump=1.3)

                # New mass reading
                change = 1e3 * (self.mass_balance.get_mass() - starting_mass) / density

                # Record error
                if move_electrolyte is True: 
                    errors[i][j] = math.floor(change - (volume - self.mass_balance.correction)) # uL
                else:
                    errors[i][j] = math.floor(change - volume) # uL

                # Save results
                pd.DataFrame(errors, index=scalars, columns=volumes).to_csv(path, index=True)

        # Plot results
        self.plot_aspiration_results(path)

        # Get minimum error variables
        i_min, j_min = np.unravel_index(np.absolute(errors).argmin(), errors.shape)
        logging.info(f"RESULT: Minimum error of {errors[i_min, j_min]}uL using {scalars[i_min]}uL/s and {volumes[j_min]}uL.")
