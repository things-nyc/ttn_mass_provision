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
import shlex
import typing

Any = typing.Any
Union = typing.Union

from . constants import Constants
from . settings import Settings
from . jumphost_ssh import JumphostSsh

##############################################################################
#
# The Jumphost object
#
##############################################################################

class Jumphost:
    def __init__(self, attr: Settings.JumphostAttributes, options: argparse.Namespace, settings: dict):
        self.attr: Settings.JumphostAttributes = attr
        self.hostname: str = attr.hostname
        self.fqdn: str = getfqdn(self.hostname)
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

        self.ssh = JumphostSsh(options, host=self.hostname, username=attr.username, port=attr.port)
        self.first_uid: int = Constants.JUMPHOST_FIRST_UID
        self.first_keepalive: int = Constants.JUMPHOST_FIRST_KEEPALIVE
        pass

    def __str__(self) -> str:
        return str({ "attr": self.attr, "hostname": self.hostname, "ssh": self.ssh})

    def isreachable(self) -> bool:
        return self.ssh.ping()

    # query jumphost getent entry
    def query_getent(self, dbname: str, entryname: str) -> str | None:
        logger = self.logger
        answer = self.ssh.do([ 'getent', dbname, entryname ])
        result: str | None = None
        if answer == None:
            logger.debug("getent %s failed completely", dbname)
            return None

        if answer.ok:
            stdout_lines = answer.stdout.splitlines()
            if len(stdout_lines) == 0:
                logger.debug("%s: %s: doesn't exist: empty response", dbname, entryname)
            elif len(stdout_lines[0].strip()) == 0:
                logger.debug("%s: %s: doesn't exist: length of first line is zero", dbname, entryname)
            else:
                result = stdout_lines[0].strip()
                logger.debug("%s: %s: exists, value %s", dbname, entryname, result)
        else:
            logger.debug("%s: %s: doesn't exist: getent exit status %d", dbname, entryname, answer.exited)

        return result

    # create gateway group
    def query_gateway_group(self, groupname: str) -> bool:
        return self.query_getent("group", groupname) != None

    # check and create gateway group: idempotent if group exists
    def create_gateway_group(self, groupname: str) -> bool:
        logger = self.logger
        if self.query_gateway_group(groupname):
            return True

        answer = self.ssh.sudo(f"groupadd {shlex.quote(groupname)}")
        if answer == None:
            return False

        if answer.ok:
            logger.info("created group %s", groupname)
            return True

        else:
            logger.error("groupadd failed: %s", answer.stderr.strip())
            return False

    #########################
    # Query a jumphost user #
    #########################
    def query_jumphost_user(self, gateway_id: str) -> int | None:
        logger = self.logger
        answer = self.query_getent("passwd", gateway_id)
        if answer == None:
            return None
        try:
            return int(answer.split(':')[2])
        except Exception as e:
            logger.error("couldn't parse result of getent passwd %s: %s", gateway_id, answer)
            return None

    ################################################################################
    # Create a jumphost user; equivalent of create-jumphost-user.sh in conduit-mfg #
    ################################################################################
    def create_jumphost_user(self, desired_uid: int | None, gateway_name: str, gateway_id: str, gateway_groupname: str, gateway_userid = None) -> int | None:
        logger = self.logger

        current_uid = self.query_jumphost_user(gateway_id)
        if current_uid != None:
            if desired_uid != None and current_uid != desired_uid:
                logger.error("%s: %s: uid conflict: current %d != desired %d", self.hostname, gateway_id, current_uid, desired_uid)
                return None
            else:
                logger.info("%s: %s: already exists with UID=%d", self.hostname, gateway_id, current_uid)
                return current_uid

        args = [
            'useradd',
            '--comment', gateway_name,
            '--password', '*',
            '--gid', gateway_groupname,
            '--no-user-group',
            '--create-home',
            '--key', f'UID_MIN={self.attr.first_uid}'
        ]

        if desired_uid != None:
            args += [ "-u", str(desired_uid) ]

        args += [ gateway_id ]

        answer = self.ssh.sudo(args)
        if answer == None:
            return None
        elif answer.ok:
            current_uid = self.query_jumphost_user(gateway_id)
            logger.info("%s: %s: created with uid=%s", self.hostname, gateway_id, str(current_uid))
            return current_uid
        else:
            logger.error("useradd failed: %s", answer.stderr.strip())
            return None

    # create the SSH linkage for gateway users. This is idempotent
    def add_gateway_user_ssh_authorization(self, keys: list[str], username: str, gateway_group: str) -> bool:
        logger = self.logger
        options = self.options

        logger.debug("user %s: keys: %s", username, keys)

        ssh_dir = shlex.quote("/home/" + username + "/.ssh")
        answer = self.ssh.sudo("test -d " + ssh_dir, user=None)

        if answer == None:
            logger.error("%s: sudo to create .ssh dir failed catastrophically", self.hostname)
            return False
        if not answer.ok:
            cmd = "mkdir -m 700 " + ssh_dir
        else:
            cmd = "chmod 700 " + ssh_dir

        answer = self.ssh.sudo(cmd)
        if answer == None:
            logger.error("%s: can't setup .ssh directory: %s", self.hostname, cmd)
        elif not answer.ok:
            logger.error("%s: %s failed: stderr: %s", self.hostname, cmd, answer.stderr)
            return False

        cmd = "chown " + shlex.quote(username) + "." + shlex.quote(gateway_group) + " " + ssh_dir
        answer = self.ssh.sudo(cmd, user=None)
        if answer == None:
            logger.error("%s: can't setup .ssh directory: %s", self.hostname, cmd)
        elif not answer.ok:
            logger.error("%s: %s failed: stderr: %s", self.hostname, cmd, answer.stderr)
            return False

        logger.info("%s: ~%s/.ssh exists with correct permissions", self.hostname, username)

        # now, put the authorized keys in the .ssh directory.
        commands = [
              "touch " + ssh_dir + "/authorized_keys",
              "chown " + shlex.quote(username) + "." + shlex.quote(gateway_group) + " " + ssh_dir + "/authorized_keys",
              "chmod 600 " + ssh_dir + "/authorized_keys",
              "sh -c " + shlex.quote("printf '%s\n' >>" + ssh_dir + "/authorized_keys " + shlex.join(keys)),
              "sort -u -o " + ssh_dir + "/authorized_keys " + ssh_dir + "/authorized_keys" ]

        for command in commands:
            answer = self.ssh.sudo(command, show=options.debug, echo=options.debug)

            if answer == None:
                logger.error("%s: failed catastrophically: %s", self.hostname, command)
                return False

            if not answer.ok:
                logger.error("%s: creating authorized_keys failed: %s\n--stdout--:\n%s\n--stderr--:\n%s",
                            self.hostname, command,
                            "" if answer.stdout == None else answer.stdout.strip(),
                            "" if answer.stderr == None else answer.stderr.strip())
                return False

        return True
