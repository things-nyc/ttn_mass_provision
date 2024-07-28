# `ttn_mass_provision`

`ttn_mass_provision` is used to provision one or more MultiTech Conduits with TTN-Ithaca firmware, typically one with fresh firmware after a deployment. It configures the Conduit to connect to a jumphost (typically `jumphost.ttni.tech`) and sets up files needed for use with the [IthacaThings administration system](https://github.com/IthacaThings/ttn-multitech-cm) by Jeff Honig.

<!-- TOC depthfrom:2 updateonsave:true -->

- [Introduction](#introduction)

<!-- /TOC -->

## Introduction

TODO

## Set up this script from a Python virtual environment

This is the recommended approach, as it doesn't require making any global environment changes other than installing python3.  We tested with Python 3.12.3.

```bash
git clone git@github.com:things-nyc/ttn_mass_provision
cd ttn_mass_provision

# after cloning, create the .venv
python3 -m venv .venv

# set up the virtual environment
source .venv/bin/activate

# get the remaining requirements into the virtual environment
python3 -m pip install -r requirements.txt

# make sure the script is functional
python3 -m ttn_mass_provision --help
```
