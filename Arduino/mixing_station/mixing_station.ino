#include <Servo.h>
#include <AccelStepper.h>

const int SERVO_PIN = 3;

const int X_STEP = 5;
const int X_DIR = 4;

const int Y_STEP = 7;
const int Y_DIR = 6;

const int Z_STEP = 9;
const int Z_DIR = 8;

const int P_STEP = 1;
const int P_DIR = 0;

const float MICROSTEPS = 4.0;

const float STAGE_SPEED = 800.0 * MICROSTEPS ; //microsteps/s
const float PUMP_SPEED = 50 * MICROSTEPS; //microsteps/s
const float HOMING_SPEED = 50 * MICROSTEPS; //microsteps/s
const float Z_HOMING_SPEED = 150 * MICROSTEPS; //microsteps/s

const float MAX_ACCEL = 400.0; //microsteps/s2

const float PULLEY_RADIUS = 6.2; //mm
const float ROD_PITCH = 2.0; //mm
const float STEPS_REV = 200.0;
const float ML_REV = 0.2; //ml/rev

// Define steppers and the pins it will use (STEP, DIR)
AccelStepper X_MOTOR(AccelStepper::DRIVER, X_STEP, X_DIR); 
AccelStepper Y_MOTOR(AccelStepper::DRIVER, Y_STEP, Y_DIR);
AccelStepper Z_MOTOR(AccelStepper::DRIVER, Z_STEP, Z_DIR); 
AccelStepper PUMP_MOTOR(AccelStepper::DRIVER, P_STEP, P_DIR);

// Create servo instance
Servo mixer;

// Joint Home Positions (mm)
const float pad_thickness = 1.0; //mm 
const float x_shift = 20.0; //mm to avoid clash between VCM and X carriage
const float home[3] = {-167.9 + pad_thickness + x_shift, 2.9 - pad_thickness, -1.0}; // Taken from CAD

// Joint Limits (mm) also from CAD
const float jointLimit[2][3] = {
    {0, 0, 0}, 
    {165.0 - x_shift, 144.0, -44.0}
};

const float drift = 6; //mm

// Joint direction coefficients: 1 or -1
// X = 0, Y = 1, Z = 2
const float motorDir[3] = {1, 1, -1};

float x = 0;
float y = 0;
float z = 0;
float vol = 0;
float duration = 0;

unsigned long StartTime;
unsigned long CurrentTime;
unsigned long ElapsedTime;

long steps;

String action;

void setup() {
  // put your setup code here, to run once:
  pinMode(SERVO_PIN, OUTPUT);
  pinMode(X_STEP, OUTPUT);
  pinMode(X_DIR, OUTPUT);
  pinMode(Y_STEP, OUTPUT);
  pinMode(Y_DIR, OUTPUT);
  pinMode(Z_STEP, OUTPUT);
  pinMode(Z_DIR, OUTPUT);
  pinMode(P_STEP, OUTPUT);
  pinMode(P_DIR, OUTPUT);

  mixer.attach(SERVO_PIN);

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
  gantrySoftHome();

};

void loop() {
    // put your main code here, to run repeatedly:
    if (Serial.available() > 0) {
        // data structure to receive = action(var1, var2)

        action = Serial.readStringUntil('(');

        if (action == "move") {
            x = Serial.readStringUntil(',').toFloat() - x_shift;
            y = Serial.readStringUntil(',').toFloat();
            z = Serial.readStringUntil(')').toFloat();
            
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
            duration = Serial.readStringUntil(')').toFloat();

            // gantryMix(duration);
        }
        else {
            Serial.println("Unknown command");
        }

        // TODO SERVO / MIXING
    }
};

long mmToSteps(float milli, bool horizontal, bool pump, int motor) {
    if (pump == true) {
        steps = floor(MICROSTEPS * STEPS_REV * milli * 2 * PI / ML_REV);
    }
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
    // Z_MOTOR.runToPosition();
    // Y_MOTOR.runToPosition();
    // X_MOTOR.runToPosition();

    while ( (X_MOTOR.distanceToGo() != 0) || (Y_MOTOR.distanceToGo() != 0) || (Z_MOTOR.distanceToGo() != 0) ) {
        Z_MOTOR.run();
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

    motorsRun();

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

    motorsRun();

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

    Serial.println("Move complete in " + String(ElapsedTime) + "s");
};

void gantryPump(float vol) {
    StartTime = ceil( millis() / 1000 );

    // No limits for Pump
    PUMP_MOTOR.moveTo(mmToSteps(vol, false, true, 0));

    // Run until complete
    while (PUMP_MOTOR.distanceToGo() != 0) {
        PUMP_MOTOR.run();
    }

    CurrentTime = ceil( millis() / 1000 );
    ElapsedTime = CurrentTime - StartTime;

    Serial.println("Pump complete in " + String(ElapsedTime) + "s");
};



