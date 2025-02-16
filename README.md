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
<!-- TOC depthFrom:2 updateOnSave:true -->

- [Introduction](#introduction)
    - [Preconditions](#preconditions)
    - [Post conditions](#post-conditions)
- [Logistics](#logistics)
    - [Set up this script from a Python virtual environment](#set-up-this-script-from-a-python-virtual-environment)
- [Running the program](#running-the-program)
- [Important gotchas](#important-gotchas)
- [Meta](#meta)
    - [Git repo (for code and issues)](#git-repo-for-code-and-issues)
    - [Author](#author)
    - [Status](#status)
    - [Future Directions](#future-directions)
    - [Prerequisites](#prerequisites)
    - [License](#license)

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

## Running the program

In most cases, the following command will work:

```bash
python -m ttn_mass_provision -P {password} -vvv
```

Messages containing the string "ERROR:" indicate that something has gone wrong and that the program didn't work. If you can't figure out why you're getting an error, try adding the `--debug` option to the command line.

## Important gotchas

#. __*DO NOT*__ use the command `python3` to launch `ttn_mass_provision` when running in a `.venv`.  For some reason, they replace `python` in the virtual environment but they don't bother to replace `python3`. So you'll get the wrong python, and things will fail mysteriously.

#. Watch out for tab completion when writing the command. On many systems, if you use `<tab>` to auto comlpete `ttn_mass_provision`, you'll get a trailing `/`.  THe command `python -m ttn_mass_provision/` typically does not work.

## Meta

### Git repo (for code and issues)

https://github.com/things-nyc/ttn_mass_provision

### Author

Terry Moore

### Status

2025-02-15: This tool works, but it's rough, especially when it comes to error handling.

### Future Directions

* See [Issues](https://github.com/things-nyc/ttn_mass_provision/issues) page on GitHub.

### Prerequisites

V0.9.0-pre3 was tested on macOS 14.6.1 arm64 (as reported by `sw_vers`) with python3 v3.12.4. It's also been tested on Debian with Python v3.11.

### License

Released under MIT license.
