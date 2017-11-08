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
# 11/08/2017

# TODO: Lookup docopt info, add a -p argument for pretend mode
# TODO: try/catch opening files correctly

# External libs
import os
import sys
import socket
import docopt
import netmiko
import datetime

#################################################################################

# Command line arguments
arguments = docopt.docopt(__doc__, version='modify_interfaces.py version 1.0.0')

SWITCH_NAME = arguments['<switch_name>']

INTERFACE_CONFIG = []
# Open file containing interface configurations and add them to INTERFACE_CONFIG
with open(arguments['<interface_config>'], 'r') as f:
    INTERFACE_CONFIG.append(f.readline())

INTERFACE_LIST = []
# Open file of interfaces and add them to the INTERFACE_LIST
with open(arguments['<interface_list>'], 'r') as f:
    INTERFACE_LIST.append(f.readline().strip())

# Log file in current dir: modify_interfaes_SWITCH.log
LOG_FILE = 'modify_interfaces_{}.log'.format(SWITCH_NAME)

#################################################################################

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

def get_interface_config(interface, ssh):
    """Get the running config for a specific interface

    Arguments:
        interface -- the interface to get the config for
        ssh -- connection to the switch

    Returns:
        config -- list of configs on the interface
    """

    cmd = 'sh run int {}'.format(interface)

    result = ssh.find_prompt() + "\n"
    result += ssh.send_command_expect(cmd)
    config = result.split('\n')

    return config

#################################################################################

def main():
    pass

#################################################################################

# Run the program
if __name__ == "__main__":
    main()
