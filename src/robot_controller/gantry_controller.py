import serial
import logging
logging.basicConfig(level = logging.INFO)

class gantry:
    def __init__(self, COM):
        
        logging.info("Configuring gantry serial port..")
        self.ser = serial.Serial(COM) # COMXX
        self.ser.baudrate = 9600 # set Baud rate to 9600
        self.ser.bytesize = 8 # Number of data bits = 8
        self.ser.parity = 'N' # No parity
        self.ser.stopbits = 1 # Number of Stop bits = 1

        logging.info("Attempting to open gantry serial port..")
        try:
            self.ser.open()
        except:
            self.ser.close()
            self.ser.open()

        logging.info("Serial connection to gantry established.")

    def ifReady(self):
        while self.ser.in_waiting:
            return True

    def close_ser(self):
        logging.info("Closing serial connection to gantry..")
        self.ser.close()

    def write(self, x, y, z, p):
        self.ser.write(f"{x},{y},{z},{p};".encode())

    def close(self):
        self.ser.close()