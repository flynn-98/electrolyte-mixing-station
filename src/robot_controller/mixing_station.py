import logging
import math
import os

from robot_controller import gantry_controller, pipette_controller

logging.basicConfig(level = logging.INFO)

class electrolyte_mixer:
    def __init__(self, gantry_port: str, pipette_port: str, gantry_sim: bool = False, pipette_sim: bool = False, home: bool = False) -> None:

        self.gantry = gantry_controller.gantry(gantry_port, gantry_sim)            
        self.pipette = pipette_controller.pipette(pipette_port, pipette_sim)

        # To be set by scheduler from hardcoded values
        self.workspace_height_correction = 0

        # Pot locations 1 -> 10 (mm), pot 10 is for washing
        self.pot_locations = [[41, 0], [75, 0], 
                              [109, 0], [143, 0], 
                              [58, 34], [92, 34], 
                              [126, 34], [75,68], 
                              [109, 68], [143, 68]
                            ]
        
        # Pipette locations 1 -> 9 (mm)
        self.pipette_x_location = 17 #mm
        self.pipette_locations = [[self.pipette_x_location, 135], [self.pipette_x_location, 119.4 ], 
                              [self.pipette_x_location, 103.8], [self.pipette_x_location, 88.2], 
                              [self.pipette_x_location, 72.6], [self.pipette_x_location, 57], 
                              [self.pipette_x_location, 41.4], [self.pipette_x_location, 25.8], 
                              [self.pipette_x_location, 10.2]
                            ]
        
        self.pipette_pick_height = -47.5 #mm (from CAD)
        self.pipette_lead_in = 12 #mm to position pipette to the right of rack (in X direction) when returning pipette

        # File to store last known active pipette for recovery
        self.pipette_file = "data/variables/active_pipette.txt" # 1-9, 0 = not active        
        
        self.pot_base_height = -68.5 #mm (from CAD)
        self.pot_area = math.pi * 2.78**2 / 4 #cm2

        self.chamber_location = [125, 140] #[125, 98] # mm
        self.dispense_height = -30 #mm

        # Home if requested (will also happen during recovery)
        if home is True:
            self.gantry.softHome()

    def correct_workspace_heights(self) -> None:
         self.pot_base_height += self.workspace_height_correction
         self.pipette_pick_height += self.workspace_height_correction

    def move_to_start(self) -> None:
        # Add to start of all loops involving gantry motion
        self.gantry.move(self.pipette_x_location + self.pipette_lead_in, 0, 0)

    def pick_pipette(self, pipette_no: int) -> None:
        # Turn pump off just in case
        self.pipette.pump_off(check=False)

        x, y = self.pipette_locations[pipette_no-1][0], self.pipette_locations[pipette_no-1][1]

        # Move above pipette rack
        logging.info(f"Moving to Pipette #{pipette_no}..")
        self.gantry.move(x + self.pipette_lead_in, y, 0)
        self.gantry.move(x, y, 0)

        # Move into pipette rack
        logging.info("Dropping to collect pipette..")
        self.gantry.move(x, y, self.pipette_pick_height)

        # Update active pipette variable 
        with open(self.pipette_file, 'w') as filehandler:
                filehandler.write(f"{pipette_no}")

        # Move into pipette rack
        logging.info(f"Raising Pipette #{pipette_no}..")
        self.gantry.zQuickHome()

        # Move into pipette rack
        logging.info("Moving away from pipette rack..")
        self.gantry.move(x + self.pipette_lead_in, y, 0)

    def return_pipette(self) -> None:
        # Turn pump off just in case
        self.pipette.pump_off(check=False)

        # Return active pipette
        file_exists = os.path.exists(self.pipette_file)
        if file_exists:
            with open(self.pipette_file, 'r') as filehandler:
                active_pipette = int(filehandler.read())
        
        if active_pipette == 0 or not file_exists:
            logging.error("Return pipette requested whilst no pipette is active.")
            return

        x, y = self.pipette_locations[active_pipette-1][0], self.pipette_locations[active_pipette-1][1]

        # Move above pipette rack (first to lead in location to avoid clash)
        logging.info(f"Moving to Pipette #{active_pipette}..")
        self.gantry.move(x + self.pipette_lead_in, y, 0)
        self.gantry.move(x, y, 0)

        # Move into pipette rack
        logging.info(f"Delivering Pipette #{active_pipette} to rack..")
        self.gantry.move(x, y, self.pipette_pick_height)

        logging.info("Pinching and raising pipette module..")
        self.gantry.pinch()
        #self.gantry.zQuickHome()
        self.gantry.release()
        logging.info("Pipettes released.")

        with open(self.pipette_file, 'w') as filehandler:
                filehandler.write("0")

    def collect_volume(self, aspirate_volume: float, starting_volume: float, name: str, pot_no: int, aspirate_scalar: float, aspirate_speed: float) -> float:
        new_volume = round(starting_volume - aspirate_volume * 1e-3, 4) #ml

        x, y = self.pot_locations[pot_no-1][0], self.pot_locations[pot_no-1][1]

        # Move above pot
        logging.info("Moving to " + name + "..")
        self.gantry.move(x, y, 0)

        # Charge pipette
        self.pipette.pump_on()
        self.pipette.charge_pipette()
        logging.info("Pipette charged.")

        # Drop into fluid (based on starting volume)
        z = self.pot_base_height + 10 * new_volume / self.pot_area

        logging.info(f"Dropping Pipette to {z}mm..")
        self.gantry.move(x, y, z)

        # Aspirate pipette
        self.pipette.aspirate(aspirate_volume, aspirate_scalar, aspirate_speed)

        logging.info("Aspiration complete.")
        logging.info(f"{aspirate_volume}uL extracted, {new_volume}mL remaining..")

        # Move out of fluid
        logging.info("Lifting Pipette..")
        self.gantry.move(x, y, 0)
        
        return new_volume
    
    def deliver_volume(self) -> None:
        x, y = self.chamber_location[0], self.chamber_location[1]

        logging.info("Moving to Mixing Chamber..")
        self.gantry.move(x, y, 0)
        
        logging.info(f"Dropping Pipette to {self.dispense_height}mm..")
        self.gantry.move(x, y, self.dispense_height)

        # Dispense pipette
        self.pipette.dispense()
        logging.info("Dispense complete.")

        logging.info("Lifting Pipette..")
        self.gantry.move(x, y, 0)
        


