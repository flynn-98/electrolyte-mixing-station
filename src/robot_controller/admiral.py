import logging
import sys

import pandas as pd
from PySide6.QtWidgets import QApplication
from SquidstatPyLibrary import (
    AisConstantCurrentElement,
    AisConstantPotElement,
    AisConstantPowerElement,
    AisConstantResistanceElement,
    AisCyclicVoltammetryElement,
    AisDCCurrentSweepElement,
    AisDCPotentialSweepElement,
    AisDeviceTracker,
    AisDiffPulseVoltammetryElement,
    AisEISGalvanostaticElement,
    AisEISPotentiostaticElement,
    AisExperiment,
    AisNormalPulseVoltammetryElement,
    AisOpenCircuitElement,
    AisSquareWaveVoltammetryElement,
)

# Suppress FutureWarning messages from Pandas
logging.basicConfig(level = logging.INFO)

class squidstat:
    def __init__(self, COM: str, instrument: str = "Plus1894", channel: int = 0, sim: bool = False) -> None:
        self.sim = sim

        self.app = QApplication()
            
        self.tracker = AisDeviceTracker.Instance()
        self.experiment = None
        self.channel = channel

        self.ac_columns = [
                "Timestamp",
                "Frequency [Hz]",
                "Absolute Impedance",
                "Phase Angle",
                "Real Impedance",
                "Imaginary Impedance",
                "Total Harmonic Distortion",
                "Number of Cycles",
                "Working electrode DC Voltage [V]",
                "DC Current [A]",
                "Current Amplitude",
                "Voltage Amplitude",
            ]
        
        self.dc_columns = [
                "Timestamp",
                "Working Electrode Voltage [V]",
                "Working Electrode Current [A]",
                "Temperature [C]",
            ]
        
        self.step_colums = [
                "Step Name", 
                "Step Number", 
                "Substep Number",
            ]
        
        # Create dataframes
        self.reset_dataframes()
        
        if self.sim is False:
            # Attach functions to call during events
            self.tracker.newDeviceConnected.connect(self.handle_device_connected)

            try:
                # Connect to device and find handler for specified type
                self.tracker.connectToDeviceOnComPort(COM)
                self.handler = self.tracker.getInstrumentHandler(instrument)
            except Exception as ex:
                logging.error("Failed to establish serial connection to Squidstat: " + ex)
                sys.exit()

            logging.info("Serial connection to Squidstat established.")

            # Attach more functions to events
            self.handler.activeACDataReady.connect(self.increment_ac_data)
            self.handler.activeDCDataReady.connect(self.increment_dc_data)

            self.handler.experimentNewElementStarting.connect(self.increment_elements)
            self.handler.experimentStopped.connect(self.handle_experiment_stopped)

    def reset_dataframes(self) -> None:
        logging.info("Resetting AC and DC dataframes..")

        # Clear AC and DC data dataframes
        self.ac_data = pd.DataFrame(columns=self.ac_columns)
        self.dc_data = pd.DataFrame(columns=self.dc_columns)
        self.elements = pd.DataFrame(columns=self.step_colums)     

    def get_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Return the AC and DC data as pandas dataframes. If no data is available, return None for the respective dataframe.
        
        logging.info("Checking if potentiostat data is available..")

        if self.ac_data.empty is True:
            logging.error("No AC data available!")
            return None, self.dc_data_list
        
        elif self.dc_data.empty is True:
            logging.error("No DC data available!")
            return self.ac_data_list, None
        
        else:
            logging.info("Returning available AC and DC data..")
            return self.ac_data, self.dc_data

    def increment_dc_data(self, channel: int, data) -> None:
        # Append incoming data to dataframe
        # channel variable expected in connected function (see https://admiral-instruments.github.io/AdmiralSquidstatAPI/md_intro_and_examples_9__python_example.html)

        logging.info(f"Extracting DC data from channel {channel}..")

        if data.timestamp is not None:
            values = [
                data.timestamp,
                data.workingElectrodeVoltage, 
                data.current, 
                data.temperature
            ]
            
            next_step = dict(zip(self.dc_columns, values))
            self.dc_data = self.dc_data.append(next_step)

    def increment_ac_data(self, channel: int, data) -> None:
        # Append incoming data to dataframe
        logging.info(f"Extracting AC data from channel {channel}..")

        if data.timestamp is not None:
            values = [
                data.timestamp,
                data.frequency,
                data.absoluteImpedance,
                data.phaseAngle,
                data.realImpedance,
                data.imagImpedance,
                data.totalHarmonicDistortion,
                data.numberOfCycles,
                data.workingElectrodeDCVoltage,
                data.DCCurrent,
                data.currentAmplitude,
                data.voltageAmplitude
            ]

            next_step = dict(zip(self.ac_columns, values))
            self.ac_data = self.ac_data.append(next_step)

    def increment_elements(self, channel: int, data) -> None:
        # Append incoming data to dataframe
        logging.info(f"Extracting element data from channel {channel}..")

        values = [
            data.stepName,
            data.stepNumber,
            data.substepNumber
        ]
        
        next_step = dict(zip(self.step_colums, values))
        self.elements = self.elements.append(next_step)

    def handle_device_connected(self, device_name: str) -> None:
        logging.info("Connected device is: " + device_name + ".")

    def handle_experiment_stopped(self, channel: int) -> None:
        logging.info(f"Experiment completed on channel {channel}.")
        self.app.quit()

    def upload_experiment(self, experiment) -> bool:
        # Internal function, to be run after the element (measurement) has been appended to the experiment

        logging.info("Uploading experiment to Squidstat..")
        error = self.handler.uploadExperimentToChannel(self.channel, experiment)

        if error != 0:
            logging.error("Failed to upload experiment to Squidstat: " + error.message())
            return False
        else:
            return True

    def trigger_experiment(self) -> bool:
        # Internal function, to be run after upload_experiment
        error = self.handler.startUploadedExperiment(self.channel)

        if error != 0:
            logging.error("Failed to start experiment: " + error.message())
            return False
        else:
            return True

    def run_experiment(self) -> bool:
        # Run an experiment on the potentiostat. Remember to define the experiment first, 
        # For instance using setup_potentiostaticEIS() or setup_CV().
        logging.info("Attempting to begin experiment..")

        if self.experiment is not None: 
            if self.sim is False:
                self.upload_experiment(self.experiment)
                self.trigger_experiment()
                self.app.exec_()
        else:
            logging.error("No experiment has been built!")

    def close_experiment(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Close the experiment on the potentiostat and release the Qt application.
        # Remember to call get_data() before calling this function to retrieve the data.

        ac_data, dc_data = self.get_data()
        self.reset_dataframes()

        # Close the experiment on the potentiostat and release the Qt application.
        logging.info("Closing experiment..")
        if self.sim is False:
            self.app.quit()

        return ac_data, dc_data

    def build_EIS_potentiostatic_experiment(
        self,
        start_frequency: float = 10000,
        end_frequency: float = 1000,
        points_per_decade: int = 10,
        voltage_bias: float = 0.0,
        voltage_amplitude: float = 0.1,
        number_of_runs: int = 1,
    ) -> None:
        #Perform an potentiostatic EIS experiment on the potentiostat

        logging.info("Setting up EIS Potentiostatic experiment..")
        logging.info(f"Frequency {start_frequency}-{end_frequency}Hz, {points_per_decade}pts/dec, {voltage_bias}V Bias, {voltage_amplitude}V Amplitude.")

        experiment = AisExperiment()
        element = AisEISPotentiostaticElement(
            start_frequency,
            end_frequency,
            points_per_decade,
            voltage_bias,
            voltage_amplitude,
        )

        self.experiment = experiment.appendElement(element, number_of_runs)
        
    def build_cyclic_voltammetry_experiment(
        self,
        start_voltage: float = 0,
        first_voltage_limit: float = 0.6,
        second_voltage_limit: float = 0,
        end_voltage: float = 0,
        scan_rate: float = 0.1,
        sampling_interval: float = 0.01,
        number_of_runs: int = 1,
    ) -> None:
        # Perform a cyclic voltammetry experiment on the potentiostat

        logging.info("Setting up Cyclic Voltammetry experiment..")
        logging.info(f"Voltage Range {start_voltage}-{end_voltage}V, {first_voltage_limit}V First Limit, {second_voltage_limit}V Second Limit, {scan_rate}V/s Scan Rate, {sampling_interval}s Intervals.")
        
        experiment = AisExperiment()
        element = AisCyclicVoltammetryElement(
            start_voltage,
            first_voltage_limit,
            second_voltage_limit,
            end_voltage,
            scan_rate,
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element, number_of_runs)

    def build_constant_current_experiment(
        self,
        hold_current: float = 0.01,
        sampling_interval: float = 0.01,
        duration: float = 10,
    ) -> None:
        #Perform a constant current experiment on the potentiostat

        logging.info("Setting up CC experiment..")
        logging.info(f"{hold_current}A Hold Current, {duration}s Duration, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisConstantCurrentElement(
            hold_current, 
            sampling_interval, 
            duration,
        )

        self.experiment = experiment.appendElement(element)

    def build_constant_potential_experiment(
        self,
        hold_voltage: float = 0.01,
        sampling_interval: float = 0.01,
        duration: float = 10,
    ) -> None:
        # Perform a constant potential experiment on the potentiostat

        logging.info("Setting up CV experiment..")
        logging.info(f"{hold_voltage}V Hold Voltage, {duration}s Duration, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisConstantPotElement(
            hold_voltage, 
            sampling_interval, 
            duration,
        )
        
        self.experiment = experiment.appendElement(element)

    def build_constant_power_experiment(
        self,
        is_charge: bool = False,
        power: float = 0.0,
        duration: float = 10,
        sampling_interval: float = 0.01,
    ) -> None:
        # Perform a constant power experiment on the potentiostat

        logging.info("Setting up Constant Power experiment..")
        if is_charge is True:
            sign = '+'
        else:
            sign = '-'

        logging.info(sign + f"{power}W Power, {duration}s Duration, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisConstantPowerElement(
            is_charge, 
            power, 
            duration, 
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element)

    def build_constant_resistance_experiment(
        self,
        resistance: float = 100.0,
        duration: float = 10,
        sampling_interval: float = 0.01,
    ) -> None:
        # Perform a constant resistance experiment on the potentiostat

        logging.info("Setting up Constant Resistance experiment..")
        logging.info(f"{resistance}ohm Resistance, {duration}s Duration, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisConstantResistanceElement(
            resistance, 
            duration, 
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element)

    def build_DC_current_sweep_experiment(
        self,
        start_current: float = 0.1,
        end_current: float = 0.6,
        scan_rate: float = 0.1,
        sampling_interval: float = 0.01,
    ) -> None:
        # Perform a DC current sweep experiment on the potentiostat

        logging.info("Setting up DC Current Sweep experiment..")
        logging.info(f"Current Range {start_current}-{end_current}A, {scan_rate}V/s Scan Rate, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisDCCurrentSweepElement(
            start_current, 
            start_current, 
            scan_rate, 
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element)

    def build_DC_potential_sweep_experiment(
        self,
        start_voltage: float = 0.1,
        end_voltage: float = 0.6,
        scan_rate: float = 0.1,
        sampling_interval: float = 0.01,
    ) -> None:
        # Perform a DC potential sweep experiment on the potentiostat

        logging.info("Setting up DC Potential Sweep experiment..")
        logging.info(f"Potential Range {start_voltage}-{end_voltage}V, {scan_rate}V/s Scan Rate, {sampling_interval}s Intervals.")
        
        experiment = AisExperiment()
        element = AisDCPotentialSweepElement(
            start_voltage, 
            end_voltage, 
            scan_rate, 
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element)

    def build_diff_pulse_voltammetry_experiment(
        self,
        start_voltage: float = 0.1,
        end_voltage: float = 0.6,
        potential_step: float = 0.01,
        pulse_height: float = 0.01,
        pulse_width: float = 0.02,
        pulse_period: float = 0.2,
    ) -> None:
        # Perform a differential pulse voltammetry experiment on the potentiostat

        logging.info("Setting up Differential Pulse Voltammetry experiment..")
        logging.info(f"Potential Range {start_voltage}-{end_voltage}V, {potential_step}V Potential Step, {pulse_height}V Pulse Height, {pulse_width}s Pulse Width, {pulse_period}s Pulse Period.")

        experiment = AisExperiment()
        element = AisDiffPulseVoltammetryElement(
            start_voltage,
            end_voltage,
            potential_step,
            pulse_height,
            pulse_width,
            pulse_period,
        )

        self.experiment = experiment.appendElement(element)

    def build_normal_pulse_voltammetry_experiment(
        self,
        start_voltage: float = 0.1,
        end_voltage: float = 0.6,
        potential_step: float = 0.01,
        pulse_width: float = 0.02,
        pulse_period: float = 0.2,
    ) -> None:
        # Perform a normal pulse voltammetry experiment on the potentiostat

        logging.info("Setting up Normal Pulse Voltammetry experiment..")
        logging.info(f"Potential Range {start_voltage}-{end_voltage}V, {potential_step}V Potential Step, {pulse_width}s Pulse Width, {pulse_period}s Pulse Period.")

        experiment = AisExperiment()
        element = AisNormalPulseVoltammetryElement(
            start_voltage,
            end_voltage,
            potential_step,
            pulse_width,
            pulse_period,
        )

        self.experiment = experiment.appendElement(element)

    def build_square_wave_experiment(
        self,
        start_voltage: float = 0.1,
        first_voltage_limit: float = 0.6,
        second_voltage_limit: float = 0.1,
        end_voltage: float = 0.01,
        scan_rate: float = 0.1,
        sampling_interval: float = 0.01,
        number_of_runs: int =1,
    ) -> None:
        # Perform a square wave voltammetry experiment on the potentiostat

        logging.info("Setting up Square Wave Voltammetry experiment..")
        logging.info(f"Voltage Range {start_voltage}-{end_voltage}V, {first_voltage_limit}V First Limit, {second_voltage_limit}V Second Limit, {scan_rate}V/s Scan Rate, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisSquareWaveVoltammetryElement(
            start_voltage,
            first_voltage_limit,
            second_voltage_limit,
            end_voltage,
            scan_rate,
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element, number_of_runs)

    def build_EIS_galvanostatic_experiment(
        self,
        start_frequency: float = 10000,
        end_frequency: float = 1000,
        points_per_decade: int = 10,
        current_bias: float = 0.0,
        current_amplitude: float = 0.1,
        number_of_runs: int = 1,
    ) -> None:
        # Perform an galvanostatic EIS experiment on the potentiostat

        logging.info("Setting up EIS Galvanostatic experiment..")
        logging.info(f"Frequency {start_frequency}-{end_frequency}Hz, {points_per_decade}pts/dec, {current_bias}A Bias, {current_amplitude}A Amplitude.")

        experiment = AisExperiment()
        element = AisEISGalvanostaticElement(
            start_frequency,
            end_frequency,
            points_per_decade,
            current_bias,
            current_amplitude,
        )

        self.experiment = experiment.appendElement(element, number_of_runs)

    def build_OCP_experiment(
            self, 
            duration: float = 10, 
            sampling_interval: float = 0.01
    ) -> None:
        # Perform an open circuit potential experiment on the potentiostat

        logging.info("Setting up Open Circuit Potential experiment..")
        logging.info(f"{duration}s Duration, {sampling_interval}s Intervals.")

        experiment = AisExperiment()
        element = AisOpenCircuitElement(
            duration, 
            sampling_interval,
        )

        self.experiment = experiment.appendElement(element)