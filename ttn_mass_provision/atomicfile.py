##############################################################################
#
# Name: atomicfile.py
#
# Function:
#       AtomicFile() class for writing files atomically.
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Based on atomicfile-pi by A. Santanov.
#
##############################################################################

#### imports ####
import errno
import os
import tempfile
import typing

class AtomicFile(object):
    def __init__(self, name, mode: str = "w", /, createmode: int | None =None, encoding=None):
        def _maketemp(name: str, mode: str, createmode : int | None = None, encoding=None):
            directory, filename = os.path.split(name)
            fd, tempname = tempfile.mkstemp(prefix=f".{filename}-", suffix=".tmp", dir=directory, text=text)
            print(f"{fd=} {tempname=}")
            try:
                file = os.fdopen(fd=fd, mode=mode, encoding=encoding)
            except:
                try:
                    os.close(fd)
                except:
                    pass
                try:
                    os.unlink(tempname)
                except:
                    pass
                raise

            try:
                st_mode = os.lstat(name).st_mode & 0o777
            except OSError as err:
                if err.errno != errno.ENOENT:
                    # file exists but we can't stat it.
                    raise
                # file doesn't exist so we need to supply a mode
                if createmode == None:
                    # lame API forces us to change umask to change it.
                    umask = os.umask(0)
                    os.umask(umask)

                    st_mode = ~umask
                else:
                    st_mode = createmode
                # turn off x bits -- this might be wrong, but..
                st_mode &= 0o666
            os.chmod(tempname, st_mode)

            return file, tempname

        # figure out whether it's a binary file
        if 'b' in mode:
            text = False
        elif 't' in mode:
            text = True
        else:
            text = True

        file, tempname = _maketemp(name, mode, createmode=createmode, encoding=encoding)

        self._fp = file
        self._tempname = tempname
        self._name = name

        # delegated methods
        self.fileno = file.fileno
        self.flush = self._fp.flush
        self.read = self._fp.read
        self.readable = self._fp.readable
        self.readline = self._fp.readline
        self.readlines = self._fp.readlines
        self.seek = self._fp.seek
        self.seekable = self._fp.seekable
        self.tell = self._fp.tell
        self.truncate = self._fp.truncate
        self.writable = self._fp.writable
        self.write = self._fp.write
        self.writelines = self._fp.writelines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, ex_tb):
        if exc_type:
            return
        self.close()

    def close(self):
        if not self._fp.closed:
            self._fp.close()
            os.replace(self._tempname, self._name)

    def discard(self):
        if not self._fp.closed:
            try:
                os.unlink(self._tempname)
            except OSError:
                pass
            self._fp.close()

    def __del__(self):
        if getattr(self, "_fp", None):  # means the constructor created a file
            self.discard()
