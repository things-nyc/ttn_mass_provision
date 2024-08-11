##############################################################################
#
# Name: conduit.py
#
# Function:
#       Toplevel Conduit() class, models a Conduit being provisioned.
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

#### imports ####
import ipaddress
import logging
import typing

Any = typing.Any
Union = typing.Union


from .constants import Constants
from .conduit_ssh import ConduitSsh
from .jumphost import Jumphost
from .settings import Settings

##############################################################################
#
# The Conduit SSH API
#
##############################################################################

class Conduit():
    def __init__(self, ip: Union[ipaddress.IPv4Address, str], mac: str, options, settings: dict):
        self.ip = ipaddress.IPv4Address(ip)
        self.mac = mac
        self.logger = logging.getLogger(__name__)
        logger = self.logger
        self.options = options
        self.ssh = ConduitSsh(options, host=ip)
        self.settings: dict = settings

        # these are populated later
        self.product_id : str | None = None
        self.product_attributes : Settings.ProductAttributes | None = None
        self.hostname : str | None = None
        self.friendly_name : str | None = None
        self.public_key : str | None = None
        self.lora_eui64 : str | None = None
        self.jumphost_userid : int | None = None

        # set the log level
        if options.debug:
            logger.setLevel('DEBUG')
        elif options.verbose:
            logger.setLevel('INFO')
        else:
            logger.setLevel('WARNING')

        pass

    def __str__(self):
        return self.mac

    class Error(Exception):
        """ this is the Exception thrown by class Conduit """
        pass

    ################################
    # Check whether SSH is enabled #
    ################################
    def check_ssh_enabled(self, /, timeout: Union[int, None] = None) -> bool:
        c = self.ssh
        logger = self.logger

        if c.ping(timeout=timeout):
            logger.info("ssh to %s is working", self.ip)
            return True
        else:
            logger.info("ssh to %s is not working", self.ip)
            return False

    ##################################
    # Get the MultiTech Conduit type #
    ##################################
    def get_product_id(self, /, timeout: int | None = None) -> bool:
        c = self.ssh
        logger = self.logger

        result = c.do("mts-io-sysfs show product-id", hide=True)
        logger.debug("mts-io-sysfs: %s", repr(result))
        if result == None or not result.ok:
            return False

        product_id: str = result.stdout.splitlines()[0]
        logger.info("product_id for %s: %s", self.mac, product_id)
        self.product_id = product_id

        return True

    ###################################################
    # Set the product attributes given the product ID #
    ###################################################
    def set_product_attributes(self) -> bool:
        if not self.product_id in self.settings["product_id_map"]:
            raise self.Error("%s: unknown product type: %s", self.mac, self.product_id)

        try:
            self.product_attributes = Settings.ProductAttributes(**self.settings["product_id_map"][self.product_id])
        except Exception as e:
            raise self.Error("can't convert product_attributes for product_id %s: check settings.json: %s",
                            self.product_id,
                            e)
        return True

    ##########################################
    # Generate the hostname for this Conduit #
    ##########################################
    def generate_hostname(self, prefix: str) -> bool:
        hostname_prefix = prefix + self.mac.replace('-', '')
        self.hostname = hostname_prefix
        self.logger.debug("%s: hostname set to %s", self.mac, self.hostname)
        return True

    #####################################################################
    # Generate the "friendly" name (short description) for this Conduit #
    #####################################################################
    def generate_friendly_name(self, org: Settings.Organization) -> bool:
        description: str = "Multitech {product_id} {mac}".format(product_id=self.product_id, mac=self.mac)
        self.friendly_name = description
        self.logger.debug("%s: friendly_name set to %s", self.mac, self.friendly_name)
        return True

    ####################################
    # Get the gatway's public host key #
    ####################################
    def get_gateway_public_key(self, /, timeout: int | None = None) -> bool:
        c = self.ssh
        logger = self.logger

        result = c.do("cat /etc/ssh/ssh_host_rsa_key.pub", hide=True)
        logger.debug("cat: %s", repr(result))
        if result == None or not result.ok:
            return False

        gateway_public_key: str = result.stdout.splitlines()[0]
        logger.info("gateway public host key for %s: %s", self.mac, gateway_public_key)
        self.public_key = gateway_public_key

        return True

    #################################
    # Get the MultiTech lora EUI-64 #
    #################################
    def get_lora_eui64(self, /, timeout: int | None = None) -> bool:
        c = self.ssh
        logger = self.logger

        result = c.do("mts-io-sysfs show lora/eui", hide=True)
        logger.debug("mts-io-sysfs show lora/eui: %s", repr(result))
        if result == None or not result.ok:
            return False

        lora_eui64: str = result.stdout.splitlines()[0].lower()
        logger.info("lora_eui64 for %s: %s", self.mac, lora_eui64)
        self.lora_eui64 = lora_eui64

        return True

    #######################################
    # Get the user ID on a given jumphost #
    #######################################
    def get_jumphost_userid(self, jumphost: Jumphost) -> int | None:
        # we don't actually support diffent values on different jumphosts
        return self.jumphost_userid

    #################################################
    # Get the gateway's user ID on a given jumphost #
    #################################################
    def set_jumphost_userid(self, jumphost: Jumphost, userid: int) -> bool:
        if self.jumphost_userid == None:
            self.jumphost_userid = userid
        elif userid != self.jumphost_userid:
            raise self.Error("%s: %s: can't change jumphost_userid from %d to %d" % (self.mac, jumphost.hostname, self.jumphost_userid, userid))
        return True
