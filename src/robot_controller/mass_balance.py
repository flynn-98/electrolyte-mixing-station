import logging
import random
import sys
import time

import serial

logging.basicConfig(level = logging.INFO)

# To communicate with: https://www.kern-sohn.com/shop/en/products/laboratory-balances/precision-balances/PCD-2500-2/

class mass_reader:
    def __init__(self, COM: str, sim: bool = False) -> None:
        self.sim = sim

        # Mass balance checks
        self.minor_mass_error = 10 # %, error if exceeded
        self.critical_mass_error = 50 # %, error if exceeded

        self.correction = 0.05 #g or mL left behind in mixing chamber

        self.timeout = 2 #s 

        if self.sim is False:
            logging.info("Configuring mass balance serial port..")
            self.ser = serial.Serial(COM) 
            self.ser.baudrate = 9600
            self.ser.bytesize = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1

            logging.info("Attempting to open mass balance serial port..")            

            if self.ser.isOpen() is False:
                self.ser.open()

            self.tare()

            if self.get_mass() == 0.0:
                logging.info("Serial connection to mass balance established.")
            else:
                logging.error("Failed to establish serial connection to mass balance.")
                sys.exit()

        else:
            logging.info("No serial connection to mass balance established.")

    def close_ser(self) -> None:
        if self.sim is False:
            if self.ser.isOpen():
                self.ser.close()

    def get_mass(self) -> float:        
        if self.sim is False:
            # Wait for balance to settle in case fluid is moving
            time.sleep(5)
            received = False

            while received is False:
                # Send char to trigger stable value to be sent
                logging.info("Requesting mass balance reading..")
                self.ser.write("s".encode())

                start = time.time()
                while (self.ser.in_waiting == 0) and (time.time() - start < self.timeout):
                    time.sleep(0.2)

                if self.ser.in_waiting > 0:
                    received = True
                else:
                    logging.error("Mass balance request timed out.")

            readout = self.ser.readline().decode().rstrip().replace("g", "").replace(" ", "")
            
            return float(readout)
        else:
            return random.uniform(1, 50)
        
    def tare(self) -> None:
        # Send char to trigger tare
        if self.sim is False:
            self.ser.write("t".encode())

    def check_mass_change(self, expected_mass: float, starting_mass: float) -> None:
        logging.info("Assessing mass balance changes..")
        
        # Correction accounts for mass left behind in mixing chamber
        expected_mass -= self.correction

        mass_change = self.get_mass() - starting_mass
        error = mass_change - expected_mass

        percent = (100 * abs(error) / expected_mass)
        
        if self.sim is False:
            if percent > self.critical_mass_error:
                logging.error(f"Mass balance detected critical error: {mass_change}g detected at test cell but expected {expected_mass}g.")
                sys.exit()
            elif percent > self.minor_mass_error:
                logging.error(f"Mass balance detected minor error: {mass_change}g detected at test cell but expected {expected_mass}g.")
            else:
                logging.info(f"Mass balance detected no significant error: {mass_change}g detected at test cell for expected {expected_mass}g.")

        else:
            logging.info(f"Mass balance detected no significant error: {mass_change}g detected at test cell for expected {expected_mass}g.")