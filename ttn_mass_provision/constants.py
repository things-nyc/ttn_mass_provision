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

#### imports ####
from pathlib import Path
import re

#### The Constants class
class Constants:
        __slots__ = ()  # prevent changes

        DEFAULT_MLINUX_USERNAME = "mtadm"
        DEFAULT_IP_ADDRESS = "192.168.12.0/24"
        DEFAULT_ORG_NAME = "ttn-nyc"

        DEFAULT_INVENTORY_PATH = Path("..")
        DEFAULT_MULTITECH_CM_PATH = Path("../ttn-multitech-cm")

### end of file ###
