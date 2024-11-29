import serial
import sys
import logging
logging.basicConfig(level = logging.INFO)

class gantry:
    def __init__(self, COM, sim=False):
        self.sim = sim

        if self.sim == False:
            logging.info("Configuring gantry serial port..")
            self.ser = serial.Serial(COM) # COMXX
            self.ser.baudrate = 9600 # set Baud rate to 9600
            self.ser.bytesize = 8 # Number of data bits = 8
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1 # Number of Stop bits = 1

            logging.info("Attempting to open gantry serial port..")

            if self.ser.isOpen() == False:
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
        
    def get_response(self):
        data = self.get_data()
        # Wait for response and check that command was understood
        if data == "Unknown command":
            logging.error("Gantry failed to recognise command.")
            sys.exit()
        else:
            logging.info("Response from gantry: " + data)

    def close_ser(self):
        logging.info("Closing serial connection to gantry..")
        self.ser.close()

    def move(self, x, y, z):
        if self.sim == False:
            self.ser.write(f"move({x},{y},{z})".encode())
            self.get_response()

    def softHome(self):
        if self.sim == False:
            self.ser.write("softHome()".encode())
            self.get_response()

    def hardHome(self):
        if self.sim == False:
            self.ser.write("hardHome()".encode())
            self.get_response()

    def pump(self, vol):
        if self.sim == False:
            self.ser.write(f"pump({vol})".encode())
            self.get_response()

    def mix(self, duration):
        if self.sim == False:
            self.ser.write(f"mix({duration})".encode())
            self.get_response()