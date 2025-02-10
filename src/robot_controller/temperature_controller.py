import logging
import random
import sys
import time

import matplotlib.pyplot as plt
import numpy as np
import serial

logging.basicConfig(level = logging.INFO)

# To communicate with: https://lairdthermal.com/products/product-temperature-controllers/tc-xx-pr-59-temperature-controller

class peltier:
    def __init__(self, COM: str, sim: bool = False) -> None:
        self.sim = sim

        #self.ready_chars = '\r' + '\n' + '>' + ' '

        self.max_temp = 60 #degsC
        self.min_temp = -40 #degsC

        self.input_voltage = 18.0 #V
        self.max_current = 11.0 #A
        self.minimum_current = 6.0 #A, 2x peltiers at 100%

        self.fan_current = 0.5 #A
        self.fan_voltage = 12.0

        # Thermisistor Steinhart coefficients NTC1
        self.A_coeff_1 = 1.396917e-3
        self.B_coeff_1 = 2.378257e-4
        self.C_coeff_1 = 9.372652e-8

        # Thermisistor Steinhart coefficients NTC2
        self.A_coeff_2 = 1.0373e-3
        self.B_coeff_2 = 2.3317e-4
        self.C_coeff_2 = 8.3896e-8

        # Steady state temperature
        self.allowable_error = 0.5 #degsC
        self.steady_state = 10 #s
        self.timeout = 1800 #s

        # Heating/Normal control
        self.heat_Kp = 12
        self.heat_Ki = 0.1
        self.heat_Kd = 0
        self.heat_tc_max = 60

        # Sub-Zero Cooling control
        self.cool_Kp = 12
        self.cool_Ki = 0.1
        self.cool_Kd = 0
        self.cool_tc_max = 100

        self.temp_threshold = 8 #degsC, to set heating or cooling parameters
        self.dead_band = 8 #+-% to prevent rapid switching

        if self.sim is False:
            logging.info("Configuring temperature controller serial port..")
            self.ser = serial.Serial(COM) 
            self.ser.baudrate = 115200
            self.ser.bytesize = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1

            logging.info("Attempting to open temperature controller serial port..")

            if self.ser.isOpen() is False:
                self.ser.open()
            

            # Unknown if this occurs on start up!
            if self.handshake() is True:
                logging.info("Serial connection to temperature controller established.")
            else:
                logging.error("Failed to establish serial connection to temperature controller.")   
                sys.exit()

            if self.check_peltiers() is True:
                logging.info("Peltier current draw is as high as expected.")
            else:
                logging.error("Check peltiers for possible damage before attempting to initialise the regulator again.")
                sys.exit()



            if self.set_regulator_mode() is True:
                logging.info("Temperature regulator PID mode successfully configured.")
            else:
                logging.error("Temperature regulator configuration failed.")
                sys.exit()

            if self.set_tc_dead_band() is True:
                logging.info("Temperature regulator dead band successfully configured.")
            else:
                logging.error("Temperature regulator dead band configuration failed.")
                sys.exit()

            if self.set_alarm_settings() is True:
                logging.info("Temperature regulator alarm settings successfully configured.")
            else:
                logging.error("Temperature regulator alarm configuration failed.")
                sys.exit()

            if self.configure_main_sensor() is True:
                logging.info("Temperature Sensor #1 successfully configured.")
            else:
                logging.error("Temperature Sensor #1 configuration failed.")
                sys.exit()

            if self.configure_heat_sink_sensor() is True:
                logging.info("Temperature sensor #2 successfully configured.")
            else:
                logging.error("Temperature sensor #2 configuration failed.")
                sys.exit()

            if self.set_heat_sink_steinhart_coeffs() is True:
                logging.info("Successfully updated steinhard coefficients for temperature sensor #2.")
            else:
                logging.error("Failed to update steinhard coefficients for temperature sensor #2.")
                sys.exit()         

            if self.set_fan_modes() is True:
                logging.info("Temperature regulator Fan settings successfully configured.")
            else:
                logging.error("Temperature regulator Fan configuration failed.")
                sys.exit()      

        else:
            logging.info("No serial connection to temperature controller established.")

    def close_ser(self) -> None:
        if self.sim is False:
            self.ser.close()

    def get_data(self) -> str:
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode().rstrip()
    
    def handshake(self) -> bool:
        msg = "$LI"

        # returns '18245 TC-XX-PR-59 REV2.6'

        if self.sim is False:
            self.ser.write((msg+'\r').encode('ascii'))

            repeat = self.get_data()
            info = self.get_data()
            if info.split(" ")[1] == "TC-XX-PR-59" and repeat == msg:
                logging.info("Serial device located: " + info)
                return True
            else:
                return False

    def set_run_flag(self) -> None:
        msg = "$W"

        if self.sim is False:
            self.ser.write((msg+'\r').encode('ascii'))
            repeat = self.get_data().split(" ")[1]

            if self.get_data() == "Run" and repeat == msg:
                logging.info("Temperature controller Run flag set.")
            else:
                logging.error("Failed to set temperature controller Run flag.")

    def clear_run_flag(self) -> None:
        msg = "$Q"

        if self.sim is False:
            self.ser.write((msg+'\r').encode('ascii'))
            repeat = self.get_data().split(" ")[1]

            if self.get_data() == "Stop" and repeat == msg:
                logging.info("Temperature controller Run flag cleared.")
            else:   
                logging.error("Failed to clear temperature controller Run flag.")

    def get_status(self) -> None:
        msg = "$S"

        if self.sim is False:
            self.ser.write((msg+'\r').encode('ascii'))
            repeat = self.get_data().split(" ")[1]

            if repeat == msg:
                logging.info("Temperature controller status returned.")
            else:   
                logging.error("Failed to return temperature controller status.")

            logging.info("Status: " + self.get_data())

    def clear_status(self) -> None:
        msg = "$SC"

        if self.sim is False:
            self.ser.write((msg+'\r').encode('ascii'))
            repeat = self.get_data().split(" ")[1]

            if repeat == msg:
                logging.info("Temperature controller status cleared.")
            else:   
                logging.error("Failed to clear temperature controller status.")

            logging.info("Status: " + self.get_data())
        
    def register_write(self, REGISTER_NUMBER: int, VALUE: int) -> bool:
        # Command set is built up by: Start char - command - data - stop char
        # Start Char "$""
        # Command "R41=" - register reference =
        # Data "23.5" for example
        # Stop char <CR> - carriage return '0x0D' or '\r'

        # When the regulator is ready to receive next command
        # we get following ASCII chars: 'CR' 'LF' '>' 'SP' 
        # HEX 0D 0A 3E 20

        # Each character sent to the regulator is echoed back from the regulator
        # and when the end of the command (CR) has been sent
        # the regulator responds with ASCII chars: 'CR' 'LF' followed by response as the table below. 
        # Note that after each command and response, following string is sent in ASCII chars: 
        # 'CR' 'LF' '>' 'SP' (HEX 0D 0A 3E 20).
        # if sent command is unknown, the regulator responds with '?' + command
        # Note commands are case sensitive

        # For RXX=, if data=int response is <Downloaded data>, if foat <no response>

        if self.sim is False:
            msg = f"$R{REGISTER_NUMBER}={VALUE}"

            self.ser.write((msg+'\r').encode('ascii'))

            repeat = self.get_data().split(" ")[1]
            response = self.get_data()
            if (response == f"{VALUE}" or response == '') and repeat == msg:
                #logging.info(f"Successfully wrote to R{REGISTER_NUMBER}.")
                return True
            else:
                logging.error(f"Failed to write to R{REGISTER_NUMBER}.")
                return False
                            
        else:
            return True
        
    def register_read(self, REGISTER_NUMBER: int) -> float:
        if self.sim is False:
            msg = f"$R{REGISTER_NUMBER}?"
            self.ser.write((msg+'\r').encode('ascii'))

            repeat = self.get_data().split(" ")[1]
            if repeat != msg:
                logging.error(f"Failed to read R{REGISTER_NUMBER}.")

            return float(self.get_data())
        else:
            return random.uniform(self.min_temp, self.max_temp)
        
    def set_regulator_mode(self, mode: int = 6) -> bool:
        # 1 = Power 
        # 2 = ON/OFF
        # 3 = P 
        # 4 = PI 
        # 5 = PD 
        # 6 = PID 
        
        return self.register_write(13, mode)

    def clamp(self, n: int | float , minn: int | float, maxn: int | float) -> int | float:
        if n < minn:
            return minn
        elif n > maxn:
            return maxn
        else:
            return n
        
    def set_max_tc(self, max: float = 100) -> bool:
        # 100 is default register value
        return self.register_write(6, self.clamp(max, 0, 100))
        
    def set_tc_dead_band(self) -> bool:
        return self.register_write(7, self.clamp(self.dead_band, 0, 100))

        # Dead band is limiting the signal around zero value. 
        # Good to adjust if we do not like fast switching from one voltage direction to the other
        # This helps to save the life of the peltier modules

    def set_pid_parameters(self, p: float, i: float, d: float, i_lim: float = 100) -> bool:
        if (self.register_write(1, p) is True) and (self.register_write(2, i) is True) and (self.register_write(3, d) is True) and (self.register_write(8, self.clamp(i_lim, 0, 100)) is True):
            return True
        else:
            return False

    def set_low_pass(self, low_pass_a: float = 2, low_pass_b: float = 3) -> bool:
        # Default controller values for now => no need to set
        if self.register_write(4, abs(low_pass_a)) is True and self.register_write(5, abs(low_pass_b)) is True:
            return True
        else:
            return False
        
    def set_power(self, power: float = 0) -> bool:
        return self.register_write(0, power)

    def set_temperature(self, temp: float) -> None:
        if temp < self.temp_threshold:
            if (self.set_pid_parameters(self.cool_Kp, self.cool_Ki, self.cool_Kd) is True) and (self.set_max_tc(self.cool_tc_max) is True):
                logging.info("Temperature controller PID settings set to cooling mode.")
            else:
                logging.error("Failed to set temperature controller PID settings to cooling mode.")
                sys.exit()
        else:
            if (self.set_pid_parameters(self.heat_Kp, self.heat_Ki, self.heat_Kd) is True) and (self.set_max_tc(self.heat_tc_max) is True):
                logging.info("Temperature controller PID settings set to heating mode.")
            else:
                logging.error("Failed to set temperature controller PID settings to heating mode.")
                sys.exit()

        if self.register_write(0, self.clamp(temp, self.min_temp, self.max_temp)) is True:
            logging.info(f"Peltier target temperature set to {temp}degsC.")
        else:
            logging.error("Failed to set peltier target temperature.")

    def set_fan_modes(self, mode: int = 4) -> bool:
        # Always OFF = 0
        # Always ON = 1
        # Cool = 2
        # Heat = 3
        # Cool / Heat = 4, on when main output is non zero (reg[106])

        if (self.register_write(16, mode) is True) and (self.register_write(23, mode) is True) and (self.register_write(22, self.fan_voltage) is True) and (self.register_write(29, self.fan_voltage) is True):
            return True
        else:
            return False
        
    def set_alarm_settings(self) -> bool:
        # Set alarms for over and under voltage
        # Main current over
        # Fan current over
        if (self.register_write(45, self.input_voltage + 1) is True) and (self.register_write(46, self.input_voltage - 1) is True) and (self.register_write(47, self.max_current) is True) and (self.register_write(49, self.fan_current) is True) and (self.register_write(51, self.fan_current) is True):
            return True
        else:
            return False
        
    def configure_main_sensor(self, mode: int = 12) -> bool:
        # 2 = to activate Steinhart calculation
        # 3 = to activate Zoom mode (internal control of digital pot). Have this bit set to achieve maximal resolution.
        # 4 = to activate PT mode 

        # To revisit best mode and values to use

        # Also set alarms on over and under

        if (self.register_write(55, mode) is True) and (self.register_write(71, self.max_temp + 5) is True) and (self.register_write(72, self.min_temp - 5) is True):
            return True
        else:
            return False
        
    def configure_heat_sink_sensor(self, mode: int = 12) -> bool:
        # 2 = to activate Steinhart calculation
        # 3 = to activate Zoom mode (internal control of digital pot). Have this bit set to achieve maximal resolution.
        # 4 = to activate PT mode 

        # To revisit best mode and values to use

        # Also set alarms on over and under

        if (self.register_write(56, mode) is True) and (self.register_write(73, self.max_temp + 5) is True) and (self.register_write(74, self.min_temp - 5) is True):
            return True
        else:
            return False
        
    def set_main_steinhart_coeffs(self) -> list[float]:
        if (self.register_write(59, self.A_coeff_1) is True) and (self.register_write(60, self.B_coeff_1) is True) and (self.register_write(61, self.C_coeff_1) is True):
            return True
        else:
            return False
        
    def set_heat_sink_steinhart_coeffs(self) -> list[float]:
        if (self.register_write(62, self.A_coeff_2) is True) and (self.register_write(63, self.B_coeff_2) is True) and (self.register_write(64, self.C_coeff_2) is True):
            return True
        else:
            return False
    
    def get_t1_mode(self) -> int:
        return self.register_read(55)
    
    def get_t2_mode(self) -> int:
        return self.register_read(65)
                
    def get_tc_value(self) -> float:
        return self.register_read(106)
    
    def get_t1_value(self) -> float:
        return self.register_read(100)
    
    def get_t2_value(self) -> float:
        return self.register_read(101)
    
    def get_main_current(self) -> float:
        return self.register_read(152)
    
    def check_peltiers(self) -> bool:
        logging.info("Checking peltiers..")

        # Set to power mode
        if self.set_regulator_mode(mode=1) is False:
            logging.error("Temperature controller regulator configuration failed.")
            sys.exit()
        
        # Set power to 100
        if self.set_power(power=100) is True:
            logging.info("Regulator power set to 100%.")
        else:
            logging.error("Failed to set regulator power to 100%.")
            sys.exit()

        self.set_run_flag()

        time.sleep(1.0)
        current = self.get_main_current()

        self.clear_run_flag()

        if (abs(current) > self.minimum_current):
            return True
        else:
            logging.error(f"Peltier current draw of {current}A is lower than expected.")
            return False
    
    def wait_until_temperature(self, value: float, sample_rate: float = 2, plot: bool = False, plot_width: int = 100) -> bool:
        if self.sim is True:
            return True
        
        self.set_power(value)
        global_start = time.time()

        # Turn controller ON
        self.set_run_flag()

        while (time.time() - global_start) < self.timeout:                
            local_start = time.time()

            while (abs(value - self.get_t1_value()) < self.allowable_error) and (time.time() - local_start < self.steady_state):
                time.sleep(1 / sample_rate)

            # Check if steady state timeout reached
            end_time = time.time() - local_start
            if end_time >= self.steady_state:
                logging.info(f"Temperature controller successfully reached {value}degsC in {time.time() - global_start}s")
                logging.info(f"Final peltier current is {round(self.get_main_current(),2)}A.")

                # Turn controller OFF
                self.clear_run_flag()
                return True
            
            time.sleep(1 / sample_rate)
            
        logging.error(f"Temperature controller timed out trying to reach {value}degsC.")
        logging.info(f"Final peltier current is {round(self.get_main_current(),2)}A.")

        # Turn controller OFF
        self.clear_run_flag()
        return False
    
    def cycle_through_temperatures(self, start_temp: float = 60.0, end_temp: float = -40.0, points: int = 11, plot: bool = False) -> None:
        logging.info(f"Cycling through {points} temperatures from {start_temp}degsC to {end_temp}degsC.")

        for val in np.linspace(start_temp, end_temp, points, plot):
            if self.wait_until_temperature(val) is False:
                logging.error("Failed to cycle through temperature set points.")
                sys.exit()
    
    def plot_live_temperature_control(self, value: float, sample_rate: float = 2, plot_width: int = 100) -> bool:
        if self.sim is True:
            return True
        
        self.set_temperature(value)
        global_start = time.time()

        plt.ion()

        fig = plt.figure(figsize=(16, 10))
        ax = fig.add_subplot(111)
            
        plt.title(f"Target Temp: {value}degsC, Sample Rate: {sample_rate}Hz")
        plt.suptitle("Live Data:")
        plt.xlabel("Samples")
        plt.ylim([self.min_temp - self.max_temp, self.max_temp - self.min_temp])
        plt.grid(which="both")

        error = [0] * plot_width
        dT = [0] * plot_width
        drive = [0] * plot_width
        samples = range(1, plot_width+1)
        line1, = ax.plot(samples, error, 'r-', label="Temperature Error K")
        line2, = ax.plot(samples, drive, 'g-', label="Drive Power %")
        line3, = ax.plot(samples, dT, 'b-', label="dT K")
        plt.legend(loc="upper right")

        # Turn controller ON
        self.set_run_flag()

        while (time.time() - global_start) < self.timeout:
            
            # Append and loose first element
            control = self.get_t1_value()
            sink = self.get_t2_value()
            curr = self.get_main_current()
            plt.title(f"Target Temp: {value}degsC, Sample Rate: {sample_rate}Hz")
            plt.suptitle(f"Live Data: Control Temperature = {round(control,2)}degsC, Heat Sink Temperature = {round(sink,2)}degsC, Main Current = {round(curr,2)}A, Elapsed Time = {round(time.time() - global_start,2)}s")

            error.append(value - control)
            error = error[-plot_width:]

            drive.append(self.get_tc_value())
            drive = drive[-plot_width:]

            dT.append(abs(control - sink))
            dT = dT[-plot_width:]

            line1.set_ydata(error)
            line2.set_ydata(drive)
            line3.set_ydata(dT)

            fig.canvas.draw()
            fig.canvas.flush_events()
                
            local_start = time.time()

            while (abs(value - self.get_t1_value()) < self.allowable_error) and (time.time() - local_start < self.steady_state):
                time.sleep(1 / sample_rate)

            # Check if steady state timeout reached
            end_time = time.time() - local_start
            if end_time >= self.steady_state:
                logging.info(f"Temperature controller successfully reached {value}degsC in {time.time() - global_start}s")
                logging.info(f"Final peltier current is {round(self.get_main_current(),2)}A.")

                # Turn controller OFF
                self.clear_run_flag()
                return True
            
            time.sleep(1 / sample_rate)
            
        logging.error(f"Temperature controller timed out trying to reach {value}degsC.")
        logging.info(f"Final peltier current is {round(self.get_main_current(),2)}A.")

        # Turn controller OFF
        self.clear_run_flag()
        return False

                