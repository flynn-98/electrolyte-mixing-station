import logging
import sys

import serial

logging.basicConfig(level = logging.INFO)

class gantry:
    def __init__(self, COM, sim=False) -> None:
        self.sim = sim

        if self.sim is False:
            logging.info("Configuring gantry serial port..")
            self.ser = serial.Serial(COM) # COMXX
            self.ser.baudrate = 9600 # set Baud rate to 9600
            self.ser.bytesize = 8 # Number of data bits = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1 # Number of Stop bits = 1

            logging.info("Attempting to open gantry serial port..")

            if self.ser.isOpen() is False:
                self.ser.open()

            if self.get_data() == "Gantry Homed":
                logging.info("Serial connection to gantry established.")
            else:
                logging.error("Failed to establish serial connection to gantry.")
                sys.exit()

        else:
            logging.info("No serial connection to gantry established.")

    def get_data(self):
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode().rstrip().replace("\x00", "")
        
    def get_response(self) -> None:
        data = self.get_data()
        # Wait for response and check that command was understood
        if data == "Unknown command":
            logging.error("Gantry failed to recognise command.")
            sys.exit()
        else:
            logging.info("Response from gantry: " + data)

    def close_ser(self) -> None:
        logging.info("Closing serial connection to gantry.")
        if self.sim is False:
            self.ser.close()

    def move(self, x, y, z) -> None:
        if self.sim is False:
            self.ser.write(f"move({x},{y},{z})".encode())
            self.get_response()

    def softHome(self) -> None:
        if self.sim is False:
            self.ser.write("softHome()".encode())
            self.get_response()

    def hardHome(self) -> None:
        if self.sim is False:
            self.ser.write("hardHome()".encode())
            self.get_response()

    def pump(self, electrolyte_vol, tube_vol=1.6, overpump=1.1) -> None:
        logging.info(f"Pumping {electrolyte_vol}mL of electrolyte to next stage.")
        vol = overpump * (electrolyte_vol+tube_vol) #ml
        
        if self.sim is False:
            self.ser.write(f"pump({vol})".encode())
            self.get_response()

    def mix(self, count=25, delay=100) -> None:
        logging.info(f"Mixing electrolyte {count} times with a {delay}ms delay.")
        if self.sim is False:
            # Move away from mixing chamber first
            self.move(0, 0, 0)

            self.ser.write(f"mix({count}, {delay})".encode())
            self.get_response()