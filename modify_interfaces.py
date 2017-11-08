#!/usr/bin/python3
'''modify_interfaces.py
Usage:
    modify_interfaces.py <switch_name> <interface_config> <interface_list>
    modify_interfaces.py (-h | --help)
    modify_interfaces.py (-v | --version)

Positional Arguments:
    <switch_name>           Hostname of switch to connect to
    <interface_config>      File with list of configurations for an interface
    <interface_list>        List of interfaces to modify

Options:
    -h --help               Print this screen and exit
    -v --version            Print the version of modify_interfaces.py
'''

# Author
# Troy <twc17@pitt.edu>

# Last modified
# 11/04/2017

# TODO: Lookup docopt info, add a -p argument for pretent mode

# External libs
import os
import sys
import socket
import docopt
import netmiko
import datetime

# Log file in current dir: modify_interfaes_DATETIME.log
LOG_FILE = 'modify_interfaces_{}.log'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S'))

def write_log(entry):
    """Write an entry to the log file"""
    log = open(LOG_FILE, 'a')
    now = datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
    log.write('{} {}\n'.format(now, entry))
    log.close()

def check_host(host):
    """Check to make sure that a host resolves in DNS

    Arguments:
        host -- Hostname to query in DNS

    Returns:
        True if lookup is good, False otherwise
    """
    try:
        socket.gethostbyname(host)
        return True
    except:
        return False


