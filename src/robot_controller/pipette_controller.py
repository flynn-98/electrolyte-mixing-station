import logging
import math
import sys
import time

import numpy as np
import serial

logging.basicConfig(level = logging.INFO)

class pipette:
    def __init__(self, COM: str, sim: bool = False, maximum_power: float = 275, charge_pressure: float = 30, Kp: int = 1, Ki: int = 20, Kd: int = 0) -> None:
        self.sim = sim

        self.max_dose = 200 # ul
        self.min_dose = 1.0 # ul
        self.calibrated_grad = 2.7 # ul/mbar

        self.max_pressure = 160 # mbar

        self.charge_pressure = charge_pressure # mbar
        self.max_power = maximum_power #mW

        self.pressure_error_criteria = 0.5 # roughly 1ul

        self.timeout = 5 # Maximum rise/fall time (s)
        self.time_resolution = 0.02 # s

        if self.sim is False:
            logging.info("Configuring pipette serial port..")
            self.ser = serial.Serial(COM) 
            self.ser.baudrate = 115200 
            self.ser.bytesize = 8 
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1 

            logging.info("Attempting to open pipette serial port..")

            if self.ser.isOpen() is False:
                self.ser.open()

            if self.configure_pump() is True:
                logging.info("Disc pump successfully initialised.")
            else:
                logging.error("Disc pump initialisation failed!")
                sys.exit()
            
            if self.configure_pid_settings() is True:
                logging.info("Disc pump drive mode succesfully configured.")
            else:
                logging.error("Disc pump drive mode configuration failed.")
                sys.exit()

            if self.configure_pid_constants(Kp, Ki, Kd) is True:
                logging.info("Disc pump PID settings succesfully configured.")
            else:
                logging.error("Disc pump PID configuration failed.")
                sys.exit()

            self.gauge = self.get_pressure() #mbar

            if (self.gauge > self.charge_pressure * 0.15):
                logging.error("Disc pump gauge pressure is greater than 15% of charge pressure.")
                logging.info("Attempting to relieve pressure..")

                self.blow_out_pipette()
                self.gauge = self.get_pressure() #mbar

        else:
            logging.info("No serial connection to pipette established.")
            self.gauge = 0 #mbar

        logging.info(f"Disc pump gauge pressure is {self.gauge}mbar.")

    def get_data(self) -> str:
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode()
    
    def get_aspiration_pressure(self, volume: float, scalar: float = 1.0) -> float:
        # Constant as function of volume (1/2.64 = 0.38mbar/ul)
        if (volume >= self.min_dose * 2):
            return round(scalar * (volume - self.min_dose) / self.calibrated_grad, 3)
        else:
            return round(volume / self.calibrated_grad, 3)
    
    def register_write(self, REGISTER_NUMBER: int, VALUE: float) -> bool:
        # The PCB responds to “write” commands by echoing the command back. 
        # This response should be read and checked by the controlling software to confirm 
        # that the command has been received correctly. If the command causes an error, 
        # or is not received at all, the PCB does not respond. 

        msg = f"#W{REGISTER_NUMBER},{VALUE}" + '\n'
     
        if self.sim is False:
            self.ser.write(msg.encode('ascii'))

            if (self.get_data() == msg):
                return True
            else:
                return False
        else:
            return True
        
    def register_read(self, REGISTER_NUMBER: int) -> float:
        # R3 = Drive voltage
        # R4 = Drive current
        # R5 = Drive power
        # R6 = Drive frequency
        # R39 = Pressure reading

        msg = f"#R{REGISTER_NUMBER}" + '\n'
        if self.sim is False:
            self.ser.write(msg.encode('ascii'))

            data = self.get_data()

            return float(data.split(",")[1])
        else:
            return self.gauge

    def close_ser(self) -> None:
        logging.info("Closing serial connection to pipette.")
        if self.sim is False:
            self.pump_off(check=False)
            if self.ser.isOpen():
                self.ser.close()

    def configure_pump(self) -> bool:
        # Configure pump registers
        # R0 -> 0/1 = Disable/Enable pump
        # R1 -> var = Maximum power (mW)
        # R2 -> 0 = Disable stream mode

        if (self.register_write(0,0) is True) and (self.register_write(1,self.max_power) is True) and (self.register_write(2,0) is True):
            return True
        else:
            return False
        
    def configure_pid_settings(self) -> bool:
        # Configure PID Settings
        # R10 -> 1 = PID mode (0 = manual)
        # R12 -> 0 = Setpoint source (register val)
        # R13 -> 5 = Input source (pressure sensor)
        # R33 -> 1 = Reset PID on pump enable

        if (self.register_write(10,1) is True) and (self.register_write(12,0) is True) and (self.register_write(13,5) is True) and (self.register_write(33,1) is True):
            return True
        else:
            return False
        
    def configure_pid_constants(self, Kp: float, Ki: float, Kd: float) -> bool:
        # Configure PID constants
            # R14 -> var = Kp
            # R15 -> var = Ki
            # R16 -> var = Integral limit (max power)
            # R17 -> var = Kd

            if (self.register_write(14,Kp) is True) and (self.register_write(15,Ki) is True) and (self.register_write(16,self.max_power) is True) and (self.register_write(17,Kd) is True):
                return True
            else:
                return False
    
    def get_pressure(self) -> float:
        return self.register_read(39)

    def pump_on(self) -> None:
        if self.register_write(0, 1) is True:
            logging.info("Pipette successfully turned on.")
        else:
            logging.error("Failed to turn on Pipette.")
            sys.exit()
    
    def pump_off(self, check: bool = False) -> None:
        if self.register_write(0, 0) is True:
            logging.info("Pipette successfully turned off.")
        else:
            logging.error("Failed to turn off Pipette.")
            sys.exit()

        if check is True:
            self.check_pressure(self.gauge)

    def get_power(self) -> float:
        power = self.register_read(5)

        if math.ceil(power) >= self.max_power:
            logging.error("Pipette at Maximum Power - Check for air flow restrictions!")
            self.pump_off()
            sys.exit()
        
        return power

    def check_pressure(self, target: float) -> None:
        if self.sim is False:
            start_time = time.time()

            pressure = self.get_pressure()
            error = target - pressure
            
            while (abs(error) > self.pressure_error_criteria):
                new_time = time.time() - start_time
                if (new_time > self.timeout):
                    logging.error(f"Pipette failed to reach pressure of {target}mbar in {self.timeout}s.")
                    logging.info(f"Final Pipette pressure is {self.get_pressure()}mbar @ {self.get_power()}mW.")
                    #self.pump_off()
                    #sys.exit()
                    break

                time.sleep(10 * self.time_resolution) # pause to prevent excessive interrupts
                
                pressure = self.get_pressure()
                error = target - pressure

            new_time = time.time() - start_time
            logging.info(f"Pipette reached {pressure}mbar in less than {math.ceil(new_time*1000)}ms.")

            # Delay to let system settle
            time.sleep(2)

            logging.info(f"Final Pump values: {self.get_pressure()}mbar @ {self.get_power()}mW.")

        else:
            logging.info(f"Pipette successfully reached {target}mbar.")
    
    def set_pressure(self, value: float, check: bool = False) -> None:
        # R/W register 23 for set point
        # mbar is default unit

        value = round(value, 2)
        
        if value > self.max_pressure:
            logging.error(f"Requested pressure of {value}mbar exceeds maximum.")
            logging.info(f"Target pressure reduced to maximum of {self.max_pressure}mbar.")

            value = self.max_pressure

        elif value < 0:
            logging.error(f"Requested pressure of {value}mbar is below zero.")
            logging.info("Target pressure set to 0mbar.")

            value = 0

        if self.register_write(23, value) is True:
            logging.info(f"Pipette target pressure set to {value}mbar.")
        else:
            logging.error(f"Failed to set pipette target pressure to {value}mbar.")
            sys.exit()

        if check is True:
            self.check_pressure(value)

    def charge_pipette(self, check: bool = True) -> None:        
        self.pump_on()
        self.set_pressure(self.charge_pressure, check=check)

    def blow_out_pipette(self) -> None:
        self.charge_pipette(check=False)
        time.sleep(0.5)
        self.pump_off()
        time.sleep(0.5)

    def aspirate(self, aspirate_volume: float, aspirate_scalar: float, aspirate_speed: float = 100.0, check: bool = True) -> None:
        if aspirate_volume > self.max_dose:
            logging.error(f"Requested dose of {aspirate_volume}uL exceeds maximum.")
            logging.info(f"Dose reduced to maximum of {self.max_dose}uL.")

            aspirate_volume = self.max_dose

        elif aspirate_volume < 0:
            logging.error(f"Requested dose of {aspirate_volume}uL is below zero.")
            logging.info("Dose set to 0uL.")

            aspirate_volume = 0
        
        #diff = aspirate_constant * aspirate_volume
        diff = self.get_aspiration_pressure(aspirate_volume, aspirate_scalar)
        aspirate_pressure = diff + self.charge_pressure # Pressure diff is from charge pressure

        if aspirate_speed != 0:
            rise_time = aspirate_volume / aspirate_speed # Seconds

            logging.info(f"Rising to aspiration pressure of {aspirate_pressure}mbar in {rise_time}s, from charged pressure of {self.charge_pressure}mbar.")
            N = math.ceil(rise_time / (2.3 * self.time_resolution)) + 2 # Nyquist * smallest time step of SPM (no point changing pressure at any higher frequency)
            dT = rise_time / (N-1)

            if N > 2:
                path = np.linspace(self.charge_pressure, aspirate_pressure, N)

                for set_point in path:
                    self.set_pressure(set_point)
                    time.sleep(dT)

                if check is True:
                    self.check_pressure(aspirate_pressure) # Only check final reading
            else:
                # Jump straight to aspirate pressure if speed is too high
                self.set_pressure(aspirate_pressure, check)

        else:
            # Jump straight to aspirate pressure if no speed given
            self.set_pressure(aspirate_pressure, check)
    
    def dispense(self, check: bool = True) -> None:
        self.pump_off(check)
        self.blow_out_pipette()