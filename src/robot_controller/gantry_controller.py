import serial
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

            if self.get_data == "Controller Ready":
                logging.info("Serial connection to gantry established.")
            else:
                logging.error("Failed to establish serial connection to gantry.")
                exit()

        else:
            logging.info("No serial connection to gantry established.")

    def get_data(self):
        while self.ser.in_waiting:
            return self.ser.readline().decode().strip()

    def close_ser(self):
        logging.info("Closing serial connection to gantry..")
        self.ser.close()

    def write(self, x, y, z, p):
        if self.sim == False:
            self.ser.write(f"{x},{y},{z},{p};".encode())

            # Wait for response but do nothing with data
            data = self.get_data()
            logging.info("Response from gantry: " + data)