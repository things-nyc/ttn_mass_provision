##############################################################################
#
# Name: app.py
#
# Function:
#       Toplevel App() class
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

#### imports ####
from __future__ import print_function
import argparse
import invoke
import io
import ipaddress
import logging
import pathlib
import sys
import time
import typing

Any = typing.Any
Union = typing.Union
List = typing.List

from .constants import Constants
from .__version__ import __version__
from .conduit import Conduit
from .conduit_ssh import ConduitSsh

##############################################################################
#
# The application class
#
##############################################################################

class App():
    def __init__(self):
        # load the constants
        self.constants = Constants()

        # now parse the args
        options = self._parse_arguments()
        self.args = options

        # set up logging
        logging.basicConfig()
        logger = logging.getLogger(__name__)
        if options.debug:
            logger.setLevel('DEBUG')
        elif options.verbose:
            logger.setLevel('INFO')
        else:
            logger.setLevel('WARNING')

        self.logger = logger

        # verbose: report the version.
        logger.info("ttn_mass_provision v%s", __version__)

        self._initialize()
        logger.info("App is initialized")
        return

    ##########################################################################
    #
    # The second-phase initializer
    #
    ##########################################################################

    def _initialize(self):
        # self.ssh = ConduitSsh(self.args)
        pass

    ##########################################################################
    #
    # The argument parser
    #
    ##########################################################################

    def _parse_arguments(self):
        parser = argparse.ArgumentParser(
            prog="ttn_mass_provision",
            description=
                """
                Initialize all mLinux Conduits on a network segment to connect
                to a jumphost.
                """
            )

        #	Debugging
        group = parser.add_argument_group("Debugging options")
        group.add_argument("-d", "--debug",
                        dest="debug", default=False,
                        action='store_true',
                        help="Print debugging messages.")
        group.add_argument("--nodebug",
                        dest="debug",
                        action='store_false',
                        help="Do not print debugging messages.")
        group.add_argument("-v", "--verbose",
                        dest="verbose", default=False,
                        action='store_true',
                        help="Print verbose messages.")
        group.add_argument("-n", "--noop", "--dry-run",
                        dest="noop", default=False,
                        action='store_true',
                        help="Don't make changes, just list what we are going to do.")
        parser.add_argument(
                        "--version",
                        action='version',
                        help="Print version and exit.",
                        version="%(prog)s v"+__version__
                        )

        #	Options
        group = parser.add_argument_group("Configuration options")
        group.add_argument("--username", "--user", "-U",
                        dest="username", default=Constants.DEFAULT_MLINUX_USERNAME,
                        help="Username to use to connect (default %(default)s).")
        group.add_argument("--password", "--pass", "-P",
                        dest="password", required=True,
                        help="Password to use to connect. There is no default; this must always be supplied.")
        group.add_argument("--address", "-A",
                        dest="address", default=Constants.DEFAULT_IP_ADDRESS,
                        help="IP address of the network holding the Conduits, as IpV4 addr/bits (default %(default)s).")

        options = parser.parse_args()
        if options.debug:
            options.verbose = options.debug

        # validate args.
        try:
            options.address = ipaddress.IPv4Network(options.address)
        except Exception as error:
            print("not a valid netmask: %s: %s", options.address, error)
            sys.exit(1)

        return options

    #############################
    # Loop until SSH is enabled #
    #############################
    def await_ssh_available(self, /, timeout:int = 10, progress:bool = False) -> bool:
        c = self.ssh
        logger = self.logger

        begin = time.time()
        while time.time() - begin < self.args.reboot_time:
            print('.', end='', flush=True)
            if c.ping():
                print()
                logger.info("ssh available after {t} seconds".format(t=time.time() - begin))
                return True
            time.sleep(1)
        return False

    ##################################################
    # Find all the MultiTech gateways on the network #
    ##################################################
    def find_conduits(self) -> bool:
        options = self.args
        logger = self.logger

        stdout = io.StringIO()

        hosts = ' '.join([ str(host) for host in options.address.hosts()])
        cmd = "for i in %s; do { ( ping -c2 -W1 $i |& grep -q '0 received' || echo $i ; ) & disown; } done" % hosts
        try:
            logger.debug("launch command: %s", cmd)
            result = invoke.run(cmd, out_stream=stdout)
        except Exception as error:
            logger.error("mass ping failed: %s", error)
            return False

        # grab the arp buffer
        try:
            with open("/proc/net/arp", "r") as f:
                arplist = f.read().splitlines()[1:]
        except Exception as error:
            logger.error("arp read failed: %s", error)
            return False

        # for each line, split and match
        conduits: List[Conduit] = []
        for line in arplist:
            fields = line.split()
            macaddr = fields[3]
            if macaddr.startswith("00:08:00:"):
                conduits.append(
                    Conduit(
                        ip=ipaddress.IPv4Address(fields[0]),
                        mac=macaddr.replace(':', '-'),
                        options=options
                        )
                    )
        self.conduits = conduits
        return True

    #################################
    # Run the app and return status #
    #################################
    def run(self) -> int:
        options = self.args
        logger = self.logger

        if not self.find_conduits():
            logger.error("couldn't find any conduits")
            return 1

        logger.info("found %d conduits: %s", len(self.conduits), self.conduits)

        no_ssh: List[str] = []

        for conduit in self.conduits:
            logger.info("check ssh for %s", str(conduit.ip))
            if not conduit.check_ssh_enabled():
                no_ssh.append(str(conduit.ip))

        if len(no_ssh) > 0:
            logger.error("%d Conduits could not be reached: %s", len(no_ssh), ', '.join(no_ssh))
            return 1

        logger.info("all %d Conduits were reachable", len(self.conduits))

        logger.info("all done")
        return 0
