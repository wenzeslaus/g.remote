MODULE_TOPDIR = ../..

PGM = g.remote

ETCFILES = friendlyssh pexpectssh simplessh localsession grasssession

include $(MODULE_TOPDIR)/include/Make/Script.make
include $(MODULE_TOPDIR)/include/Make/Python.make

default: script
