# `ttn_mass_provision`

`ttn_mass_provision` is used to provision one or more MultiTech Conduits with TTN-Ithaca firmware, typically one with fresh firmware after a deployment. It configures the Conduit to connect to a jumphost (typically `jumphost.ttni.tech`) and sets up files needed for use with the [IthacaThings administration system][1] by Jeff Honig.

[1]: https://github.com/IthacaThings/ttn-multitech-cm
[2]: https://github.com/terrillmoore/conduit-mfg.git
[3]: https://github.com/terrillmoore/conduit-mfg/blob/master/HOWTO-MASS-PROVISION.md

<!-- markdownlint-disable MD033 -->
<!-- markdownlint-disable MD004 -->
<!-- don't complain about starting bulleted list with '*' -->
<!-- markdownlint-capture -->
<!-- markdownlint-disable -->
<!-- TOC depthfrom:2 updateonsave:true -->

- [Introduction](#introduction)
    - [Preconditions](#preconditions)
    - [Post conditions](#post-conditions)
- [Logistics](#logistics)
    - [Set up this script from a Python virtual environment](#set-up-this-script-from-a-python-virtual-environment)

<!-- /TOC -->
<!-- markdownlint-restore -->
<!-- Due to a bug in Markdown TOC, the table is formatted incorrectly if tab indentation is set other than 4. Due to another bug, this comment must be *after* the TOC entry. -->

## Introduction

Connecting a gateway to the jumphost in a consistend way is a complicated multi-step process. Although there is an effective procedure given in [`HOWTO-MASS-PROVISION.md`][3] in [`conduit-mfg`][2], the procedure is long, error prone, and not suitable for common use.

This application is intended to implement that procedure, up to but not including invoking Ansible to do the mass provisioning for the set of gateways.

### Preconditions

* One or more MultiTech Conduits running TTN Ithaca mLinux connected to a local Ethernet network.  The network must have connectivity to the cloud.
* A Unix system connected to the same local Ethernet network. The Unix system will be used to run this program.
* Knowledge of the password used for `root` logins on the local Ethernet adapter.
* An SSH public key to be used for connecting to the Conduits. This must match a private key loaded into your ssh agent.
* Access to `jumphost.ttni.tech`, with `sudo` privileges.
* A checked out copy of the gateway inventory for `ttn-multitech-cm`.

### Post conditions

If successful, this script establishes the following post conditions.

1. It is possible to connect to each Conduit via the jumphost.

2. Each Conduit is ready to do a `make ping` in `ttn-multitech-cm`.

3. Yaml inventory files have been created for each conduit in the inventory directory.

4. The `hosts` file in the inventory has been updated with the gateway in the a suitable group of gateways.

5. Instructions are printed on how to do a `make apply`.

## Logistics

### Set up this script from a Python virtual environment

This is the recommended approach, as it doesn't require making any global environment changes other than installing python3.  We tested with Python 3.12.3.

```bash
git clone git@github.com:things-nyc/ttn_mass_provision
cd ttn_mass_provision

# after cloning, create the .venv
make venv

# set up the virtual environment
# follow the prompt, but normally:
source .venv/bin/activate

# make sure the script is functional
python -m ttn_mass_provision --help
```
