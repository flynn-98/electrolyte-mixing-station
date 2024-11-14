import serial
import logging
logging.basicConfig(level = logging.INFO)

class pipette:
    def __init__(self, COM, sim=False, maximum_power=300, Kp=1, Ki=1, Kd=0):
        self.sim = sim

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
            # R0 -> 1 = Enable pump
            # R1 -> var = Maximum power (mW)
            # R2 -> 0 = Disable stream mode

            if (self.register_write(0,1) == True) and (self.register_write(1,maximum_power) == True) and (self.register_write(2,0) == True):
                logging.info("Disc pump successfully initialised.")
            else:
                logging.error("Disc pump initialisation failed..")
                exit()
            
            # Configure PID Settings
            # R10 -> 1 = PID mode (0 = manual)
            # R12 -> 0 = Setpoint source (register val)
            # R13 -> 5 = Input source (pressure sensor)
            # R33 -> 1 = Reset PID on pump enable

            if (self.register_write(10,1) == True) and (self.register_write(12,0) == True) and (self.register_write(13,5) == True) and (self.register_write(33,1) == True):
                logging.info("Disc pump PID settings succesfully configured.")
            else:
                logging.error("Disc pump PID configuration failed..")
                exit()

            # Configure PID constants
            # R14 -> var = Kp
            # R15 -> var = Ki
            # R16 -> var = Integral limit (max power)
            # R17 -> var = Kd

            if (self.register_write(14,Kp) == True) and (self.register_write(15,Ki) == True) and (self.register_write(16,maximum_power) == True) and (self.register_write(17,Kd) == True):
                logging.info("Disc pump PID settings succesfully configured.")
            else:
                logging.error("Disc pump PID configuration failed..")
                exit()

        else:
            logging.info("No serial connection to pipette established.")

    def get_data(self):
        while self.ser.in_waiting:
            return self.ser.readline().decode().strip()
        
    def set_pressure(self, VALUE):
        # R/W register 23 for set point
        return self.register_write(23, VALUE)
        
    def register_write(self, REGISTER_NUMBER, VALUE):
        # The PCB responds to “write” commands by echoing the command back. 
        # This response should be read and checked by the controlling software to confirm 
        # that the command has been received correctly. If the command causes an error, 
        # or is not received at all, the PCB does not respond. 

        msg = f"#W<{REGISTER_NUMBER}>,<{VALUE}>\n"
        self.ser.write(msg)

        if (self.get_data() == msg):
            return True
        else:
            return False
        
    def register_read(self, REGISTER_NUMBER):
        # R3 = Drive voltage
        # R4 = Drive current
        # R5 = Drive power
        # R6 = Drive frequency
        # R39 = Pressure reading

        msg = f"#R<{REGISTER_NUMBER}>\n"
        self.ser.write(msg)

        data = self.get_data()

        return float(data.split(",")[1])

    def close_ser(self):
        logging.info("Closing serial connection to pipette..")
        self.ser.close()

    def write(self, x, y, z, p):
        if self.sim == False:
            self.ser.write(f"{x},{y},{z},{p};".encode())

            # Wait for response but do nothing with data
            data = self.get_data()
            logging.info("Response from pipette: " + data)