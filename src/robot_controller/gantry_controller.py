import logging
import math
import sys

import serial

logging.basicConfig(level = logging.INFO)

class gantry:
    def __init__(self, COM: str, sim: bool = False) -> None:
        self.sim = sim

        # File to store last known active pipette for recovery
        self.location_file = "data/variables/location_recovery.txt" # X,Y,Z. Allows gantry to recover position if gantry firmware not homed (i.e. full power off)

        if self.sim is False:
            logging.info("Configuring gantry kit serial port..")
            self.ser = serial.Serial(COM) # COMXX
            self.ser.baudrate = 9600 # set Baud rate to 9600
            self.ser.bytesize = 8 # Number of data bits = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1 # Number of Stop bits = 1

            logging.info("Attempting to open gantry kit serial port..")

            if self.ser.isOpen() is False:
                self.ser.open()

            if self.get_data() == "Gantry Kit Ready":
                logging.info("Serial connection to gantry kit established.")
            else:
                logging.error("Failed to establish serial connection to gantry kit.")
                sys.exit()

        else:
            logging.info("No serial connection to gantry kit established.")

    def get_file(self) -> str:
        return self.location_file

    def get_data(self) -> str:
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode().rstrip().replace("\x00", "")
        
    def get_response(self) -> None:
        data = self.get_data()
        # Wait for response and check that command was understood
        if data == "Unknown command":
            logging.error("Gantry kit failed to recognise command.")
            sys.exit()
        else:
            logging.info("Response from gantry kit: " + data)

    def close_ser(self) -> None:
        logging.info("Closing serial connection to gantry kit.")
        if self.sim is False:
            self.ser.close()

    def move(self, x: float, y: float, z: float) -> None:
        as_string = f"{x},{y},{z}"

        # Update last known location for recovery
        with open(self.location_file, 'w') as filehandler:
                filehandler.write(as_string)

        if self.sim is False:
            msg = "move(" + as_string + ")"
            self.ser.write(msg.encode())
            self.get_response()

    def softHome(self) -> None:
        if self.sim is False:
            self.ser.write("softHome()".encode())
            self.get_response()

    def hardHome(self) -> None:
        if self.sim is False:
            self.ser.write("hardHome()".encode())
            self.get_response()

    def mix(self, count: int = 25, delay: int = 100) -> None:
        logging.info(f"Mixing electrolyte {count} times with a {delay}ms delay.")
        if self.sim is False:
            # Move away from mixing chamber first
            self.move(0, 0, 0)

            self.ser.write(f"mix({count}, {delay})".encode())
            self.get_response()

    def pinch(self) -> None:
        if self.sim is False:
            self.ser.write("pinch()".encode())
            self.get_response()

    def release(self) -> None:
        if self.sim is False:
            self.ser.write("release()".encode())
            self.get_response()

    def recover(self, xyz: str) -> None:
        if self.sim is False:
            msg = "recover(" + xyz + ")"
            self.ser.write(msg.encode())
            self.get_response()