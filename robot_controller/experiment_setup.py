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
        self.pot_locations = [[7, 21], [7, 55], 
                              [41, 21], [41, 55], 
                              [75, 21], [75, 55], 
                              [109, 21], [109, 55], 
                              [143, 21], [143, 55]
                            ]
        
        self.pot_base_height = -74
        self.pot_diameter = 27.8
        self.chamber_location = [7, 116]

        # Open CSV as dataframe
        logging.info("Reading CSV file..")
        self.df = pd.read_csv(CSV_PATH)
        print(self.df)

        logging.info("Experiment ready to begin.")

    def run(self):
        pass



