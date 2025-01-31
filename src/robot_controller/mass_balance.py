import logging
import math
import sys

import serial

logging.basicConfig(level = logging.INFO)

class mass_reader:
    def __init__(self, COM: str, sim: bool = False) -> None:
        self.sim = sim

        if self.sim is False:
            logging.info("Configuring mass balance serial port..")
            self.ser = serial.Serial(COM) # COMXX
            self.ser.baudrate = 9600 # set Baud rate to 9600
            self.ser.bytesize = 8 # Number of data bits = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1 # Number of Stop bits = 1

            logging.info("Attempting to open mass balance kit serial port..")

            if self.ser.isOpen() is False:
                self.ser.open()

            if self.get_data() == "Mass Balance Ready":
                logging.info("Serial connection to mass balance kit established.")
            else:
                logging.error("Failed to establish serial connection to mass balance.")
                sys.exit()

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