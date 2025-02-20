import logging
import math
import sys
import time

import numpy as np
import serial

logging.basicConfig(level = logging.INFO)

class pipette:
    def __init__(self, COM: str, sim: bool = False, maximum_power: float = 250, charge_pressure: float = 30, Kp: int = 2, Ki: int = 20, Kd: int = 0) -> None:
        self.sim = sim

        self.max_dose = 200 # ul
        self.max_pressure = 160 # mbar
        self.charge_pressure = charge_pressure # mbar
        self.max_power = maximum_power #mW

        self.pressure_error_criteria = 1.0 # roughly 2ul

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

            self.gauge = self.get_gauge() #mbar

        else:
            logging.info("No serial connection to pipette established.")
            self.gauge = 0 #mbar

        logging.info(f"Disc pump gauge pressure set as {self.gauge}mbar.")

    def get_data(self) -> str:
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode()
    
    def get_max_dose(self) -> float:
        return self.max_dose
    
    def get_charge_pressure(self) -> float:
        return self.charge_pressure
    
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

    def get_gauge(self) -> float:
        return self.register_read(39)
    
    def get_pressure(self) -> float:
        return self.register_read(39) - self.gauge

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
            self.check_pressure(0)

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

        value = round(value + self.gauge, 3) # Increment by gauge pressure such that set_pressure(0) turns pump off

        if value > self.max_pressure:
            logging.error(f"Requested pressure of {value}mbar exceeds maximum.")
            logging.info(f"Target pressure reduced to maximum of {self.max_pressure}mbar.")

            value = self.max_pressure

        elif value < 0:
            logging.error(f"Requested pressure of {value}mbar is below zero.")
            logging.info("Target pressure set to 0mbar.")

            value = 0

        if self.register_write(23, value) is True:
            logging.info(f"Pipette target gauge pressure set to {value - self.gauge}mbar.")
        else:
            logging.error(f"Failed to set pipette target gauge pressure to {value - self.gauge}mbar.")
            sys.exit()

        if check is True:
            self.check_pressure(value - self.gauge)

    def charge_pipette(self) -> None:
        self.set_pressure(self.charge_pressure, check=True)

    def get_poly_equation(self, xi: float, diff: float, T: float, N: int) -> np.ndarray:
        time = np.linspace(0, T, N)

        # polynomial coefficients
        C_0 = xi
        C_3 = diff * 10 / pow(T, 3)
        C_4 = diff * -15 / pow(T, 4)
        C_5 = diff * 6 / pow(T, 5)

        return C_0 + C_3 * np.power(time, 3) + C_4 * np.power(time, 4) + C_5 * np.power(time, 5)

    def aspirate(self, aspirate_volume: float, aspirate_constant: float, aspirate_speed: float, poly: bool = False, check: bool = True) -> None:
        charge_pressure = self.get_pressure()

        if aspirate_volume > self.max_dose:
            logging.error(f"Requested dose of {aspirate_volume}uL exceeds maximum.")
            logging.info(f"Dose reduced to maximum of {self.max_dose}uL.")

            aspirate_volume = self.max_dose

        elif aspirate_volume < 0:
            logging.error(f"Requested dose of {aspirate_volume}uL is below zero.")
            logging.info("Dose set to 0uL.")

            aspirate_volume = 0
        
        diff = aspirate_constant * aspirate_volume
        aspirate_pressure = diff + charge_pressure # Pressure diff is from charge pressure

        if aspirate_speed != 0:
            rise_time = aspirate_volume / aspirate_speed # Seconds

            logging.info(f"Rising to aspiration pressure of {aspirate_pressure}mbar in {rise_time}s, from charged pressure of {charge_pressure}mbar.")
            N = math.ceil(rise_time / (2.3 * self.time_resolution)) + 2 # Nyquist * smallest time step of SPM (no point changing pressure at any higher frequency)
            dT = rise_time / (N-1)

            if N > 2:
                if poly is False:
                    path = np.linspace(charge_pressure, aspirate_pressure, N)
                else:
                    path = self.get_poly_equation(charge_pressure, diff, rise_time, N)

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
        self.set_pressure(0) # To dispense as quickly as possible to remove all liquid
        self.pump_off(check)

    def aspiration_test(self) -> None:
        # Used for testing only => No logging
        if self.ser.isOpen() is False:
                self.ser.open()

        try:
            charge_pressure = float(input("Enter charge pressure (mbar): "))
        except Exception as ex:
            charge_pressure = self.charge_pressure
            print(ex)
            print(f"Charge Pressure set to {charge_pressure}mbar.")

        # Charge pipette
        self.pump_on()
        self.set_pressure(charge_pressure, check=True)
        print("Pipette charged.")

        try:
            aspirate_volume = float(input("Enter Aspirate Volume (uL): "))
        except Exception as ex:
            aspirate_volume = 10
            print(ex)
            print(f"Aspirate Volume set to {aspirate_volume}uL.")

        try:
            aspirate_constant = float(input("Enter Aspirate Constant (mbar/uL): "))
        except Exception as ex:
            aspirate_constant = 0.5
            print(ex)
            print(f"Aspirate Constant set to {aspirate_constant}mbar/uL.")

        try:
            aspirate_speed = float(input("Enter Aspirate Speed (uL/s): "))
        except Exception as ex:
            aspirate_speed = 10
            print(ex)
            print(f"Aspirate Speed set to {aspirate_speed}uL/s.")

        # Aspirate pipette
        self.aspirate(aspirate_volume, aspirate_constant, aspirate_speed, poly=False, check=True)

        print("Aspiration complete.")
        print(f"{aspirate_volume}uL extracted.")

        _ = input("Press any key to Dispense")

         # Dispense pipette
        self.dispense()
        print("Dispense complete.")

        self.close_ser()