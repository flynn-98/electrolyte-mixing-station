import logging
import os
import random
import sys
from csv import DictWriter
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from robot_controller import admiral, temperature_controller

logging.basicConfig(level = logging.INFO)

class measurements:
    def __init__(self, squid_port: str, temp_port: str, squid_sim: bool = False, temp_sim: bool = False) -> None:

        self.peltier = temperature_controller.peltier(COM=temp_port, sim=temp_sim)
        self.squid = admiral.squidstat(COM=squid_port, sim=squid_sim)

        self.sim = squid_sim

        self.temp_file = os.path.join(self.squid.results_path, "temperature_report.csv")

        # Temperature parameters
        self.start_temp = self.peltier.max_temp
        self.end_temp = self.peltier.min_temp
        self.temp_points = 8

        self.epsilon_0 = 8.8541878128e-12 # vacuum permittivity
        self.cell_constant = 1.0 # to be set from hardcoded values
        
        self.test_cell_volume = 2.5 # ml from CAD

        # Create file with header if first time running code on PC
        if not os.path.exists(self.temp_file):
            with open(self.temp_file, 'a+') as file:
                writer = DictWriter(file, fieldnames=['Temperature Target', 'Mean Result', 'STD'])
                writer.writeheader()

    def set_blind_temperature(self, temp: float) -> None:
        self.peltier.set_temperature(temp)

    def get_indentifier(self) -> str:
        now = datetime.now()
        return "ID_" + now.strftime("%d-%m-%Y_%H-%M-%S")
        
    def single_temperature_analysis(self, temp: float, report: bool = True) -> None:
        result, mean, std = self.peltier.wait_until_temperature(temp, keep_on=True)

        if result is False:
            logging.error("Failed to cycle through temperature set points.")
            sys.exit()
    
        elif report is True:
            with open(self.temp_file, 'a') as file:
                writer = DictWriter(file, fieldnames=['Temperature Target', 'Mean Result', 'STD'])
                writer.writerow({'Temperature Target': temp, 'Mean Result': mean, 'STD': std})

        id = self.get_indentifier()

        # Take measurements with Squidstat
        self.squid.take_measurements(id)

        # Turn off Peltiers
        self.peltier.clear_run_flag()

        # Get data
        ohmic_resistance, ionic_conductivity = self.get_impedance_properties(identifier=id)

        return (ohmic_resistance, ionic_conductivity)

    def full_range_temperature_analysis(self, report: bool = True) -> None:
        logging.info(f"Cycling through {self.temp_points} temperatures from {self.start_temp}C to {self.end_temp}C..")

        temperatures = np.linspace(self.start_temp, self.end_temp, self.temp_points)
        data = np.empty((self.temp_points, 2))

        for i, temp in enumerate(temperatures):
            result, mean, std = self.peltier.wait_until_temperature(temp, keep_on=True)
            
            if result is False:
                logging.error("Failed to cycle through temperature set points.")
                sys.exit()
    
            elif report is True:
                with open(self.temp_file, 'a') as file:
                    writer = DictWriter(file, fieldnames=['Temperature Target', 'Mean Result', 'STD'])
                    writer.writerow({'Temperature Target': temp, 'Mean Result': mean, 'STD': std})

            id = self.get_indentifier()

            # Take measurements with Squidstat
            self.squid.take_measurements(id)

            # Get data
            data[0,i], data[1,i] = self.get_impedance_properties(identifier=id)

        # Turn off Peltiers
        self.peltier.clear_run_flag()

        return pd.DataFrame(data=np.vstack((temperatures, data)))

    def plot_EIS(self, identifier: str = "na") -> None:
        logging.info("Saving EIS plot (Dataset " + identifier + ")..")
        data = pd.read_csv(self.squid.get_ac_path(identifier)).to_numpy()

        plt.figure()
        plt.title("EIS Data Results: " + identifier)
        plt.xlabel("Zreal (Ohms)")
        plt.ylabel("Zimag (Ohms)")
        plt.scatter(data[:, 3], -data[:, 4]) #Zreal vs -Zimag
        plt.savefig(os.path.join(self.squid.results_path, identifier+".png"))
        plt.close()

    def get_impedance_properties(self, identifier: str = "na", plot: bool = True) -> float:
        if self.sim is True:
            return (random.random(), random.random())
        
        # AC data required for impedance properties
        data = pd.read_csv(self.squid.get_ac_path(identifier)).to_numpy()

        frequency = data[:, 2]
        z_real = data[:, 3]

        z_img = -data[:, 4]
        abs_imag = np.abs(data[:, 4])
        
        # Finding ohmic resistance
        min_imag = np.amin(abs_imag) # minimum of abs(Imag)

        min_index = np.where(abs_imag == min_imag)[0][0] # take the first index if multiple instances
        ohmic_resistance = np.round(z_real[min_index], 5).item() * 100 # take real value corresponding to minimum imag

        logging.info(f"Ohmic Resistance calculated as {ohmic_resistance}Ohms (Dataset: " + identifier + ").")

        # Finding Ionic conductivity
        conductivity = np.empty((1,0))
        tan_delta = np.empty((1,0))

        for i in range(len(z_real)):
            z_square = z_real[i] ** 2 + z_img[i] ** 2
            epsilon_real = z_img[i] * self.cell_constant / (2 * np.pi * frequency[i] * self.epsilon_0 * z_square)
            epsilon_img = z_real[i] * self.cell_constant / (2 * np.pi * frequency[i] * self.epsilon_0 * z_square)

            conductivity = np.append(conductivity, np.array([self.epsilon_0 * epsilon_img * 2 * np.pi * frequency[i]]))
            tan_delta = np.append(tan_delta, np.array([epsilon_img / epsilon_real]))

        max_index = np.argmax(tan_delta)
        ionic_conductivity = np.round(conductivity[max_index], 5).item() * 1000 # ms/cm

        logging.info(f"Ionic Conductivity calculated as {ionic_conductivity}mS/cm (Dataset: " + identifier + ").")

        if plot is True:
            self.plot_EIS(identifier)

        return ohmic_resistance, ionic_conductivity