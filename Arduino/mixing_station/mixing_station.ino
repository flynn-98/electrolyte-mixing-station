#include <Servo.h>
#include <AccelStepper.h>

// Define Arduino pins for each function
const int SERVO_PIN = 3;

// Pins for XYZ stepper motors, see https://learn.sparkfun.com/tutorials/big-easy-driver-hookup-guide/all
const int X_STEP = 5;
const int X_DIR = 4;

const int Y_STEP = 7;
const int Y_DIR = 6;

const int Z_STEP = 9;
const int Z_DIR = 8;

// Pins for future Pump stepper motor
const int P_STEP = 11;
const int P_DIR = 10;

// Motor speed and acceleration parameters, stepper motors have 200 steps / revolution.
// Microsteps (per step) used for increased positional accuracy and smoother stepping
const float STEPS_REV = 200.0;
const float MICROSTEPS = 4.0;
const float GEAR_RATIO = 14.0; // Peri-Pump only

const float STAGE_SPEED = 800.0 * MICROSTEPS ; //microsteps/s
const float PUMP_SPEED = 20.0 * MICROSTEPS * GEAR_RATIO; //microsteps/s
const float HOMING_SPEED = 50.0 * MICROSTEPS; //microsteps/s
const float Z_HOMING_SPEED = 150 * MICROSTEPS; //microsteps/s

const float MAX_ACCEL = 300.0 * MICROSTEPS; //microsteps/s2

// Parameters needed to convert distances (mm) to motor steps
const float PULLEY_RADIUS = 6.34; //mm
const float ROD_PITCH = 2.0; //mm
// For future Pump stepper motor
const float ML_REV = 0.33; //ml/rev

// Parameters for Mixer (Servo)
const int servoHome = 90;
const int servoStart = 20; // +Home
const int servoEnd = 50; // +Home

// Define steppers with pins (STEP, DIR)
AccelStepper X_MOTOR(AccelStepper::DRIVER, X_STEP, X_DIR); 
AccelStepper Y_MOTOR(AccelStepper::DRIVER, Y_STEP, Y_DIR);
AccelStepper Z_MOTOR(AccelStepper::DRIVER, Z_STEP, Z_DIR); 
AccelStepper PUMP_MOTOR(AccelStepper::DRIVER, P_STEP, P_DIR);

// Create servo instance
Servo mixer;

// Gantry (CNC) Home Positions (mm), values taken from CAD model and adjusted
const float pad_thickness = 1.0; //mm 
const float x_shift = 14.0; //mm (home position shift in X direction, to avoid unwanted clash)

const float home[3] = {-167.9 + pad_thickness + x_shift, 2.0 - pad_thickness, -0.5}; 

// Joint Limits (mm), also taken from CAD model
const float jointLimit[2][3] = {
    {0, 0, 0}, 
    {165.0 - x_shift, 141.0, -44.5}
};

// Overshoot value used during Homing, any gantry drift less than this value will be corrected (in theory!)
const float drift = 8; //mm

// Joint direction coefficients: 1 or -1, for desired motor directions
// X = 0, Y = 1, Z = 2
const float motorDir[3] = {1, 1, -1};

// Maximum time in Loop before softHome (s)
const unsigned long HomeTime = 60;

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

void setup() {
  // Setup code here, will run just once on start-up
  mixer.attach(SERVO_PIN);

  // Setup OUTPUT pins
  pinMode(SERVO_PIN, OUTPUT);
  pinMode(X_STEP, OUTPUT);
  pinMode(X_DIR, OUTPUT);
  pinMode(Y_STEP, OUTPUT);
  pinMode(Y_DIR, OUTPUT);
  pinMode(Z_STEP, OUTPUT);
  pinMode(Z_DIR, OUTPUT);
  pinMode(P_STEP, OUTPUT);
  pinMode(P_DIR, OUTPUT);

  // Set motor speeds / acceleration, XYZ speeds set before and after homing
  X_MOTOR.setAcceleration(MAX_ACCEL);
  Y_MOTOR.setAcceleration(MAX_ACCEL);
  Z_MOTOR.setAcceleration(MAX_ACCEL);

  PUMP_MOTOR.setMaxSpeed(PUMP_SPEED);
  PUMP_MOTOR.setAcceleration(MAX_ACCEL);

  // Set positions to Zero
  X_MOTOR.setCurrentPosition(0);
  Y_MOTOR.setCurrentPosition(0);
  Z_MOTOR.setCurrentPosition(0);

  Serial.begin(9600);
  mixer.write(servoHome);
  gantrySoftHome();

};

void loop() {
    // Main code here, to run repeatedly on a loop 

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
        else if (action == "pump") {
            vol = Serial.readStringUntil(')').toFloat();

            gantryPump(vol);
        }
        else if (action == "mix") {
            count = Serial.readStringUntil(',').toInt();
            servoDelay = Serial.readStringUntil(')').toInt();

            gantryMix(count, servoDelay);
        }
        else {
            // Report back to PC if confused
            Serial.println("Unknown command");
        }
    }
    else {
        // Check how long since last call, softHome if too long
        CurrentTime = ceil( millis() / 1000 );
        ElapsedTime = CurrentTime - LastCall;
        Serial.println(ElapsedTime);
        if (ElapsedTime > HomeTime) {
            gantrySoftHome();
            LastCall = CurrentTime;
        }
    }
};

long mmToSteps(float milli, bool horizontal, bool pump, int motor) {
    // If Pump, use ml/rev to convert to steps
    if (pump == true) {
        steps = floor(MICROSTEPS * STEPS_REV * milli * GEAR_RATIO / ML_REV);
    }
    // Else, check if motors are vertical (Z) or horizontal (XY). Z motor uses threaded rod, XY motors use belts/pulleys
    else {
        if (horizontal == true) {
            // XY Motion
            steps = floor(motorDir[motor] * MICROSTEPS * STEPS_REV * milli / (2 * PI * PULLEY_RADIUS));
        }
        else {
            // Z Motion
            steps = floor(motorDir[motor] * MICROSTEPS * STEPS_REV * milli / ROD_PITCH);
        }
    }
    return steps;
};

void motorsRun() {
    // Run until complete
    while ( (X_MOTOR.distanceToGo() != 0) || (Y_MOTOR.distanceToGo() != 0) || (Z_MOTOR.distanceToGo() != 0) ) {
        Z_MOTOR.run();
        Y_MOTOR.run();
        X_MOTOR.run();
    }
};

void motorsHome() {
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
    X_MOTOR.move(mmToSteps(jointLimit[1][0], true, false, 0)); // X motor homes at max X value
    Y_MOTOR.move(-1 * mmToSteps(jointLimit[1][1], true, false, 1)); // Y motor homes at zero
    Z_MOTOR.move(-1 * mmToSteps(jointLimit[1][2], false, false, 2)); // Z motor homes at zero

    motorsHome();

    // Move to home position
    X_MOTOR.move(mmToSteps(home[0], true, false, 0));
    Y_MOTOR.move(mmToSteps(home[1], true, false, 1));
    Z_MOTOR.move(mmToSteps(home[2], false, false, 2));

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
};

void gantrySoftHome() {
    // Slow down motors for required homing collision
    X_MOTOR.setMaxSpeed(HOMING_SPEED);
    Y_MOTOR.setMaxSpeed(HOMING_SPEED);
    Z_MOTOR.setMaxSpeed(Z_HOMING_SPEED);

    // Send to home pads plus small distance to remove any drift
    X_MOTOR.moveTo(mmToSteps(jointLimit[1][0] + drift, true, false, 0));
    Y_MOTOR.moveTo(mmToSteps(-1 * drift, true, false, 1));
    Z_MOTOR.moveTo(mmToSteps(drift, false, false, 2));

    motorsHome();

    // Move to home position
    X_MOTOR.move(mmToSteps(home[0], true, false, 0));
    Y_MOTOR.move(mmToSteps(home[1], true, false, 1));
    Z_MOTOR.move(mmToSteps(home[2], false, false, 2));

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
    X_MOTOR.moveTo(mmToSteps(x, true, false, 0));

    if (y < jointLimit[0][1]) {
        y = jointLimit[0][1];
    }
    else if (y > jointLimit[1][1]) {
        y = jointLimit[1][1];
    }

    Y_MOTOR.moveTo(mmToSteps(y, true, false, 1));

    if (z < jointLimit[1][2]) {
        z = jointLimit[1][2];
    }
    else if (z > jointLimit[0][2]) {
        z = jointLimit[0][2];
    }

    Z_MOTOR.moveTo(mmToSteps(z, false, false, 2));

    motorsRun();

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;
    
    // Report back to PC
    Serial.println("Move complete in " + String(ElapsedTime) + "s");
};

void gantryPump(float vol) {
    StartTime = ceil( millis() / 1000 );

    // No limits for Pump
    PUMP_MOTOR.move(mmToSteps(vol, false, true, 0));

    // Run until complete
    PUMP_MOTOR.runToPosition();

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;

    // Report back to PC
    Serial.println("Pump complete in " + String(ElapsedTime) + "s");
};

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



