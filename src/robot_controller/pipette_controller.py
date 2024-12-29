import serial
import sys
import logging
import time

import numpy as np
import math

logging.basicConfig(level = logging.INFO)

class pipette:
    def __init__(self, COM, sim=False, maximum_power=500, Kp=10, Ki=12, Kd=0):
        self.sim = sim
        self.resolution = 0.415 # mbar resolution of sensor (12bit, 160mbar)
        self.timeout = 5 # Maximum rise/fall time (s)
        self.success_factor = 2 # Multiple of resolution to determine success of pressure control loop

        if self.sim == False:
            logging.info("Configuring pipette serial port..")
            self.ser = serial.Serial(COM) # COMXX
            self.ser.baudrate = 115200 # set Baud rate to 9600
            self.ser.bytesize = 8 # Number of data bits = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1 # Number of Stop bits = 1

            logging.info("Attempting to open pipette serial port..")

            if self.ser.isOpen() == False:
                self.ser.open()

            # Configure pump registers
            # R0 -> 0/1 = Disable/Enable pump
            # R1 -> var = Maximum power (mW)
            # R2 -> 0 = Disable stream mode

            if (self.register_write(0,0) == True) and (self.register_write(1,maximum_power) == True) and (self.register_write(2,0) == True):
                logging.info("Disc pump successfully initialised.")
            else:
                logging.error("Disc pump initialisation failed!")
                sys.exit()
            
            # Configure PID Settings
            # R10 -> 1 = PID mode (0 = manual)
            # R12 -> 0 = Setpoint source (register val)
            # R13 -> 5 = Input source (pressure sensor)
            # R33 -> 1 = Reset PID on pump enable

            if (self.register_write(10,1) == True) and (self.register_write(12,0) == True) and (self.register_write(13,5) == True) and (self.register_write(33,1) == True):
                logging.info("Disc pump drive mode succesfully configured.")
            else:
                logging.error("Disc pump drive mode configuration failed!")
                sys.exit()

            # Configure PID constants
            # R14 -> var = Kp
            # R15 -> var = Ki
            # R16 -> var = Integral limit (max power)
            # R17 -> var = Kd

            if (self.register_write(14,Kp) == True) and (self.register_write(15,Ki) == True) and (self.register_write(16,maximum_power) == True) and (self.register_write(17,Kd) == True):
                logging.info("Disc pump PID settings succesfully configured.")
            else:
                logging.error("Disc pump PID configuration failed!")
                sys.exit()

            self.gauge = self.get_gauge() #mbar

        else:
            logging.info("No serial connection to pipette established.")
            self.gauge = 0 #mbar

        logging.info(f"Disc pump gauge pressure set as {self.gauge}mbar.")

    def get_data(self):
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode()
    
    def register_write(self, REGISTER_NUMBER, VALUE):
        # The PCB responds to “write” commands by echoing the command back. 
        # This response should be read and checked by the controlling software to confirm 
        # that the command has been received correctly. If the command causes an error, 
        # or is not received at all, the PCB does not respond. 

        msg = f"#W{REGISTER_NUMBER},{VALUE}" + '\n'
     
        if self.sim == False:
            self.ser.write(msg.encode('ascii'))

            if (self.get_data() == msg):
                return True
            else:
                return False
        else:
            return True
        
    def register_read(self, REGISTER_NUMBER):
        # R3 = Drive voltage
        # R4 = Drive current
        # R5 = Drive power
        # R6 = Drive frequency
        # R39 = Pressure reading

        msg = f"#R{REGISTER_NUMBER}" + '\n'
        if self.sim == False:
            self.ser.write(msg.encode('ascii'))

            data = self.get_data()

            return float(data.split(",")[1])
        else:
            return self.gauge

    def close_ser(self):
        logging.info("Closing serial connection to pipette..")
        self.ser.close()

    def get_gauge(self):
        return self.register_read(39)
    
    def get_pressure(self):
        return self.register_read(39)
    
    def get_power(self):
        return self.register_read(5)

    def pump_on(self):
        if self.register_write(0, 1) == True:
            logging.info(f"Pipette successfully turned on.")
        else:
            logging.error(f"Failed to turn on Pipette.")
            sys.exit()
    
    def pump_off(self, check=False):
        if self.register_write(0, 0) == True:
            logging.info(f"Pipette successfully turned off.")
        else:
            logging.error(f"Failed to turn off Pipette.")
            sys.exit()

        if check == True:
            self.check_pressure(0)

    def check_pressure(self, target):
        if self.sim == False:
            start_time = time.time()
            
            error = target - self.get_pressure()
            
            while (error > self.success_factor * self.resolution):
                new_time = time.time() - start_time
                if (new_time > self.timeout):
                    logging.error(f"Pipette failed to reach pressure of {target}mbar in {self.timeout}s.")
                    logging.info(f"Final Pipette pressure is {self.get_pressure()}mbar.")
                    self.pump_off()
                    sys.exit()

                time.sleep(0.02) # 20ms pause to prevent excessive interrupts
                error = target - self.get_pressure()

            new_time = time.time() - start_time
            logging.info(f"Pipette successfully reached {target - error}mbar in less than {math.ceil(new_time*1000)}ms.")

            # Delay to let system settle
            time.sleep(2)

            logging.info(f"Final Pump values: {self.get_pressure()}mbar and {self.get_power()}mW.")

        else:
            logging.info(f"Pipette successfully reached {target}mbar.")
    
    def set_pressure(self, value, check=False):
        # R/W register 23 for set point
        # mbar is default unit
        value = round(value + self.gauge, 3) # Increment by gauge pressure such that set_pressure(0) turns pump off 

        if self.register_write(23, value) == True:
            logging.info(f"Pipette target pressure set to {value}mbar.")
        else:
            logging.error(f"Failed to set pipette target pressure to {value}mbar.")
            sys.exit()

        if check == True:
            self.check_pressure(value)

    def get_poly_equation(self, xi, diff, T, N):
        time = np.linspace(0, T, N)

        # polynomial coefficients
        C_0 = xi
        C_1 = 0
        C_3 = diff * 10 / pow(T, 3)
        C_4 = diff * -15 / pow(T, 4)
        C_5 = diff * 6 / pow(T, 5)

        return C_0 + C_3 * np.power(time, 3) + C_4 * np.power(time, 4) + C_5 * np.power(time, 5)

    def aspirate(self, aspirate_volume, aspirate_constant, aspirate_speed, poly=False, check=True):
        charge_pressure = self.get_pressure()
        diff = aspirate_constant * aspirate_volume
        aspirate_pressure = diff + charge_pressure # Pressure diff is from charge pressure

        if aspirate_speed != 0:
            rise_time = aspirate_volume / aspirate_speed # Seconds

            logging.info(f"Rising to aspiration pressure of {aspirate_pressure}mbar in {rise_time}s, from charged pressure of {charge_pressure}mbar.")
            N = math.floor(diff / self.resolution) + 2 # Ideal resolution of sensor (1.7bar range with 12bit value), N >= 2
            dT = rise_time / (N-1)

            if poly==False:
                path = np.linspace(charge_pressure, aspirate_pressure, N)
            else:
                path = self.get_poly_equation(charge_pressure, diff, rise_time, N)

            for set_point in path:
                self.set_pressure(set_point)
                time.sleep(dT)

            if check==True:
                self.check_pressure(aspirate_pressure) # Only check final reading

        else:
            # Jumpy straight to aspirate pressure if no speed given
            self.set_pressure(aspirate_pressure, check)
    
    def dispense(self, check=False):
        self.set_pressure(0) # To dispense as quickly as possible to remove all liquid
        self.pump_off(check=True)