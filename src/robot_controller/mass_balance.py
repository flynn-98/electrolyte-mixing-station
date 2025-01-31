import logging
import math
import sys

import serial

logging.basicConfig(level = logging.INFO)

# To communicate with: https://www.kern-sohn.com/shop/en/products/laboratory-balances/precision-balances/PCD-2500-2/

class mass_reader:
    def __init__(self, COM: str, sim: bool = False) -> None:
        self.sim = sim

        if self.sim is False:
            logging.info("Configuring mass balance serial port..")
            self.ser = serial.Serial(COM) 
            self.ser.baudrate = 9600
            self.ser.bytesize = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1

            logging.info("Attempting to open mass balance serial port..")

            if self.ser.isOpen() is False:
                try:
                    self.ser.open()
                    logging.info("Serial connection to mass balance established.")
                except Exception as ex:
                    logging.error(ex)
                    logging.error("Failed to establish serial connection to mass balance.")    

            # Close serial until mass reading required - to silence continuous streaming.
            self.close_ser()

        else:
            logging.info("No serial connection to mass balance established.")

    def close_ser(self) -> None:
        if self.sim is False:
            self.ser.close()

    def get_mass(self) -> float:
        if self.sim is False:
            self.ser.open()

            while self.ser.in_waiting == 0:
                pass

            readout = self.ser.readline().decode().rstrip().replace("g", "")
            self.ser.close()
            return float(readout)
        
        else:
            return 0.0