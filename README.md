# Electrolyte Mixing Station

## Introduction

The Electrolyte Mixing Station is a flexible tool, primarily designed to select and mix microlitres of different electrolytes, using a volume control module that can be configured to deal with low and higher viscosities.

![image](data/images/workflow.png)

### Be sure to follow all the steps to set up the virtual environment!

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

## Setting up SquidstatPyLibrary (Windows Only!)

Download latest *.whl* file from [here](https://github.com/Admiral-Instruments/AdmiralSquidstatAPI/tree/main/SquidstatLibrary/windows/pythonWrapper/Release). Move the file to the *electrolyte-mixing-station* and run the following command:

```
.venv/bin/pip install FILE.whl
```

## Setting up Atinary SDK

Download latest *.tar.gz* file from [here](https://scientia.atinary.com/download/). Move the file to the *electrolyte-mixing-station* and run the following command:

```
.venv/bin/pip install FILE.tar.gz
```

## Using Platformio to Flash Latest Firmware

Install the [PlatformIO VSCode Extension](https://docs.platformio.org/en/latest/integration/ide/vscode.html) and open a new Pio terminal (found in *Quick Access/Miscellaneous*). Change directory to either *gantry-kit* or *fluid-handling-kit* in the terminal, then connect the the target Arduino Nano via USB and run the following command:

```
cd gantry-kit/
```

```
pio run --target upload
```

## Device Configuration

Com port addresses for each device can be found [here](data/devices/mixing_stations.json). To add a new device, simply copy and paste the last device entry, increment the ID and rename the COM port addresses. The easiest way to determine these addresses, is to connect the device(s) and go to [PlatformIO's](https://docs.platformio.org/en/latest/integration/ide/vscode.html) *Devices* tab.

By toggling the booleans, you can activate or deactivate the various com port connections for scenarios where not all connections are needed.

## Run Experiments

Experiments can be run using a command line tool, allowing for a single PC to run tests on multiple mixing stations at once. For each device, open a new terminal and run the following command:

```
run-experiment --device_name microtron_01
```

Run `run-experiment --help` for more information. The electrolyte mixing ratios and aspiration variables will be pulled from [here](data/CSVs/electrolyte_recipe.csv) (for now).

**Jump to the [workspace jupyter notebook](Workspace.ipynb) for more guidance on how to use the mixing station!**

## Recommended Extensions

For easy viewing and editing of CSVs, it is recommended that you download [this CSV extension](https://marketplace.visualstudio.com/items?itemName=ReprEng.csv) for VS Code.

## References
1. [Smart Pump Module](https://www.theleeco.com/product/smart-pump-module/#resources)
2. [Laird Temperature Controller](https://lairdthermal.com/products/product-temperature-controllers/tc-xx-pr-59-temperature-controller?creative=&keyword=&matchtype=&network=x&device=c&gad_source=1&gclid=CjwKCAiAzPy8BhBoEiwAbnM9O_ueQ3Ph8NvZ4LYCpqO9oUzX78J1sfagfGnYWUDeDpQ8P9rKzc11pBoCUR8QAvD_BwE)
3. [PCX Peltier Module](https://lairdthermal.com/products/thermoelectric-cooler-modules/peltier-thermal-cycling-pcx-series)
4. [Kern Mass Balance](https://www.kern-sohn.com/shop/en/products/laboratory-balances/precision-balances/PCD-2500-2/)
5. [Boxer Pump](https://www.boxerpumps.com/peristaltic-pumps-for-liquid/29qq/)
6. [Atinary Self-Driving Labs](https://scientia.atinary.com/sdlabs/academic/dashboard)
7. [Squidstat API Manual](https://admiral-instruments.github.io/AdmiralSquidstatAPI/index.html)