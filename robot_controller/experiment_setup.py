import math
import pandas as pd
import numpy as np
import time

import logging
logging.basicConfig(level = logging.INFO)

from robot_controller import gantry_controller

class experiment:
    def __init__(self, CSV_PATH, GANTRY_COM, PIPETTE_COM):

        # Establish serial connections
        #gantry = gantry_controller.gantry(GANTRY_COM)
        #pipette = pipette_controller.pipette(PIPETTE_COM) <- TODO

        # Pot locations 1 -> 10
        self.pot_locations = [[10, 10], [20, 20], 
                              [10, 20], [20, 10], 
                              [30, 30], [20, 30], 
                              [30, 20], [40, 10], 
                              [30, 40], [50, 50]
                              ]
        
        self.pot_base_height = 50
        self.pot_diameter = 30
        self.chamber_location = [100, 10]

        # Open CSV as dataframe
        logging.info("Reading CSV file..")
        self.df = pd.read_csv(CSV_PATH)
        print(self.df)

        logging.info("Experiment ready to begin.")

    def run(self):
        pass



