# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`ttn_mass_provision` is a CLI that prepares MultiTech Conduit gateways (running TTN Ithaca mLinux) on a local Ethernet segment so that `ttn-multitech-cm` (Ansible) can manage them through a jumphost (`jumphost.ttni.tech`). It finds the Conduits, reads their identity over ssh, creates a matching user on the jumphost, and installs a reverse ssh tunnel on each Conduit. It implements the procedure in `HOWTO-MASS-PROVISION.md` of `terrillmoore/conduit-mfg`.

## Commands

The project uses uv; Python 3.11 or later.

```bash
uv sync                                   # create .venv from uv.lock
uv run ttn_mass_provision --help
uv run ttn_mass_provision -P {password} -vvv          # normal run
uv run ttn_mass_provision -P {password} -M 192.168.12.5,192.168.12.6 -d
uv lock --upgrade                         # or: make lock
uv build                                  # or: make build; output in dist/
```

There are no tests and no linter configuration. A real run needs Conduits on the local network and an ssh agent that can log in to the jumphost and `sudo` there; `--help` and `--version` are the only checks possible without them.

The arp-based Conduit search runs a `sh` loop of `ping` plus `arp -an` on the local host, so a full run needs Linux or macOS. `-M` (`--manual`) skips that search.

## Architecture

`__main__.main()` builds `app.App`, whose `run()` executes a fixed sequence of steps. Each step loops over all Conduits or jumphosts and returns `bool`; the first failure logs an error and ends the run with status 1. The order in `App.run()`:

1. reach each jumphost by ssh;
2. find Conduits (arp scan of `--address`, default `192.168.12.0/24`, matching MultiTech MAC prefix `00:08:00`; or the `-M` list);
3. check ssh login to each Conduit (`-S` skips failures instead of stopping);
4. read MAC, product ID (`mts-io-sysfs show product-id`), ssh host key, and LoRa EUI-64 from each Conduit;
5. on the jumphost, create the org's gateway group and one user per Conduit, named `{org prefix}{mac}`, with the Conduit's host key in its `authorized_keys`;
6. on each Conduit, install `ssh_tunnel` as `/etc/init.d/ssh_tunnel`, write `/etc/default/ssh_tunnel`, add `conduit_authorized_keys.pub` to root's keys under `/var/config/home/root/.ssh`, and start the tunnel.

Port numbering: the gateway's jumphost UID is also its reverse-tunnel port. The autossh keepalive port is `(uid - 20000) * 2 + 40000` (`Constants.JUMPHOST_FIRST_UID`, `JUMPHOST_FIRST_KEEPALIVE`). `useradd` gets `UID_MIN=20000`, so the jumphost assigns the UID.

ssh layers:
- `ConduitSsh` (`conduit_ssh.py`) logs in with `--username` (default `mtadm`) and `--password`, with the ssh agent disabled.
- `JumphostSsh` (`jumphost_ssh.py`) logs in as the local user through the ssh agent and uses passwordless `sudo`.
- Both wrap `fabric.Connection`. Their `do()` and `sudo()` return `None` on an exception and a `fabric.Result` (with `warn=True`) otherwise, so callers check `answer == None or not answer.ok`.
- `--noop` passes `dry=True` only to `sudo()`; read-only `do()` commands still run.

Data files, loaded from the package with `importlib.resources` (so they must stay listed in `[tool.setuptools.package-data]` in `pyproject.toml`):
- `settings.json` holds `product_id_map` (Conduit product ID to device class/type and cellular flag), `organizations` (hostname prefix, inventory directory, jumphost list), and `jumphosts`. A Conduit whose product ID is missing from `product_id_map` stops the run; adding a new model means adding an entry there.
- `ssh_tunnel` is the init script copied to each Conduit.
- `conduit_authorized_keys.pub` holds the admin keys installed for root on each Conduit.

`App` keeps `settings.json` as a plain dict and builds the dataclasses in `settings.py` (`Organization`, `JumphostAttributes`, `ProductAttributes`) from it when needed, filling defaults first and then overlaying the JSON values.

The org's inventory directory must exist at `../{org_dir}` relative to the current directory (`Constants.DEFAULT_INVENTORY_PATH`); `App._initialize()` exits otherwise. Exactly one jumphost per organization is allowed, although the loops are written for several.

Not yet implemented: the README's post conditions 3 to 5 (writing Ansible host_vars files and updating the inventory `hosts` file). `hostvars_template.yml` and `atomicfile.py` are for that work and nothing imports them yet.

## Conventions

- The version lives only in `ttn_mass_provision/__version__.py`, spelled in PEP 440 form (`0.9.0rc4`); `pyproject.toml` reads it dynamically.
- Each module sets its own logger level from `options.debug` / `options.verbose`. Error messages for common failures tell the user what to check (ssh agent, jumphost `sudo`, gateway DNS).
- Files start with the `####` banner block (Name, Function, Copyright notice and license, Author). The license is MIT (`LICENSE.md`).
