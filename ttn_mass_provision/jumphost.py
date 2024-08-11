##############################################################################
#
# Name: constants.py
#
# Function:
#       Class for the immutable constants for this app
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

# imports
import argparse
import ipaddress
import logging
from socket import getfqdn
import typing

Any = typing.Any
Union = typing.Union

from . settings import Settings
from . jumphost_ssh import JumphostSsh

##############################################################################
#
# The Jumphost object
#
##############################################################################

class Jumphost:
    def __init__(self, hostname: str, options: argparse.Namespace, settings: dict):
        self.hostname: str = getfqdn(hostname)
        self.options = options
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        logger = self.logger

        # set the log level
        if options.debug:
            logger.setLevel('DEBUG')
        elif options.verbose:
            logger.setLevel('INFO')
        else:
            logger.setLevel('WARNING')

        self.ssh = JumphostSsh(options, host=self.hostname)

        pass
