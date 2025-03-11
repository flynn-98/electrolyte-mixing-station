import logging
import math
import sys

import serial

logging.basicConfig(level = logging.INFO)

class fluid_handler:
    def __init__(self, COM: str, sim: bool = False) -> None:
        self.sim = sim

        if self.sim is False:
            logging.info("Configuring fluid handling kit serial port..")
            self.ser = serial.Serial(COM) 
            self.ser.baudrate = 9600
            self.ser.bytesize = 8 
            self.ser.parity = 'N' # No parity
            self.ser.stopbits = 1

            logging.info("Attempting to open fluid handling kit serial port..")

            if self.ser.isOpen() is False:
                self.ser.open()

            if self.get_data() == "Fluid Handling Kit Ready":
                logging.info("Serial connection to fluid handling kit established.")
            else:
                logging.error("Failed to establish serial connection to fluid handling kit.")
                sys.exit()

        else:
            logging.info("No serial connection to fluid handling kit established.")

    def get_data(self) -> str:
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode().rstrip().replace("\x00", "")
        
    def get_response(self) -> None:
        data = self.get_data()
        # Wait for response and check that command was understood
        if data == "Unknown command":
            logging.error("Fluid handling kit failed to recognise command.")
            sys.exit()
        else:
            logging.info("Response from fluid handling kit: " + data)

    def close_ser(self) -> None:
        logging.info("Closing serial connection to fluid handling kit.")
        if self.sim is False:
            if self.ser.isOpen():
                self.ser.close()

    def add_electrolyte(self, fluid_vol: float, tube_length: float = 300.0, overpump: float = 1.2) -> None:
        # Fluid volume in uL -> sent volume in mL
        logging.info(f"Pumping {fluid_vol}uL of electrolyte to test cell..")
        tube_vol = math.pi * tube_length * 1e-3 # 2mm ID tubing (Area = Pi)
        vol = overpump * (fluid_vol / 1000 + tube_vol) #ml
        
        if self.sim is False:
            self.ser.write(f"addElectrolyte({vol})".encode())
            self.get_response()

    def clean_cell(self, fluid_vol: float = 3.0, tube_length: float = 300.0, overpump: float = 1.0) -> None:
        logging.info(f"Pumping {fluid_vol}uL of cleaning solution to test cell..")
        tube_vol = math.pi * tube_length * 1e-3 # 2mm ID tubing (Area = Pi)
        vol = overpump * (fluid_vol / 1000 + tube_vol) #ml
        
        if self.sim is False:
            self.ser.write(f"cleanCell({vol})".encode())
            self.get_response()

            self.empty_cell(fluid_vol)

    def empty_cell(self, fluid_vol: float, tube_length: float = 300.0, overpump: float = 1.2) -> None:
        logging.info(f"Pumping {fluid_vol}uL from test cell to waste..")
        tube_vol = math.pi * tube_length * 1e-3 # 2mm ID tubing (Area = Pi)
        vol = overpump * (fluid_vol / 1000 + tube_vol) #ml
        
        if self.sim is False:
            self.ser.write(f"emptyCell({vol})".encode())
            self.get_response()