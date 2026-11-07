##############################################################################
#
# Module: Makefile
#
# Purpose:
#	Procedures for this directory
#
# Copyright notice and license:
#   See LICENSE.md in this directory.
#
# Author:
#   Terry Moore   July 2024
#
##############################################################################

# the uv command
UV=uv

#
# Default target: print help.
#
help:
	@printf "%s\n" \
		"This Makefile contains the following targets" \
		"" \
		"* make help -- prints this message" \
		"* make build -- builds the app (in dist)" \
		"* make venv -- sets up .venv for development (uv sync)" \
		"* make lock -- updates uv.lock to the latest allowed versions" \
		"* make clean -- get rid of build artifacts" \
		"* make distclean -- like clean, but also removes distribution directory"

#
# build release files in dist.
#
build:
	$(UV) build
	@printf "%s\n" "distribution files are in the dist directory:" && ls dist

#
# targets for local development:
#    venv creates or updates .venv from uv.lock, and installs the app.
#    lock updates uv.lock.
#
venv:
	$(UV) sync
	@printf "%s\n" \
		"Virtual environment is in .venv. To run the app, say:" \
		"    uv run ttn_mass_provision --help" \
		""

lock:
	$(UV) lock --upgrade

#
# maintenance targets
#
clean:
	rm -rf .buildenv .venv build *.egg-info */__pycache__

distclean:	clean
	rm -rf dist

.PHONY: help build venv lock clean distclean

#### end of file ####
