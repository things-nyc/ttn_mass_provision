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

##############################################################################
#
# The Conduit SSH API
#
##############################################################################

class Conduit():
    def __init__(self, ip: Union[ipaddress.IPv4Address, str], mac: str, options):
        self.ip = ipaddress.IPv4Address(ip)
        self.mac = mac
        self.logger = logging.getLogger(__name__)
        logger = self.logger
        self.options = options
        self.ssh = ConduitSsh(options, host=ip)

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
    def check_ssh_enabled(self, /, timemout: Union[int, None] = None) -> bool:
        c = self.ssh
        logger = self.logger

        if c.ping():
            logger.info("ssh to %s is working", self.ip)
            return True
        else:
            logger.info("ssh to %s is not working", self.ip)
            return False
