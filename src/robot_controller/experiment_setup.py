import math
import pandas as pd
import numpy as np
import time
import sys
from IPython.display import display

from datetime import datetime

import logging

# Save logs to file
file_handler = logging.basicConfig(filename="experiment_log.txt",
                    filemode='a',
                    format='%(asctime)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO)

# Also output to stdout
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

from robot_controller import gantry_controller, pipette_controller

class experiment:
    def __init__(self, CSV_PATH, GANTRY_COM, PIPETTE_COM, SIM=False):

        # Establish serial connections
        self.gantry = gantry_controller.gantry(GANTRY_COM, SIM)
        self.pipette = pipette_controller.pipette(PIPETTE_COM, SIM)

        # Pot locations 1 -> 10
        self.pot_locations = [[7, 21], [7, 55], 
                              [41, 21], [41, 55], 
                              [75, 21], [75, 55], 
                              [109, 21], [109, 55], 
                              [143, 21], [143, 55]
                            ]
        
        self.pot_base_height = -74 - 0.5 # CAD value minus tunable value to ensure submersion
        self.pot_area = math.pi * 2.78**2 / 4 #cm2
        self.chamber_location = [7, 116]

        # Open CSV as dataframe
        logging.info("Reading CSV file..")
        self.column_names = ["Name", "Volume (uL)", "Starting Volume (mL)", "Aspirate Speed (mbar/s)", "Aspirate Constant (mbar/ml)"]
        # Using dictionary to convert specific columns
        convert_dict = {'Name': str,
                        'Volume (uL)': float,
                        'Starting Volume (mL)': float,
                        'Aspirate Speed (mbar/s)': float,
                        'Aspirate Constant (mbar/ml)': float,
                        }
        
        self.df = pd.read_csv(CSV_PATH, names=self.column_names).astype(convert_dict)
        display(self.df)

        logging.info(f'Experiment will result in a total electrolyte volume of {self.df[self.column_names[1]].sum()/1000}ml')
        
        now = datetime.now()
        logging.info("Experiment ready to begin: " + now.strftime("%d/%m/%Y %H:%M:%S"))

    def run(self, N=1):
        for n in range(0, N):
            logging.info(f"Creating electrolyte mixture #{n}..")
            non_zero = self.df[self.df["Volume (uL)"] > 0]

            # Loop through all non zero constituents
            for i in non_zero.index.to_numpy(dtype=int):
                # Get pot locations
                x = self.pot_locations[i][0]
                y = self.pot_locations[i][1]
                z = 0

                # Extract relevant data
                relevant_row = non_zero.loc[i]
                name = relevant_row["Name"]
                aspirate_volume = relevant_row["Volume (uL)"]
                starting_volume = relevant_row["Starting Volume (mL)"]

                new_volume = starting_volume - aspirate_volume * 1e-3 #ml

                # Set new starting volume for next repeat
                self.df.loc[i, "Starting Volume (mL)"] = new_volume

                # Move above pot
                logging.info("Moving to " + name + "..")
                self.gantry.move(x, y, z)

                # Charge pipette
                logging.info("Pipette charged.")

                # Drop into fluid (based on starting volume)
                logging.info("Dropping Pipette into " + name + "..")
                z = self.pot_base_height + 10 * new_volume / self.pot_area
                self.gantry.move(x, y, z)

                # Aspirate pipette
                logging.info("Aspiration complete.")
                logging.info(f"{aspirate_volume}ul extracted, {new_volume}ml remaining..")

                # Move out of fluid
                logging.info("Moving Pipette out of " + name + "..")
                z = 0
                self.gantry.move(x, y, z)

                # Move to mixing chamber
                logging.info("Moving to Mixing Chamber..")
                x = self.chamber_location[0]
                y = self.chamber_location[1]
                self.gantry.move(x, y, z)

                # Dispense pipette
                logging.info("Dispense complete.")

        logging.info(f"Experiment complete after {N} repeat(s).")

        logging.info("Remaining volumes..")
        display(self.df)