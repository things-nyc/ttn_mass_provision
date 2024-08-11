##############################################################################
#
# Name: conduit_ssh.py
#
# Function:
#       Toplevel ConduitSsh() class, provides APIs for ssh connection to
#       a controlled Conduit.
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

import warnings
with warnings.catch_warnings():
   warnings.filterwarnings("ignore", message='.*cryptography')
   import fabric

from .constants import Constants

##############################################################################
#
# The Conduit SSH API
#
##############################################################################

class ConduitSsh():
    def __init__(self, options: Any, host: Union[ipaddress.IPv4Address, str]):
        self.options = options
        self.connection = fabric.Connection(
                            host=str(host),
                            user=options.username,
                            connect_kwargs={
                                "password": options.password,
                                "timeout": 3
                                }
                            )

        self.logger = logging.getLogger(__name__)
        logger = self.logger

        # set the log level
        if options.debug:
            logger.setLevel('DEBUG')
        elif options.verbose:
            logger.setLevel('INFO')
        else:
            logger.setLevel('WARNING')

        pass

    class Error(Exception):
        """ this is the Exception thrown by class ConduitSsh """
        pass

    # return TRUE if we can reach via SSH
    def ping(self, /, timeout: Union[int, None]=None) -> bool:
        self.logger.info("ping ssh")
        connection = self.connection

        if timeout != None:
            connection.connect_timeout = timeout

        try:
            _ = connection.run("echo ping", hide=True, timeout=5)
            return True
        except Exception as error:
            return False

    def sudo(self, command: str, /, **sudo_kwargs) -> bool:
        self.logger.debug("sudo")
        connection = self.connection
        options = self.options

        try:
            result = connection.sudo(
                    command,
                    password=options.password,
                    dry=options.noop,
                    **sudo_kwargs
                    )
            self.logger.debug("sudo results: %s", result)
            return True
        except Exception as error:
            self.logger.error("sudo error", exc_info=error, stack_info=True)
            return False

    def do(self, command: str, /, **run_kwargs) -> fabric.Result | None:
        self.logger.debug("do")
        connection = self.connection
        options = self.options

        try:
            result = connection.run(command, **run_kwargs)
            self.logger.debug("%s: result: %s", command, result)
            return result
        except Exception as error:
            self.logger.error("do error", exc_info=error, stack_info=True)
            return None
