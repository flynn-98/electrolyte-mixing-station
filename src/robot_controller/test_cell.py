import logging
import os
import sys
from csv import DictWriter

import numpy as np
import pandas as pd

from robot_controller import admiral, temperature_controller

logging.basicConfig(level = logging.INFO)

class analytics:
    def __init__(self, squid_port: str, temp_port: str, squid_sim: bool = False, temp_sim: bool = False) -> None:

        self.peltier = temperature_controller.peltier(temp_port, temp_sim)
        self.squid = admiral.squidstat(squid_port, squid_sim)

        self.temp_file = "data/results/temperature_report.csv"

        # Temperature parameters
        self.start_temp = 60.0
        self.end_temp = -10.0
        self.temp_points = 8

        # create np array of data ?

    def analyse_electrolyte(self, report: bool = True) -> None:
        logging.info(f"Cycling through {self.temp_points} temperatures from {self.start_temp}C to {self.end_temp}C.")

        file_exists = os.path.exists(self.report_file)

        for val in np.linspace(self.start_temp, self.end_temp, self.temp_points):
            result, mean, std = self.peltier.wait_until_temperature(val, keep_on=True)
            
            if result is False:
                logging.error("Failed to cycle through temperature set points.")
                sys.exit()
    
            elif report is True:
                with open(self.temp_file, 'a') as file:
                    writer = DictWriter(file, fieldnames=['Temperature Target', 'Mean Result', 'STD'])
                    
                    if file_exists is False:
                        writer.writeheader()
                        file_exists = True

                    writer.writerow({'Temperature Target': val, 'Mean Result': mean, 'STD': std})

            # Take measurements with Squidstat
            ac_data, dc_data = self.squid.take_measurements()

            print(ac_data)
            print(dc_data)

            # Extract values from data - how? what?

    def analyse_data(self, ac_data: pd.DataFrame, dc_data: pd.dataFrame) -> np.ndarray:
        pass