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
import argparse
from importlib.resources import files as importlib_files
import invoke
import io
import ipaddress
import jsons
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
from .settings import Settings


##############################################################################
#
# The application class
#
##############################################################################

class App():
    def __init__(self):
        # load the constants
        self.constants = Constants()

        # load the settings -- must be before parsing args
        self._load_settings()

        # now parse the args
        self.organization : Settings.Organization | None = None
        options = self._parse_arguments()
        self.args = options

        # set up logging
        logging.basicConfig(format="%(levelname)s: %(module)s: %(message)s")
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

    # load the settings file during initialization.
    def _load_settings(self):
        # read the JSON settings file
        settings_file = importlib_files("ttn_mass_provision").joinpath("settings.json")
        if not settings_file.is_file():
            raise self.Error(f"Can't find setup JSON file: {settings_file}")

        settings_text = ""
        try:
            settings_text = settings_file.read_text()
        except:
            raise self.Error(f"Can't read: {settings_file}")

        settings_dict: dict = jsons.loads(settings_text)
        self.settings = settings_dict

    class Error(Exception):
        """ this is the Exception thrown by class App """
        pass

    ##########################################################################
    #
    # The second-phase initializer
    #
    ##########################################################################

    def _initialize(self):
        self.inventory_dir : pathlib.Path = Constants.DEFAULT_INVENTORY_PATH / self.organization.org_dir
        if not self.inventory_dir.is_dir():
            self.logger.error("not a directory: %s", str(self.inventory_dir))
            sys.exit(1)
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

        group = parser.add_argument_group("Provisioning options")
        group.add_argument("--organization",
                        dest="organization",
                        default=Constants.DEFAULT_ORG_NAME,
                        help="default organization name (default %(default)s).")

        options = parser.parse_args()
        if options.debug:
            options.verbose = options.debug

        # validate args.
        try:
            options.address = ipaddress.IPv4Network(options.address)
        except Exception as error:
            print("not a valid netmask: %s: %s", options.address, error)
            sys.exit(1)

        if options.organization in self.settings["organizations"]:
            try:
                self.organization = Settings.Organization(**self.settings["organizations"][options.organization])
            except Exception as e:
                raise self.Error(
                    "can't convert Organization() for organization %s: check settings.json: %s",
                                self.organization,
                                e)
        else:
            print("not a valid organization: %s", options.organization)
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
                        options=options,
                        settings=self.settings
                        )
                    )
        self.conduits = conduits
        self.conduits.sort(key=lambda conduit: conduit.mac)
        return True

    ##################################
    # Populate the Conduit type info #
    ##################################
    def get_product_ids(self) -> bool:
        result: bool = True
        for conduit in self.conduits:
            self.logger.info("%s: attributes %s", conduit.mac, conduit.product_attributes)
            if conduit.get_product_id():
                conduit.set_product_attributes()
            else:
                result = False
        return result

    ##############################
    # Populate the gateway names #
    ##############################
    def populate_gateway_names(self) -> bool:
        result: bool = True
        for conduit in self.conduits:
            result = conduit.generate_hostname(self.organization.prefix) and result
            result = conduit.generate_friendly_name(self.organization) and result
        return result

    #####################
    # Get the host keys #
    #####################
    def get_host_keys(self) -> bool:
        result : bool = True
        for conduit in self.conduits:
            if not conduit.get_gateway_public_key():
                self.logger.error("Can't get host key for %s", conduit.mac)
                result = False
        return result

    ##########################
    # Get the lorawan GW ids #
    ##########################
    def get_lora_eui64(self) -> bool:
        result : bool = True
        for conduit in self.conduits:
            if not conduit.get_lora_eui64():
                self.logger.error("Can't get LoRa EUI64 for %s", conduit.mac)
                result = False
        return result


    #################################
    # Run the app and return status #
    #################################
    def run(self) -> int:
        options = self.args
        logger = self.logger

        if not self.find_conduits():
            logger.error("couldn't find any conduits")
            return 1

        logger.info("found %d conduits: %s", len(self.conduits), [ str(x) for x in self.conduits ])

        no_ssh: List[str] = []

        for conduit in self.conduits:
            logger.info("check ssh for %s", str(conduit.ip))
            if not conduit.check_ssh_enabled():
                no_ssh.append(str(conduit.ip))

        if len(no_ssh) > 0:
            logger.error("%d Conduits could not be reached: %s", len(no_ssh), ', '.join(no_ssh))
            return 1

        logger.info("all %d Conduits were reachable", len(self.conduits))

        # get all the product IDs for the Conduits
        if not self.get_product_ids():
            logger.error("get_product_ids() failed")
            return 1

        # populate the gateway names and descriptions
        if not self.populate_gateway_names():
            logger.error("populate_gateway_names failed")
            return 1

        # populate the host keys
        if not self.get_host_keys():
            logger.error("get_host_keys() failed")
            return 1

        # populate the lora EUI64
        if not self.get_lora_eui64():
            logger.error("get_lora_eui64() failed")
            return 1

        logger.info("all done")
        return 0
