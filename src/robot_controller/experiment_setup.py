import math
import pandas as pd
import numpy as np
import time
from IPython.display import display

import logging
logging.basicConfig(level = logging.INFO)

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
        self.pot_diameter = 27.8
        self.chamber_location = [7, 116]

        # Open CSV as dataframe
        logging.info("Reading CSV file..")
        self.column_names = ["Name", "Volume (uL)", "Starting Volume (mL)", "Aspirate Speed (W/s)", "Aspirate Constant (mbar/ml)"]
        self.df = pd.read_csv(CSV_PATH, names=self.column_names)
        display(self.df)

        logging.info(f'Experiment will result in a total electrolyte volume of {self.df[self.column_names[1]].sum()/1000}ml')
        logging.info("Experiment ready to begin.")

    def run(self):
        non_zero = self.df[self.df[self.column_names[1]] > 0]
        pot_area = math.pi * self.pot_diameter**2 / 4

        # Loop through all non zero constituents
        for i in non_zero.index.to_numpy(dtype=int):
            # Get pot locations
            x = self.pot_locations[i][0]
            y = self.pot_locations[i][1]
            z = 0

            # Extract relevant data
            name = non_zero[non_zero.index == i][self.column_names[0]].values[0]
            starting_volume = non_zero[non_zero.index == i][self.column_names[1]].values[0]

            # Move above pot
            logging.info("Moving to " + name + "..")
            self.gantry.move(x, y, z)

            # Charge pipette
            logging.info("Pipette charged.")

            # Drop into fluid (based on starting volume)
            logging.info("Dropping Pipette into " + name + "..")
            z = self.pot_base_height + starting_volume / pot_area
            self.gantry.move(x, y, z)

            # Aspirate pipette
            logging.info("Aspiration complete.")

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