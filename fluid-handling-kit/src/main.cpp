#include <Servo.h>
#include <AccelStepper.h>

const int TX = 0;
const int RX = 1;

// Pins for pump stepper motors, see https://learn.sparkfun.com/tutorials/big-easy-driver-hookup-guide/all
const int PUMP_1_STEP = 2;
const int PUMP_1_DIR = 3;

const int PUMP_2_STEP = 4;
const int PUMP_2_DIR = 5;

const int PUMP_3_STEP = 6;
const int PUMP_3_DIR = 7;

// Pump 1 = Electrolyte into Cell, Pump 2 = Electrolyte out of Cell, Pump 3 = Cleaning Solution into Cell

// Pins for 4th stepper motor
const int PUMP_4_STEP = 8;
const int PUMP_4_DIR = 9;

// Define Arduino pins for each function
const int SERVO_PIN = 10;

// Define relay pin
const byte RELAY_PIN = A0;

// Define comms pins
const int MOSI_PIN = 11;
const int MISO_PIN = 12;
const int SCK_PIN = 13;
const int SDA_PIN = 18;
const int SCL_PIN = 19;

// Define remaining pins (A6 & A7 are analog only)
const byte ANALOG_1 = A1;
const byte ANALOG_2 = A2;
const byte ANALOG_3 = A3;
const byte ANALOG_6 = A6;
const byte ANALOG_7 = A7;

// Motor speed and acceleration parameters, stepper motors have 200 steps / revolution.
// Microsteps (per step) used for increased positional accuracy and smoother stepping
const float STEPS_REV = 200.0;
const float MICROSTEPS = 4.0;
const float GEAR_RATIO = 1.0;

const float PUMP_SPEED = 500.0 * MICROSTEPS * GEAR_RATIO; //microsteps/s
const float MAX_ACCEL = 350.0 * MICROSTEPS * GEAR_RATIO; //microsteps/s2

// For Pump stepper motor
const float ML_REV = 0.1; //ml/rev

// Parameters for Mixer (Servo)
const int servoHome = 90;

// Define steppers with pins (STEP, DIR)
AccelStepper PUMP_1(AccelStepper::DRIVER, PUMP_1_STEP, PUMP_1_DIR); 
AccelStepper PUMP_2(AccelStepper::DRIVER, PUMP_2_STEP, PUMP_2_DIR);
AccelStepper PUMP_3(AccelStepper::DRIVER, PUMP_3_STEP, PUMP_3_DIR); 
AccelStepper PUMP_4(AccelStepper::DRIVER, PUMP_4_STEP, PUMP_4_DIR);

// Create servo instance
Servo mixer;

// Ensure motor direction matches desired pump direction
const float motorDir = 1;

// Maximum time in Loop before idle mode (s)
const unsigned long idleTime = 10;

float vol = 0;
unsigned long StartTime;
unsigned long CurrentTime;
unsigned long LastCall = 0;
unsigned long ElapsedTime;

String action;

void relayOn() {
    digitalWrite(RELAY_PIN, HIGH);
    delay(200);
};

void relayOff() {
    digitalWrite(RELAY_PIN, LOW);
    delay(200);
};

long volToSteps(float vol) {
    return floor(motorDir * MICROSTEPS * STEPS_REV * vol * GEAR_RATIO / ML_REV);
};

void addElectrolyte(float vol) {
    relayOn();

    StartTime = ceil( millis() / 1000 );

    // No limits for Pump
    PUMP_1.move(volToSteps(vol));

    // Run until complete
    PUMP_1.runToPosition();

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;

    // Report back to PC
    Serial.println("Pump complete in " + String(ElapsedTime) + "s");
};

void emptyCell(float vol) {
    relayOn();

    StartTime = ceil( millis() / 1000 );

    // No limits for Pump
    PUMP_2.move(volToSteps(vol));

    // Run until complete
    PUMP_2.runToPosition();

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;

    // Report back to PC
    Serial.println("Pump complete in " + String(ElapsedTime) + "s");
};

void cleanCell(float vol) {
    relayOn();

    StartTime = ceil( millis() / 1000 );

    // No limits for Pump
    PUMP_3.move(volToSteps(vol));

    // Run until complete
    PUMP_3.runToPosition();

    // Deprime line to avoid dripping into cell
    PUMP_3.move(-1 * volToSteps(vol));

    // Run until complete
    PUMP_3.runToPosition();

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;

    // Report back to PC
    Serial.println("Pump complete in " + String(ElapsedTime) + "s");
};

void setup() {
  // Setup code here, will run just once on start-up

  // Set pins to be used
  pinMode(PUMP_1_STEP, OUTPUT);
  pinMode(PUMP_1_DIR, OUTPUT);

  pinMode(PUMP_2_STEP, OUTPUT);
  pinMode(PUMP_2_DIR, OUTPUT);

  pinMode(PUMP_3_STEP, OUTPUT);
  pinMode(PUMP_3_DIR, OUTPUT);

  pinMode(PUMP_4_STEP, OUTPUT);
  pinMode(PUMP_4_DIR, OUTPUT);

  pinMode(SERVO_PIN, OUTPUT);
  mixer.attach(SERVO_PIN);
  
  pinMode(RELAY_PIN, OUTPUT);

  // Set motor speeds / acceleration
  PUMP_1.setAcceleration(MAX_ACCEL);
  PUMP_1.setMaxSpeed(PUMP_SPEED);

  PUMP_2.setAcceleration(MAX_ACCEL);
  PUMP_2.setMaxSpeed(PUMP_SPEED);

  PUMP_3.setAcceleration(MAX_ACCEL);
  PUMP_3.setMaxSpeed(PUMP_SPEED);

  PUMP_4.setAcceleration(MAX_ACCEL);
  PUMP_4.setMaxSpeed(PUMP_SPEED);

  Serial.begin(9600);
  mixer.write(servoHome);

relayOff();

Serial.println("Fluid Handling Kit Ready");
};

void loop() {
    // Main code here, to run repeatedly on a loop 
    delay(500);

    // Wait until data received from PC, via Serial (USB)
    if (Serial.available() > 0) {
        LastCall = ceil( millis() / 1000 );
        // data structure to receive = action(var1, var2..)

        // Read until open bracket to extract action, continue based on which action was requested
        action = Serial.readStringUntil('(');

        if (action == "addElectrolyte") {
            // Extract variables spaced by commas, then last variable up to closed bracket
            vol = Serial.readStringUntil(')').toFloat();
            
            // Call action using received variables
            addElectrolyte(vol);
        }
        else if (action == "cleanCell") {
            vol = Serial.readStringUntil(')').toFloat();
            
            // Call action using received variables
            cleanCell(vol);
        }
        else if (action == "emptyCell") {
            vol = Serial.readStringUntil(')').toFloat();
            
            // Call action using received variables
            emptyCell(vol);
        }
        else if (action == "returnState") {
            vol = Serial.readStringUntil(')').toFloat();

            Serial.println("Fluid Handling Kit Ready");
        }
        else {
            // Report back to PC if confused
            Serial.println("Unknown command");
        }

        // Start idle counter after action complete
        LastCall = ceil( millis() / 1000 );
    }
    else {
        // Check how long since last call, move to Home if too long
        CurrentTime = ceil( millis() / 1000 );
        ElapsedTime = CurrentTime - LastCall;

        if (ElapsedTime > idleTime) {
            relayOff();
            LastCall = CurrentTime;
        }
    }
};