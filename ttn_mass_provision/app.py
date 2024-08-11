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
import getpass
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
from .jumphost import Jumphost
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

        # remaining arg validation
        self._validateArgs()

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

        return options

    ##########################################################################
    #
    # The argument validator; called from __init__() after setting up logging.
    #
    ##########################################################################

    def _validateArgs(self):
        options = self.args
        logger = self.logger

        # validate args.
        try:
            options.address = ipaddress.IPv4Network(options.address)
        except Exception as error:
            print("not a valid network address: %s: %s" % (options.address, error))
            sys.exit(1)

        if options.organization in self.settings["organizations"]:
            org_data = {
                "id": options.organization,
                "gateway_group": options.organization + "-gateways"
                }
            org_data |= self.settings["organizations"][options.organization]
            try:
                self.organization = Settings.Organization(**org_data)
            except Exception as e:
                raise self.Error(
                    f"can't convert Organization() for organization {options.organization:s}: check settings.json: {e}")
        else:
            print("not a valid organization: %s", options.organization)
            sys.exit(1)

        # now, get the jumphosts
        jumphosts : list[Jumphost] = []
        for jumphost_tag in self.organization.jumphosts:
            if not jumphost_tag in self.settings["jumphosts"]:
                raise self.Error(
                    f"unknown jumphost tag {jumphost_tag} in organization {options.organization}, check settings.json"
                    )
            jumphost_data = {
                "hostname": jumphost_tag,
                "username": getpass.getuser(),
                "port": 22,
                "first_uid": Constants.JUMPHOST_FIRST_UID,
                "first_keepalive": Constants.JUMPHOST_FIRST_KEEPALIVE
                }
            jumphost_data |= self.settings["jumphosts"][jumphost_tag]
            try:
                jumphost_attr = Settings.JumphostAttributes(**jumphost_data)
            except Exception as e:
                raise self.Error(
                    f"can't convert jumphost data: org {options.organization:s}, jumphost {jumphost_tag}, data: {jumphost_data}, error: {e}"
                    )
            jumphost = Jumphost(jumphost_attr, options, self.settings)
            logger.debug("jumphost[%d]: %s", len(jumphosts), jumphost)
            jumphosts.append(jumphost)

        self.jumphosts = jumphosts
        return options

    #################
    # Test jumposts #
    #################
    def check_jumphosts(self) -> bool:
        logger = self.logger

        logger.debug("check_jumphosts")
        result = True
        for jumphost in self.jumphosts:
            if not jumphost.isreachable():
                logger.error("can't reach jumphost %s", jumphost.hostname)
                result = False
            else:
                logger.info("jumphost %s: ok", jumphost.hostname)

        logger.debug("check_jumphosts -> %s", result)
        return result

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

    #############################################
    # Create the gateway group on each jumphost #
    #############################################
    def create_gateway_groups_on_jumphosts(self) -> bool:
        result = True
        logger = self.logger
        organization = self.organization
        gateway_group = organization.gateway_group
        for jumphost in self.jumphosts:
            logger.info("%s: confirm gateway_group %s", jumphost.hostname, gateway_group)
            if not jumphost.create_gateway_group(gateway_group):
                result = False
                logger.debug("failed to create group %s for organization %s on jumphost %s",
                             gateway_group, organization.id, jumphost.hostname
                             )
        return result

    #############################################
    # Create the gateway users on each jumphost #
    #############################################
    def create_gateway_users_on_jumphosts(self) -> bool:
        result = True
        logger = self.logger
        organization = self.organization
        gateway_group = organization.gateway_group

        #
        # we don't want to handle multiple user ids on multi jumphosts: no way to test.
        # so the below code
        for conduit in self.conduits:
            for jumphost in self.jumphosts:
                username = conduit.hostname
                userid = conduit.get_jumphost_userid(jumphost)
                logger.info("%s: create gateway user %s group %s%s",
                            jumphost.hostname, username, gateway_group,
                            f" with user id {userid}" if userid != None else ""
                            )
                current_uid = jumphost.create_jumphost_user(desired_uid=userid, gateway_id=username, gateway_name=username, gateway_groupname=gateway_group)
                if current_uid == None:
                    result = False
                    logger.debug("failed to create user %s (uid %s) for gateway %s on jumphost %s",
                                 username,
                                 "auto" if userid == None else str(userid),
                                 conduit.mac, jumphost.hostname
                                 )
                else:
                    conduit.set_jumphost_userid(jumphost, userid=current_uid)

        return result

    #################################
    # Run the app and return status #
    #################################
    def run(self) -> int:
        options = self.args
        logger = self.logger

        if not self.check_jumphosts():
            logger.error("not all jumphosts available")
            return 1

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

        # create the jumphost gateway groups
        if not self.create_gateway_groups_on_jumphosts():
            logger.error("create_gateway_groups_on_jumphosts() failed")
            return 1

        # create users for each of the gateways in each of the jumphots
        if not self.create_gateway_users_on_jumphosts():
            logger.error("create_gateway_users_on_jumphosts() failed")
            return 1

        logger.info("all done")
        return 0
