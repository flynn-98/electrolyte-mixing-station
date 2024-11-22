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

const float STAGE_SPEED = 200.0; //microsteps/s
const float PUMP_SPEED = 50; //microsteps/s
const float HOMING_SPEED = 50; //microsteps/s

const float MAX_SPEED = 200.0; //microsteps/s
const float MAX_ACCEL = 200.0; //microsteps/s2

const float MICROSTEPS = 1.0;
const float PULLEY_RADIUS = 6.0; //mm
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
const int home[3] = {1.5, 2.5, -1.0};

// Joint Limits (mm)
const float jointLimit[2][3] = {
    {0, 0, 0}, 
    {160.4, 144.0, -45.0}
};

// Joint direction coefficients: 1 or -1
// X = 0, Y = 1, Z = 2
const float motorDir[3] = {1, 1, 1};

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

  X_MOTOR.setMaxSpeed(MAX_SPEED);
  X_MOTOR.setAcceleration(MAX_ACCEL);

  Y_MOTOR.setMaxSpeed(MAX_SPEED);
  Y_MOTOR.setAcceleration(MAX_ACCEL);

  Z_MOTOR.setMaxSpeed(MAX_SPEED);
  Z_MOTOR.setAcceleration(MAX_ACCEL);

  PUMP_MOTOR.setMaxSpeed(MAX_SPEED);
  PUMP_MOTOR.setAcceleration(MAX_ACCEL);

  Serial.begin(9600);
  gantryHome();

  X_MOTOR.setSpeed(STAGE_SPEED);
  Y_MOTOR.setSpeed(STAGE_SPEED);
  Z_MOTOR.setSpeed(STAGE_SPEED);
  PUMP_MOTOR.setSpeed(PUMP_SPEED);

  Serial.println("Controller Ready");
};

void loop() {
    // put your main code here, to run repeatedly:
    if (Serial.available() > 0) {
        // data structure to receive = action(var1, var2..)

        action = Serial.readStringUntil('(');

        if (action == "move") {
            x = Serial.readStringUntil(',').toFloat();
            y = Serial.readStringUntil(',').toFloat();
            z = Serial.readStringUntil(')').toFloat();

            gantryMove(x, y, z);
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
    return steps
};

void gantryHome() {
    // Slow down motors for required homing collision
    X_MOTOR.setSpeed(HOMING_SPEED);
    Y_MOTOR.setSpeed(HOMING_SPEED);
    Z_MOTOR.setSpeed(HOMING_SPEED);

    // Move towards hard stop
    X_MOTOR.move(-1 * mmToSteps(jointLimit[1][0], true, false, 0));
    Y_MOTOR.move(-1 * mmToSteps(jointLimit[1][1], true, false, 1));
    Z_MOTOR.move(-1 * mmToSteps(-jointLimit[1][2], false, false, 2));

    while ((X_MOTOR.distanceToGo() != 0) && (Y_MOTOR.distanceToGo() != 0) && (Z_MOTOR.distanceToGo() != 0)) {
        X_MOTOR.run();
        Y_MOTOR.run();
        Z_MOTOR.run();
    }

    // Move towards home position
    X_MOTOR.move(mmToSteps(home[0], true, false, 0));
    Y_MOTOR.move(mmToSteps(home[1], true, false, 1));
    Z_MOTOR.move(mmToSteps(home[2], false, false, 2));

    while ((X_MOTOR.distanceToGo() != 0) && (Y_MOTOR.distanceToGo() != 0) && (Z_MOTOR.distanceToGo() != 0)) {
        X_MOTOR.run();
        Y_MOTOR.run();
        Z_MOTOR.run();
    }

    // Set positions to Zero
    X_MOTOR.setCurrentPosition(0);
    Y_MOTOR.setCurrentPosition(0);
    Z_MOTOR.setCurrentPosition(0);
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

    if (z < jointLimit[0][2]) {
        z = jointLimit[0][2];
    }
    else if (z > jointLimit[1][2]) {
        z = jointLimit[1][2];
    }

    Z_MOTOR.moveTo(mmToSteps(z, false, false, 2));

    // Run until complete
    while ((X_MOTOR.distanceToGo() != 0) && (Y_MOTOR.distanceToGo() != 0) && (Z_MOTOR.distanceToGo() != 0)) {
        X_MOTOR.run();
        Y_MOTOR.run();
        Z_MOTOR.run();
    }

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



