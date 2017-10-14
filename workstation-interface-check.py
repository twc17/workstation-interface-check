#!/usr/bin/python3

# Title: workstaion-interface-check.py
# Author: Troy W. Caro <twc17@pitt.edu>
# Version: 1.0.0
# Last Modified: <10/14/2017>
#
# Purpose: To check all interfaces that are in workstaion VLANs for correct configuration
#
# Dependencies:
#   python3
#   netmiko module
#
# Usage:
#  python3 workstation-interface-check.py SWITCH_LIST.txt 

# External libraries
import os
import sys
import socket
import netmiko

# We will write all of our output to this file, just in case
LOG_FILE = "workstation-interface-check.log"

# List of items that we want in each port config
BASE_CONFIG = [
        'description',
        'switchport access vlan',
        'switchport port-security maximum',
        'no logging event link status',
        'source template',
        'spanning-tree portfast']

def write_log(entry):
    """Write an entry to the log file"""
    f = open(LOG_FILE, 'a')
    f.write(entry + '\n')
    f.close()

def check_host(host):
    """Check to make sure that the host resolves in DNS

    Arguments:
        host -- hostname to check in DNS

    Returns:
        True if lookup is good, False otherwise
    """
    try:
        socket.gethostbyname(host)
        return True
    except:
        return False

def get_workstation_interfaces(ssh):
    """Get all of the interfaces that are in workstaion VLANs

    Arguments:
        ssh -- connection to the switch

    Returns:
        interfaces -- list of interaces in workstaion VLANs
    """
    # Command that we will run on the switch to get workstation vlans
    cmd = "sh vl br | i (W-I|WKSTN|WKST)"
    result = ssh.find_prompt() + "\n"
    # Send command to switch and get the output
    result += ssh.send_command_expect(cmd)

    # Split the output by white spaces
    output = result.split()

    interfaces = []

    for i in output:
        # All of the interfaces start with 'Gi', so that's what we're looking for
        if i.find("Gi") is not -1:
            # Remove the comma from the port
            interfaces.append(i.replace(',', ''))

    return interfaces

def get_interface_configs(interfaces, ssh):
    """Get the running config for a list of interfaces

    Arguments:
        interfaces -- list of interfaces to get configs
        ssh -- connection to switch

    Returns:
        configs -- dictionary of interfaces configs (configs[Gi1/0/1] = ['description xxx', 'other configs'])
    """
    # Dictionary that we will use for interface configs
    configs = {}
    
    # Command that will be used to get running config of interface
    # Note the trailing space... we need this
    cmd = "sh run int "

    for i in interfaces:
        result = ssh.find_prompt() + "\n"
        result += ssh.send_command_expect(cmd + i)
        result = result.split()

        configs[i] = result
    
    return configs

def check_interface_config(interface):
    """Compare the given interfaces config to the BASE_CONFIG

    Arguments:
        interface -- list of configurations for an interface

    Returns:
        True if the interface is configured correctly, False otherwise
    """
    pass

def main():
    """Main program logic"""
    pass

# Run the program!
if __name__ == "__main__":
    main()
