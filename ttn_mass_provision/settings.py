##############################################################################
#
# Name: settings.py
#
# Function:
#       Toplevel Settings() class, models the data in the settings.json file.
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

#### imports ####
from dataclasses import dataclass
import jsons
import pathlib

@dataclass
class Settings(jsons.JsonSerializable):
    @dataclass
    class ProductAttributes(jsons.JsonSerializable):
        device_type: str
        device_class: str
        has_cellular: bool = False

    @dataclass
    class Organization(jsons.JsonSerializable):
        description: str
        prefix: str
        org_dir: pathlib.Path
        jumphosts: list[str]

    @dataclass
    class Jumphost(jsons.JsonSerializable):
        description: str                # the description of the jump host
        username: str                   # the username used when logging in
        hostname: str | None = None     # the host name of the jump host
        hostport: int = 22              # the port to use for connecting
