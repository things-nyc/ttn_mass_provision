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
from dataclasses import dataclass
import ipaddress
import logging
import pathlib
import shlex
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
        hostname_prefix = prefix
        self.hostname = hostname_prefix + self.mac
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
    def fetch_gateway_public_key(self, /, timeout: int | None = None) -> bool:
        c = self.ssh
        logger = self.logger

        result = c.do("cat /etc/ssh/ssh_host_rsa_key.pub", hide=True)
        logger.debug("cat: %s", repr(result))
        if result == None or not result.ok:
            return False

        gateway_public_key: str = result.stdout.splitlines()[0].strip()
        logger.info("gateway public host key for %s: %s", self.mac, gateway_public_key)
        self.public_key = gateway_public_key

        return True

    #################################
    # Get the MultiTech lora EUI-64 #
    #################################
    def fetch_lora_eui64(self, /, timeout: int | None = None) -> bool:
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

    ###################################################################
    # Get the reverse socket on a given jumphost -- we use the userid #
    ###################################################################
    def get_jumphost_reverse_socket(self, jumphost: Jumphost) -> int | None:
        return self.get_jumphost_userid(jumphost)

    ##############################################################################
    # Get the keepalive socket base on a given jumphost -- we base on the userid #
    ##############################################################################
    def get_jumphost_keepalive(self, jumphost: Jumphost) -> int | None:
        return (self.get_jumphost_userid(jumphost) - jumphost.first_uid) * 2 + jumphost.first_keepalive

    #####################################
    # Set up the tunnel to the jumphost #
    #####################################

    # set date using ntp
    def set_date_using_ntp(self) -> bool:
        logger = self.logger
        answer = self.ssh.sudo("ntpdate -ub pool.ntp.org")
        if answer == None:
            return False
        return answer.ok

    def mkdir(self, path: str | pathlib.Path, mode: int, user: str = "root", group: str = "root") -> bool:
        logger = self.logger
        safepath = shlex.quote(str(path))
        answer = self.ssh.sudo("mkdir -p -m %o %s" % (mode, safepath))
        if answer == None or not answer.ok:
            logger.error("%s: could not create %s with mode %o", self.mac, str(path), mode)
            return False
        answer = self.ssh.sudo("chmod %o %s" % (mode, safepath))
        if answer == None or not answer.ok:
            logger.error("%s: could not chmod %s to %o", self.mac, safepath)
            return False
        answer = self.ssh.sudo("chown %s.%s %s" % (shlex.quote(user), shlex.quote(group), safepath))
        if answer == None or not answer.ok:
            logger.error("%s: could not change owner of %s", self.mac, path)
            return False
        return True

    def simplecmd(self, command: str, logfail: bool = True, /, **kwargs) -> bool:
        logger = self.logger
        options = self.options
        if options.debug:
            kwargs['hide'] = False
            kwargs['echo'] = True

        answer = self.ssh.sudo(command, **kwargs)
        if answer == None or not answer.ok:
            logger.error("%s: failed: %s", self.mac, command)
            return False
        return True

    # the worker
    def setup_jumphost_tunnel(self, jumphost: Jumphost, authorized_keys: list[str]) -> bool:
        if not self.set_date_using_ntp():
            return False

        var_root = pathlib.Path("/var/config/home")
        if not self.mkdir(var_root, 0o755):
            return False
        var_root = var_root / "root"
        if not self.mkdir(var_root, 0o700):
            return False
        if not self.mkdir(var_root / ".ssh", 0x700):
            return False

        var_auth_keys = var_root / ".ssh/authorized_keys"
        root_home = pathlib.Path("/home/root")
        root_auth_keys = root_home / ".ssh/authorized_keys"
        if not self.simplecmd("test -f " + str(var_auth_keys), logfail=False):
            if self.simplecmd("test -f " + str(root_auth_keys), logfail=False):
                if not self.simplecmd("sh -c " + shlex.quote(
                    "cat " + str(root_auth_keys) + " >" + str(var_auth_keys)
                    )):
                    return False
            else:
                if not self.simplecmd("touch " + str(var_auth_keys)):
                    return False
            if not self.simplecmd("chmod 700 " + str(var_auth_keys)):
                return False

        # set contents of /var/config/... authorized_keys
        cmd = "sh -c " + shlex.quote("printf '%s\n' >>" + str(var_auth_keys) + " " + shlex.join(authorized_keys))
        if not self.simplecmd(cmd):
            return False
        if not self.simplecmd(f"sort -u -o {str(var_auth_keys)} {str(var_auth_keys)}"):
            return False

        # if no ~root/.ssh, link it
        # if ~root/.ssh and not a link, rm and link it
        # if ~root/.ssh and a link, simply relink it
        var_root_ssh = var_root / ".ssh"
        root_ssh = root_home / ".ssh"
        if not self.simplecmd("test -d " + str(root_ssh), logfail=False):
            if not self.simplecmd(f"ln -fs {str(var_root_ssh)} {root_home}"):
                return False
        elif not self.simplecmd(f"test -L {root_ssh}", logfail=False):
            # somewhat unpleasant and not atomic, but....
            if not self.simplecmd(f"mv {str(root_ssh)} {str(root_home / ".ssh_old")}"):
                return False
            if not self.simplecmd(f"ln -s {str(var_root_ssh)} {root_home}"):
                return False
        else:
            # atomic update: maybe no change
            if not self.simplecmd(f"ln -fs {str(var_root_ssh)} {root_home}"):
                return False

        # now the ssh_tunnel defaults
        ssh_tunnel_lines = [
            "DAEMON=/usr/bin/autossh",
            "LOCAL_PORT=22",
            f"REMOTE_HOST={jumphost.hostname}",
            f"REMOTE_USER={self.hostname}",
            f"REMOTE_PORT={self.get_jumphost_reverse_socket(jumphost)}",
            'SSH_KEY="/etc/ssh/ssh_host_rsa_key.pub"',
            "SSH_PORT=22",
            f'DAEMON_ARGS="-f -M {self.get_jumphost_keepalive(jumphost)} -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i /etc/ssh/ssh_host_rsa_key"',
            ]

        default_tunnel_config=pathlib.Path("/etc/default/ssh_tunnel")
        cmd = "sh -c " + shlex.quote("printf '%s\n' >>" + str(default_tunnel_config) + " " + shlex.join(ssh_tunnel_lines))
        if not self.simplecmd(cmd):
            return False

        if not self.simplecmd(f"chmod 755 {str(default_tunnel_config)}"):
            return False
        if not self.simplecmd(f"chown root.root {str(default_tunnel_config)}"):
            return False

        # copy the ssh tunnel file.
        default_tunnel_script=pathlib.Path("/etc/init.d/ssh_tunnel")
        cmd = "sh -c " + shlex.quote("printf '%s\n' >>" + str(default_tunnel_script) + " " + shlex.join(self.settings["ssh_tunnel_script"]))
        if not self.simplecmd(cmd):
            return False

        if not self.simplecmd(f"chmod 755 {str(default_tunnel_script)}"):
            return False
        if not self.simplecmd(f"chown root.root {str(default_tunnel_script)}"):
            return False

        if not self.simplecmd(f"{str(default_tunnel_script)} restart"):
            return False

        return True
