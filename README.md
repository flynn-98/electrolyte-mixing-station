# Electrolyte Mixing Station

## Introduction

The Electrolyte Mixing Station is a customisable tool, designed to select and mix microlitres of different electrolytes, using a volume control module and pipette system that can be configured to deal with low and high viscosities.

![image](data/images/CAD.png)

### Jump to the [Workspace Notebook](workspace.ipynb) for instructions on how to use the mixing station!

## Installing Dependencies

Run the following in the root directory:

```
pip install .
```

Or possibly:

```
python3 -m pip install .
```

## Accelerated Life Tests

Accelerated life tests can be run using a command line tool, allowing for a single PC to run tests on multiple mixing stations at once. For each device, open a new terminal and run the following command:

```
accelerated-life-test --gantry /dev/cu.usbmodem1101 --pipette /dev/cu.usbmodem1301 --repeats 50
```

The USB port addresses for each gantry and pipette will need to be entered manually. The `--pipette_sim` and `--gantry_sim` flags can be used if just a single system is to be tested. Run `accelerated-life-test --help` for more information.

**Accelerated life tests should be run without any liquids to avoid unsupervised spillages.**

## References
1. [Smart Pump Module](https://www.theleeco.com/product/smart-pump-module/#resources)