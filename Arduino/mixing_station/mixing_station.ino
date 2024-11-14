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

const long STAGE_SPEED = 3000; //microsteps/s
const long PUMP_SPEED = 3000; //microsteps/s
const long HOMING_SPEED = 1500; //microsteps/s
const long MAX_ACCEL = 1000; //microsteps/s2

const float MICROSTEPS = 4.0;
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
const float jointLimits[2][3] = {
    {0, 0, 0}, 
    {160.4, 144.0, -45.0}
};

float x = 0;
float y = 0;
float z = 0;
float pump = 0;

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

  X_MOTOR.setMaxSpeed(STAGE_SPEED);
  X_MOTOR.setAcceleration(MAX_ACCEL);

  Y_MOTOR.setMaxSpeed(STAGE_SPEED);
  Y_MOTOR.setAcceleration(MAX_ACCEL);

  Z_MOTOR.setMaxSpeed(STAGE_SPEED);
  Z_MOTOR.setAcceleration(MAX_ACCEL);

  PUMP_MOTOR.setMaxSpeed(PUMP_SPEED);
  PUMP_MOTOR.setAcceleration(MAX_ACCEL);

  X_MOTOR.setSpeed(HOMING_SPEED);
  Y_MOTOR.setSpeed(HOMING_SPEED);
  Z_MOTOR.setSpeed(HOMING_SPEED);

  Serial.begin(9600);
  robotHome();

  X_MOTOR.setSpeed(STAGE_SPEED);
  Y_MOTOR.setSpeed(STAGE_SPEED);
  Z_MOTOR.setSpeed(STAGE_SPEED);
  PUMP_MOTOR.setSpeed(PUMP_SPEED);

  Serial.println("Controller Ready");
};

void loop() {
  // put your main code here, to run repeatedly:
  if (Serial.available() > 0) {
    // data structure to receive = x,y,z,pump;
      x = Serial.readStringUntil(',').toFloat();
      y = Serial.readStringUntil(',').toFloat();
      z = Serial.readStringUntil(',').toFloat();
      pump = Serial.readStringUntil(';').toFloat();

      robotMove(x, y, z, pump);
  }
};

long mmToSteps(float milli, bool horizontal, bool pump) {
    if (pump == true) {
        return MICROSTEPS * STEPS_REV * milli * 2 * PI / ML_REV;
    }
    else {
        if (horizontal == true) {
            return MICROSTEPS * STEPS_REV * milli / (2 * PI * PULLEY_RADIUS);
        }
        else {
            return MICROSTEPS * STEPS_REV * milli / ROD_PITCH;
        }
    }
};

void robotHome() {
    // Move towards hard stop
    X_MOTOR.move(-1 * mmToSteps(jointLimits[1][0], true, false));
    Y_MOTOR.move(-1 * mmToSteps(jointLimits[1][1], true, false));
    Z_MOTOR.move(-1 * mmToSteps(-jointLimits[1][2], false, false));

    while ((X_MOTOR.distanceToGo() != 0) && (Y_MOTOR.distanceToGo() != 0) && (Z_MOTOR.distanceToGo() != 0)) {
        X_MOTOR.run();
        Y_MOTOR.run();
        Z_MOTOR.run();
    }

    // Move towards home position
    X_MOTOR.move(mmToSteps(home[0], true, false));
    Y_MOTOR.move(mmToSteps(home[1], true, false));
    Z_MOTOR.move(mmToSteps(home[2], false, false));

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

void robotMove(float x, float y, float z, float pump) {
    unsigned long StartTime = ceil( millis() / 1000 );

    // check if requested angle is with in hardcoded limits
    if (x < jointLimits[0][0]) {
        x = jointLimits[0][0];
    }
    else if (x > jointLimits[1][0]) {
        x = jointLimits[1][0];
    }

    // add steps
    X_MOTOR.moveTo(mmToSteps(x, true, false));

    if (y < jointLimits[0][1]) {
        y = jointLimits[0][1];
    }
    else if (y > jointLimits[1][1]) {
        y = jointLimits[1][1];
    }

    Y_MOTOR.moveTo(mmToSteps(y, true, false));

    if (z < jointLimits[0][2]) {
        z = jointLimits[0][2];
    }
    else if (z > jointLimits[1][2]) {
        z = jointLimits[1][2];
    }

    Z_MOTOR.moveTo(mmToSteps(z, false, false));

    // No limits for Pump
    PUMP_MOTOR.moveTo(mmToSteps(pump, false, true));

    // Run until complete
    while ((X_MOTOR.distanceToGo() != 0) && (Y_MOTOR.distanceToGo() != 0) && (Z_MOTOR.distanceToGo() != 0) && (PUMP_MOTOR.distanceToGo() != 0)) {
        X_MOTOR.run();
        Y_MOTOR.run();
        Z_MOTOR.run();
        PUMP_MOTOR.run();
    }

    unsigned long CurrentTime = ceil( millis() / 1000 );
    unsigned long ElapsedTime = CurrentTime - StartTime;

    Serial.println("Move Complete in " + String(ElapsedTime) + "s");
};


