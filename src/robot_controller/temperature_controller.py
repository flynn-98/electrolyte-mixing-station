import logging
import sys

import serial

logging.basicConfig(level = logging.INFO)

# To communicate with: https://lairdthermal.com/products/product-temperature-controllers/tc-xx-pr-59-temperature-controller

class peltier:
    def __init__(self, COM: str, sim: bool = False, Kp: float = 1, Ki: float = 1, Kd: float = 0) -> None:
        self.sim = sim

        self.ready_chars = '\r' + '\n' + '>' + ' '

        self.max_temp = 60 #degsC
        self.min_temp = -40 #degsC

        self.input_voltage = 12 #V

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
            if self.get_data() == self.ready_chars:
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
                logging.info("Temperature controller regulation settings successfully configured.")
            else:
                logging.error("Temperature controller regulation configuration failed.")
                sys.exit()

            if self.set_tc_parameters() is True:
                logging.info("Temperature controller Tc settings successfully configured.")
            else:
                logging.error("Temperature controller Tc configuration failed.")
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

        return self.ser.readline().decode()
    
    def send_chars(self, msg: str) -> bool: 
        last = len(msg) - 1

        for i, character in enumerate(msg):
                # Char by Char communication which is echoed back
                self.ser.write(character.encode('ascii'))

                if i < last:
                    received = self.get_data()
                    if (received != character):
                        logging.error("Bad char received by temperature controller: " + character + " sent but " + received + "received.")
                        return False
                else:
                    # Ready chars sent once stop char (\r) received
                    if (received != self.ready_chars):
                        logging.error("Register write not received by temperature controller.")
                        return False
                    else:
                        return True

    def set_run_flag(self) -> None:
        msg = "$W" + '\r'

        if self.sim is False:
            if self.send_chars(msg) is True:
                logging.info("Temperature controller Run flag set.")
            else:
                logging.error("Failed to set temperature controller Run flag.")

    def clear_run_flag(self) -> None:
        msg = "$Q" + '\r'

        if self.sim is False:
            if self.send_chars(msg) is True:
                logging.info("Temperature controller Run flag cleared.")
            else:   
                logging.error("Failed to clear temperature controller Run flag.")
        
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
            msg = f"$R{REGISTER_NUMBER}={VALUE}" + '\r'

            if self.send_chars(msg) is True:
                logging.info(f"Successfully wrote to Register {REGISTER_NUMBER}.")
            
            response = self.get_data()
            if response == "Downloaded data" or response == "no response":
                return True
            else:
                logging.error("Integer data not received by temperature controller.")
                return False
                            
        else:
            return True
        
    def register_read(self, REGISTER_NUMBER: int) -> float:
        if self.sim is False:
            msg = f"$R{REGISTER_NUMBER}?" + '\r'

            if self.send_chars(msg) is True:
                logging.info("Successfully read data from temperature controller.")

            data = self.get_data()
            return float(data)
        
        else:
            return 0.0
        
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

    def set_low_pass(self, low_pass_a: float, low_pass_b: float) -> bool:
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
        # Always ON = 1
        # Always OFF = 2
        # Cool / Heat = 4, on when main output is non zero (reg[106])

        if (self.register_write(16, mode) is True) and (self.register_write(23, mode) is True) and (self.register_write(22, self.input_voltage) is True) and (self.register_write(29, self.input_voltage) is True):
            return True
        else:
            return False
        
    def configure_main_sensor(self, mode: int = 2) -> bool:
        # 2 = to activate Steinhart calculation
        # 3 = to activate Zoom mode (internal control of digital pot). Have this bit set to achieve maximal resolution.
        # 4 = to activate PT mode 

        # To revisit best mode and values to use

        return self.register_write(55, mode)
        
    def get_tc_value(self) -> float:
        return self.register_read(106)