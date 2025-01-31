# Electrolyte Mixing Station

## Introduction

The Electrolyte Mixing Station (or Microtron) is a customisable tool, designed to select and mix microlitres of different electrolytes, using a volume control module that can be configured to deal with low and high viscosities.

**Make sure to follow ALL the below set up steps!**

![image](data/images/CAD.png)

## Installing Dependencies

Build venv in root directory:

```
python3 -m venv .venv
```

Install dependencies into new venv:

```
.venv/bin/pip install -e .
```

Activate venv:

```
source .venv/bin/activate
```

## Setting up Squidstat Python API

### Mac & Linux (Build API using CMake)

For Mac & Linux users, follow the instructions given [here](https://admiral-instruments.github.io/AdmiralSquidstatAPI/md_intro_and_examples_2__build__a_p_i_using__cmake.html) to build the SquidstatLibrary.

For Mac users, it is recommended that you use `brew` to download cmake:

```
brew install cmake
```

### Windows (SquidstatPyLibrary)

For Windows users, a Python wrapper can be used. Download latest *.whl* file from [here](https://github.com/Admiral-Instruments/AdmiralSquidstatAPI/tree/main/SquidstatLibrary/windows/pythonWrapper/Release). Move the file to the *electrolyte-mixing-station* and run the following command:

```
.venv/bin/pip install FILE.whl
```

## Setting up Atinary SDK

Download latest *.tar.gz* file from [here](https://scientia.atinary.com/download/). Move the file to the *electrolyte-mixing-station* and run the following command:

```
.venv/bin/pip install FILE.tar.gz
```

## Device Data and Configuration

Information on each device can be found [here](data/devices/mixing_stations.json). To add a new device, simply copy and paste the last device entry, increment the ID and rename the COM port addresses. The easiest way to determine these addresses, is to connect the device(s) and go to [PlatformIO's](https://docs.platformio.org/en/latest/integration/ide/vscode.html) *Devices* tab.

## Using Platformio to Flash Latest Firmware

Install the [PlatformIO VSCode Extension](https://docs.platformio.org/en/latest/integration/ide/vscode.html) and open a new Pio terminal (found in *Quick Access/Miscellaneous*). Change directory to either *gantry-kit* or *fluid-handling-kit* in the terminal, then connect the the target Arduino Nano via USB and run the following command:

```
cd gantry-kit/
```

```
pio run --target upload
```

## Run Experiments from Command Line

Experiments can be run using a command line tool, allowing for a single PC to run tests on multiple mixing stations at once. For each device, open a new terminal and run the following command:

```
run-experiment --device_name microtron_01 --repeats 1
```

Run `run-experiment --help` for more information. The electrolyte mixing ratios and aspiration variables will be pulled from [here](data/CSVs/electrolyte_recipe.csv) (for now).

## Accelerated Life Tests

**Accelerated life tests should be run without any liquids to avoid unsupervised spillages.**

```
accelerated-life-test --device_name microtron_01 --repeats 20
```

Run `accelerated-life-test --help` for more information. 

## Recommended Extensions

For easy viewing and editing of CSVs, it is recommended that you download [this CSV extension](https://marketplace.visualstudio.com/items?itemName=ReprEng.csv) for VS Code.

## References
1. [Smart Pump Module](https://www.theleeco.com/product/smart-pump-module/#resources)
2. [Atinary Self-Driving Labs](https://scientia.atinary.com/sdlabs/academic/dashboard)
3. [Squidstat API Manual](https://admiral-instruments.github.io/AdmiralSquidstatAPI/index.html)