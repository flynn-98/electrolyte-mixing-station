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
    def __init__(self, COM: str, sim: bool = False, Kp: float = 5, Ki: float = 2, Kd: float = 1) -> None:
        self.sim = sim

        #self.ready_chars = '\r' + '\n' + '>' + ' '

        self.max_temp = 60 #degsC
        self.min_temp = -40 #degsC

        self.input_voltage = 12.0 #V
        self.max_current = 9.0 #A
        self.fan_current = 0.5 #A
        self.fan_voltage = 12.0

        # Thermisistor Steinhart coefficients
        self.A_coeff = 1.396917e-3
        self.B_coeff = 2.378257e-4
        self.C_coeff = 9.372652e-8

        # Steady state temperature
        self.allowable_error = 0.5 #degsC
        self.steady_state = 2 #s
        self.timeout = 600 #s

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

            if self.set_pid_parameters(Kp, Ki, Kd) is True:
                logging.info("Temperature controller PID settings successfully configured.")
            else:
                logging.error("Temperature controller PID configuration failed.")
                sys.exit()

            if self.set_regulator_mode() is True:
                logging.info("Temperature controller regulator settings successfully configured.")
            else:
                logging.error("Temperature controller regulator configuration failed.")
                sys.exit()

            if self.set_tc_parameters() is True:
                logging.info("Temperature controller Tc settings successfully configured.")
            else:
                logging.error("Temperature controller Tc configuration failed.")
                sys.exit()

            if self.set_alarm_settings() is True:
                logging.info("Temperature controller alarm settings successfully configured.")
            else:
                logging.error("Temperature controller alarm configuration failed.")
                sys.exit()

            if self.configure_main_sensor() is True:
                logging.info("Temperature controller Sensor1 settings successfully configured.")
            else:
                logging.error("Temperature controller Sensor1 configuration failed.")
                sys.exit()   

            if self.set_fan_modes() is True:
                logging.info("Temperature controller Fan settings successfully configured.")
            else:
                logging.error("Temperature controller Fan configuration failed.")
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
        
    def set_tc_parameters(self, max_percent: int = 100, dead_band: int = 5) -> bool:
        if (self.register_write(6, self.clamp(max_percent, 0, 100)) is True) and (self.register_write(7, self.clamp(dead_band, 0, 50)) is True):
            return True
        else:
            return False

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

    def set_temperature(self, temp: float) -> None:
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
        
    def set_steinhart_coeffs(self) -> list[float]:
        if (self.register_write(59, self.A_coeff) is True) and (self.register_write(60, self.B_coeff) is True) and (self.register_write(61, self.C_coeff) is True):
            return True
        else:
            return False
        
    def get_steinhart_coeffs(self) -> list[float]:
        A = self.register_read(59)
        B = self.register_read(60)
        C = self.register_read(61)

        return [A, B, C]
    
    def get_t1_mode(self) -> int:
        return self.register_read(55)
                
    def get_tc_value(self) -> float:
        return self.register_read(106)
    
    def get_t1_value(self) -> float:
        return self.register_read(100)
    
    def wait_until_temperature(self, value: float, sample_rate: float = 2, plot: bool = False, plot_width: int = 100) -> bool:
        self.set_temperature(value)
        global_start = time.time()

        if self.sim is True:
            return True

        if plot is True:
            plt.ion()

            fig = plt.figure(figsize=(14, 8))
            ax = fig.add_subplot(111)
            
            plt.title(f"Target Temp: {value}degsC, Sample Rate: {sample_rate}Hz")
            plt.xlabel("Samples")
            plt.ylabel("Error /degsC")
            plt.ylim([self.min_temp - self.max_temp, self.max_temp - self.min_temp])
            plt.grid(True)

            error = [0] * plot_width
            samples = range(1, plot_width+1)
            line1, = ax.plot(samples, error, 'r-')

        while (time.time() - global_start) < self.timeout and self.sim is False:

            if plot is True:
                # Append and loose first element
                error.append(value - self.get_t1_value())
                error = error[-plot_width:]

                line1.set_ydata(error)
                fig.canvas.draw()
                fig.canvas.flush_events()
                
            local_start = time.time()

            while (abs(value - self.get_t1_value()) < self.allowable_error) and (time.time() - local_start < self.steady_state):
                time.sleep(1 / sample_rate)

            # Check if steady state timeout reached
            end_time = time.time() - local_start
            if end_time >= self.steady_state:
                logging.info(f"Temperature controller successfully reached {value}degsC in {end_time}s.")
                return True
            
            time.sleep(1 / sample_rate)
            
        logging.error(f"Temperature controller timed out trying to reach {value}degsC.")
        return False
    
    def cycle_through_temperatures(self, start_temp: float = 60.0, end_temp: float = -20.0, points: int = 9) -> None:
        logging.info(f"Cycling through {points} temperatures from {start_temp}degsC to {end_temp}degsC.")

        for val in np.linspace(start_temp, end_temp, points):
            if self.wait_until_temperature(val) is False:
                logging.error("Failed to cycle through temperature set points.")
                sys.exit()

                