#include <Servo.h>
#include <AccelStepper.h>

const int TX = 0;
const int RX = 1;

// Pins for XYZ stepper motors, see https://learn.sparkfun.com/tutorials/big-easy-driver-hookup-guide/all
const int X_STEP = 2;
const int X_DIR = 3;

const int Y_STEP = 4;
const int Y_DIR = 5;

const int Z_STEP = 6;
const int Z_DIR = 7;

// Pins for extra stepper motor
const int E_STEP = 8;
const int E_DIR = 9;

// Define Arduino pins for each function
const int SERVO_PIN = 10;

// Define relay pin
const int RELAY_PIN = A0;

// Define comms pins
const int MOSI_PIN = 11;
const int MISO_PIN = 12;
const int SCK_PIN = 13;
const int SDA_PIN = 18;
const int SCL_PIN = 19;

// Define remaining pins (A6 & A7 are analog only)
const int ANALOG_1 = A1;
const int ANALOG_2 = A2;
const int ANALOG_3 = A3;
const int ANALOG_6 = A6;
const int ANALOG_7 = A7;

// Motor speed and acceleration parameters, stepper motors have 200 steps / revolution.
// Microsteps (per step) used for increased positional accuracy and smoother stepping
const float STEPS_REV = 200.0;
const float MICROSTEPS = 4.0;

const float STAGE_SPEED = 1000.0 * MICROSTEPS; //microsteps/s
const float ROPE_SPEED = 20.0 * MICROSTEPS; //microsteps/s
const float HOMING_SPEED = 50.0 * MICROSTEPS; //microsteps/s

const float MAX_ACCEL = 350.0 * MICROSTEPS; //microsteps/s2

const float Z_STAGE_SPEED = 1600.0 * MICROSTEPS; //microsteps/s
const float Z_HOMING_SPEED = 150 * MICROSTEPS; //microsteps/s
const float Z_ACCEL = 500.0 * MICROSTEPS; //microsteps/s2

// Parameters needed to convert distances (mm) to motor steps
const float PULLEY_RADIUS = 6.34; //mm
const float ROD_PITCH = 2.0; //mm

// Parameters for Mixer (Servo)
const int servoHome = 90;
const int servoStart = 20; // +Home
const int servoEnd = 50; // +Home

// Parameters for pipette rack
const float tension_rotations = 0.25;
const float pinch_rotations = 0.08;

// Define steppers with pins (STEP, DIR)
AccelStepper X_MOTOR(AccelStepper::DRIVER, X_STEP, X_DIR); 
AccelStepper Y_MOTOR(AccelStepper::DRIVER, Y_STEP, Y_DIR);
AccelStepper Z_MOTOR(AccelStepper::DRIVER, Z_STEP, Z_DIR); 
AccelStepper E_MOTOR(AccelStepper::DRIVER, E_STEP, E_DIR);

// Create servo instance
Servo mixer;

// Gantry (CNC) Home Positions (mm), values taken from CAD model and adjusted
const float pad_thickness = 1.0; //mm 
const float x_shift = 14.0; //mm (home position shift in X direction, to avoid unwanted clash)

const float home[3] = {-167.9 + pad_thickness + x_shift, 1.5 - pad_thickness, -0.5}; 

// Joint Limits (mm), also taken from CAD model
const float jointLimit[2][3] = {
    {0, 0, 0}, 
    {165.0 - x_shift, 141.0, -49}
};

// Overshoot value used during Homing, any gantry drift +- this value will be corrected (in theory!)
const float drift = 5; //mm

// Joint direction coefficients: 1 or -1, for desired motor directions
// X = 0, Y = 1, Z = 2
const float motorDir[4] = {1, 1, -1, 1};

// Maximum time in Loop before idle mode (s)
const unsigned long HomeTime = 30;

// Define variables to change during Loop
float x = 0;
float y = 0;
float z = 0;

float vol = 0;
int count = 0;
int servoDelay = 0;

unsigned long StartTime;
unsigned long CurrentTime;
unsigned long LastCall = 0;
unsigned long ElapsedTime;

long steps;
String action;
bool homed = false;

void relayOn() {
    digitalWrite(RELAY_PIN, HIGH);
    delay(200);
};

void relayOff() {
    digitalWrite(RELAY_PIN, LOW);
    delay(200);
};

void pullRope(float rotations) {
    relayOn();

    steps = motorDir[3] * MICROSTEPS * STEPS_REV * rotations;

    E_MOTOR.move(steps);
    E_MOTOR.runToPosition();
}

void pinchPipettes() {
    pullRope(pinch_rotations);

    // Report back to PC
    Serial.println("Pipettes successfully pinched");
}

void releasePipettes() {
    pullRope(-1 * pinch_rotations);

    // Report back to PC
    Serial.println("Pipettes successfully released");
}

void tensionRope() {
    pullRope(tension_rotations);
    pullRope(pinch_rotations);
    pullRope(-1 * pinch_rotations);
}

long mmToSteps(float milli, bool horizontal, int motor) {
    // Else, check if motors are vertical (Z) or horizontal (XY). Z motor uses threaded rod, XY motors use belts/pulleys
    if (horizontal == true) {
        // XY Motion
        steps = floor(motorDir[motor] * MICROSTEPS * STEPS_REV * milli / (2 * PI * PULLEY_RADIUS));
    }
    else {
        // Z Motion
        steps = floor(motorDir[motor] * MICROSTEPS * STEPS_REV * milli / ROD_PITCH);
    }

    return steps;
};

void motorsRun() {
    relayOn();

    // Run until complete (Z motor moves first to avoid clashes)
    Z_MOTOR.runToPosition();

    while ( (X_MOTOR.distanceToGo() != 0) || (Y_MOTOR.distanceToGo() != 0) ) {
        Y_MOTOR.run();
        X_MOTOR.run();
    }
};

void gantryHardHome() {
    // Slow down motors for required homing collision
    X_MOTOR.setMaxSpeed(HOMING_SPEED);
    Y_MOTOR.setMaxSpeed(HOMING_SPEED);
    Z_MOTOR.setMaxSpeed(Z_HOMING_SPEED);

    // Move towards hard pads
    X_MOTOR.move(mmToSteps(jointLimit[1][0] + x_shift, true, 0)); // X motor homes at max X value
    Y_MOTOR.move(-1 * mmToSteps(jointLimit[1][1], true, 1)); // Y motor homes at zero
    Z_MOTOR.move(-1 * mmToSteps(jointLimit[1][2], false, 2)); // Z motor homes at zero

    motorsRun();

    // Move to home position
    X_MOTOR.move(mmToSteps(home[0], true, 0));
    Y_MOTOR.move(mmToSteps(home[1], true, 1));
    Z_MOTOR.move(mmToSteps(home[2], false, 2));

    motorsRun();

    // Set positions to Zero
    X_MOTOR.setCurrentPosition(0);
    Y_MOTOR.setCurrentPosition(0);
    Z_MOTOR.setCurrentPosition(0);

    // Return to usual speeds
    X_MOTOR.setMaxSpeed(STAGE_SPEED);
    Y_MOTOR.setMaxSpeed(STAGE_SPEED);
    Z_MOTOR.setMaxSpeed(STAGE_SPEED);

    // Report back to PC
    Serial.println("Gantry Homed");
    homed = true;
};

void gantrySoftHome() {
    // Slow down motors for required homing collision
    X_MOTOR.setMaxSpeed(HOMING_SPEED);
    Y_MOTOR.setMaxSpeed(HOMING_SPEED);
    Z_MOTOR.setMaxSpeed(Z_HOMING_SPEED);

    // Send to home pads plus small distance to remove any drift
    X_MOTOR.moveTo(mmToSteps(jointLimit[1][0] + drift, true, 0));
    Y_MOTOR.moveTo(mmToSteps(-1 * drift, true, 1));
    Z_MOTOR.moveTo(mmToSteps(drift, false, 2));

    motorsRun();

    // Move to home position
    X_MOTOR.move(mmToSteps(home[0], true, 0));
    Y_MOTOR.move(mmToSteps(home[1], true, 1));
    Z_MOTOR.move(mmToSteps(home[2], false, 2));

    motorsRun();

    // Set positions to Zero
    X_MOTOR.setCurrentPosition(0);
    Y_MOTOR.setCurrentPosition(0);
    Z_MOTOR.setCurrentPosition(0);

    // Return to usual speeds
    X_MOTOR.setMaxSpeed(STAGE_SPEED);
    Y_MOTOR.setMaxSpeed(STAGE_SPEED);
    Z_MOTOR.setMaxSpeed(Z_STAGE_SPEED);

    // Report back to PC
    Serial.println("Gantry Homed");
    homed = true;
};

void gantryMove(float x, float y, float z) {
    StartTime = ceil( millis() / 1000 );

    // check if requested angle is with in hardcoded limits
    if (x < jointLimit[0][0]) {
        x = jointLimit[0][0];
    }
    else if (x > jointLimit[1][0]) {
        x = jointLimit[1][0];
    }

    // add steps
    X_MOTOR.moveTo(mmToSteps(x, true, 0));

    if (y < jointLimit[0][1]) {
        y = jointLimit[0][1];
    }
    else if (y > jointLimit[1][1]) {
        y = jointLimit[1][1];
    }

    Y_MOTOR.moveTo(mmToSteps(y, true, 1));

    if (z < jointLimit[1][2]) {
        z = jointLimit[1][2];
    }
    else if (z > jointLimit[0][2]) {
        z = jointLimit[0][2];
    }

    Z_MOTOR.moveTo(mmToSteps(z, false, 2));

    motorsRun();
    homed = false;

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;
    
    // Report back to PC
    Serial.println("Move complete in " + String(ElapsedTime) + "s");
};

void gantryZero() {
    // Move X to middle of workspace to avoid pipette rack
    X_MOTOR.moveTo(mmToSteps(jointLimit[1][0] / 2, true, 0));
    Y_MOTOR.moveTo(0);
    Z_MOTOR.moveTo(0);

    // Reverse order to minimise risk of clashes with pipette rack and bottles
    Z_MOTOR.runToPosition();
    X_MOTOR.runToPosition();
    Y_MOTOR.runToPosition();

    X_MOTOR.moveTo(0);
    X_MOTOR.runToPosition();

    homed = true;

    // gantrySoftHome();
}

void gantryMix(int count, int servoDelay) {
    StartTime = ceil( millis() / 1000 );

    for (int i=0; i<count; i++) {
        mixer.write(servoHome + servoStart);
        delay(servoDelay);
        mixer.write(servoHome + servoEnd);
        delay(servoDelay);
    }
    
    mixer.write(servoHome);

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;

    // Report back to PC
    Serial.println("Mix complete in " + String(ElapsedTime) + "s");
};

void setup() {
  // Setup code here, will run just once on start-up

  // Set pins to be used
  pinMode(X_STEP, OUTPUT);
  pinMode(X_DIR, OUTPUT);
  pinMode(Y_STEP, OUTPUT);
  pinMode(Y_DIR, OUTPUT);
  pinMode(Z_STEP, OUTPUT);
  pinMode(Z_DIR, OUTPUT);

  pinMode(E_STEP, OUTPUT);
  pinMode(E_DIR, OUTPUT);

  pinMode(SERVO_PIN, OUTPUT);
  mixer.attach(SERVO_PIN);
  
  pinMode(RELAY_PIN, OUTPUT);

  // Set motor speeds / acceleration, XYZ speeds set before and after homing
  X_MOTOR.setAcceleration(MAX_ACCEL);
  Y_MOTOR.setAcceleration(MAX_ACCEL);
  Z_MOTOR.setAcceleration(Z_ACCEL);

  E_MOTOR.setMaxSpeed(ROPE_SPEED);
  E_MOTOR.setAcceleration(MAX_ACCEL);

  X_MOTOR.setMaxSpeed(STAGE_SPEED);
  Y_MOTOR.setMaxSpeed(STAGE_SPEED);
  Z_MOTOR.setMaxSpeed(Z_STAGE_SPEED);

  // Set positions to Zero
  X_MOTOR.setCurrentPosition(0);
  Y_MOTOR.setCurrentPosition(0);
  Z_MOTOR.setCurrentPosition(0);

  Serial.begin(9600);
  mixer.write(servoHome);
  tensionRope();

  relayOff();
  
  Serial.println("Gantry Kit Ready");
};

void loop() {
    // Main code here, to run repeatedly on a loop 
    delay(100);

    // Wait until data received from PC, via Serial (USB)
    if (Serial.available() > 0) {
        LastCall = ceil( millis() / 1000 );
        // data structure to receive = action(var1, var2..)

        // Read until open bracket to extract action, continue based on which action was requested
        action = Serial.readStringUntil('(');

        if (action == "move") {
            // Extract variables spaced by commas, then last variable up to closed bracket
            x = Serial.readStringUntil(',').toFloat() - x_shift;
            y = Serial.readStringUntil(',').toFloat();
            z = Serial.readStringUntil(')').toFloat();
            
            // Call action using received variables
            gantryMove(x, y, z);
        }
        else if (action == "softHome") {
            x = Serial.readStringUntil(')').toFloat();
            
            gantrySoftHome();
        }
        else if (action == "hardHome") {
            x = Serial.readStringUntil(')').toFloat();
            
            gantryHardHome();
        }
        else if (action == "mix") {
            count = Serial.readStringUntil(',').toInt();
            servoDelay = Serial.readStringUntil(')').toInt();

            gantryMix(count, servoDelay);
        }
        else if (action == "pinch") {
            x = Serial.readStringUntil(')').toFloat();

            pinchPipettes();
        }
        else if (action == "release") {
            x = Serial.readStringUntil(')').toFloat();

            releasePipettes();
        }
        else if (action == "returnState") {
            x = Serial.readStringUntil(')').toFloat();

            Serial.println("Gantry Kit Ready");
        }
        else {
            // Report back to PC if confused
            Serial.println("Unknown command");
        }
    }
    else {
        // Check how long since last call, move to Home if too long
        CurrentTime = ceil( millis() / 1000 );
        ElapsedTime = CurrentTime - LastCall;

        if (ElapsedTime > HomeTime) {
            if (homed == false) {
                gantryZero();  
            }
            
            relayOff();
            LastCall = CurrentTime;
        }
    }
};