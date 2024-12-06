# Electrolyte Mixing Station

## Introduction

The Electrolyte Mixing Station (or Microtron) is a customisable tool, designed to select and mix microlitres of different electrolytes, using a volume control module and pipette system that can be configured to deal with low and high viscosities.

![image](data/images/CAD.png)

### Jump to the [Workspace Notebook](workspace.ipynb) for instructions on how to use the mixing station!

## Installing Dependencies

Build venv in root directory:

```
python3 -m venv .venv
```

Install dependencies into new venv:

```
.venv/bin/pip install .
```

Activate venv:

```
source .venv/bin/activate
```

## Device Data and Configuration

Information on each device can be found [here](data/devices/mixing_stations.json). To add a new device, simply copy and paste the last device entry, increment the ID and rename the COM port addresses. The easiest was to determine these addresses, is to connect the device and go to [PlatformIO's](https://docs.platformio.org/en/latest/integration/ide/vscode.html) *Devices* tab.

## Run Experiments from Command Line

Experiments can be run using a command line tool, allowing for a single PC to run tests on multiple mixing stations at once. For each device, open a new terminal and run the following command:

```
run-experiment --device_name microtron_01 --repeats 1
```

Run `run-experiment --help` for more information. The electrolyte mixing ratios and aspiration variables will be pulled from [here](data/CSVs/electrolyte_recipe.csv).

## Accelerated Life Tests

**Accelerated life tests should be run without any liquids to avoid unsupervised spillages.**

```
accelerated-life-test --device_name microtron_01 --repeats 20
```

Run `accelerated-life-test --help` for more information. 

## References
1. [Smart Pump Module](https://www.theleeco.com/product/smart-pump-module/#resources)