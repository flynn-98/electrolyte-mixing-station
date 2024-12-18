import serial
import sys
import logging
logging.basicConfig(level = logging.INFO)

class pipette:
    def __init__(self, COM, sim=False, maximum_power=300, Kp=5, Ki=10, Kd=0):
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
            # R0 -> 0/1 = Disable/Enable pump
            # R1 -> var = Maximum power (mW)
            # R2 -> 0 = Disable stream mode

            if (self.register_write(0,0) == True) and (self.register_write(1,maximum_power) == True) and (self.register_write(2,0) == True):
                logging.info("Disc pump successfully initialised.")
            else:
                logging.error("Disc pump initialisation failed..")
                sys.exit()
            
            # Configure PID Settings
            # R10 -> 1 = PID mode (0 = manual)
            # R12 -> 0 = Setpoint source (register val)
            # R13 -> 5 = Input source (pressure sensor)
            # R33 -> 1 = Reset PID on pump enable

            if (self.register_write(10,1) == True) and (self.register_write(12,0) == True) and (self.register_write(13,5) == True) and (self.register_write(33,1) == True):
                logging.info("Disc pump PID settings succesfully configured.")
            else:
                logging.error("Disc pump PID settings configuration failed..")
                sys.exit()

            # Configure PID constants
            # R14 -> var = Kp
            # R15 -> var = Ki
            # R16 -> var = Integral limit (max power)
            # R17 -> var = Kd

            if (self.register_write(14,Kp) == True) and (self.register_write(15,Ki) == True) and (self.register_write(16,maximum_power) == True) and (self.register_write(17,Kd) == True):
                logging.info("Disc pump PID constants succesfully configured.")
            else:
                logging.error("Disc pump PID constants configuration failed..")
                sys.exit()

            self.gauge = self.get_gauge() #mbar

        else:
            logging.info("No serial connection to pipette established.")
            self.gauge = 1000 #mbar

        logging.info(f"Disc pump gauge pressure set as {self.gauge}mbar.")

    def get_data(self):
        while self.ser.in_waiting == 0:
            pass

        return self.ser.readline().decode()
        
    def set_pressure(self, VALUE):
        # R/W register 23 for set point
        # mbar is default unit
        VALUE = round(VALUE + self.gauge, 3) # Increment by gauge pressure such that set_pressure(0) turns pump off 

        if self.register_write(23, VALUE) == True:
            logging.info(f"Pipette pressure set to {VALUE}mbar.")
        else:
            logging.error(f"Failed to set pipette pressure to {VALUE}mbar.")
            sys.exit()

    def pump_on(self):
        return self.register_write(0, 1)
    
    def pump_off(self):
        return self.register_write(0, 0)
    
    def get_gauge(self):
        return self.register_read(39)
    
    def get_pressure(self):
        return self.register_read(39) - self.gauge
    
    def get_power(self):
        return self.register_read(5)
        
    def register_write(self, REGISTER_NUMBER, VALUE):
        # The PCB responds to “write” commands by echoing the command back. 
        # This response should be read and checked by the controlling software to confirm 
        # that the command has been received correctly. If the command causes an error, 
        # or is not received at all, the PCB does not respond. 

        msg = f"#W{REGISTER_NUMBER},{VALUE}" + '\n'
     
        if self.sim == False:
            self.ser.write(msg.encode('ascii'))

            if (self.get_data() == msg):
                return True
            else:
                return False
        else:
            return True
        
    def register_read(self, REGISTER_NUMBER):
        # R3 = Drive voltage
        # R4 = Drive current
        # R5 = Drive power
        # R6 = Drive frequency
        # R39 = Pressure reading

        msg = f"#R{REGISTER_NUMBER}" + '\n'
        if self.sim == False:
            self.ser.write(msg.encode('ascii'))

            data = self.get_data()

            return float(data.split(",")[1])
        else:
            return self.gauge

    def close_ser(self):
        logging.info("Closing serial connection to pipette..")
        self.ser.close()