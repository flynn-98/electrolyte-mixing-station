# Electrolyte Mixing Station (MicroTron)

## Introduction

The Electrolyte Mixing Station is a customisable tool, designed to select and mix microlitres of different electrolytes, using a volume control module and pipette system that can be configured to deal with low and high viscosities.

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

## Accelerated Life Tests

Accelerated life tests can be run using a command line tool, allowing for a single PC to run tests on multiple mixing stations at once. For each device, open a new terminal and run the following command:

```
accelerated-life-test --device_name microtron_01 --repeats 50
```

Run `accelerated-life-test --help` for more information. 

**Accelerated life tests should be run without any liquids to avoid unsupervised spillages.**

## References
1. [Smart Pump Module](https://www.theleeco.com/product/smart-pump-module/#resources)