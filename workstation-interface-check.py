#!/usr/bin/python3

# Title: workstaion-interface-check.py
# Author: Troy W. Caro <twc17@pitt.edu>
# Version: 1.1.0
# Last Modified: <10/18/2017>
#
# Purpose: To check all interfaces that are in workstaion VLANs for correct configuration
#
# Dependencies:
#   python3
#   netmiko module
#
# Usage:
#  python3 workstation-interface-check.py [-h] SWITCH_LIST.txt 
#
# TODO: Full test and review

# External libraries
import os
import sys
import socket
import netmiko
import argparse
import datetime

# We will write all of our output to this file, just in case
LOG_FILE = "workstation-interface-check.log"

# Username and pass to connect to switch
USER = '****'
SECRET_STRING = '*******'

# List of items that we want in each port config
BASE_CONFIG = [
        'switchport access vlan',
        'switchport port-security maximum',
        'no logging event link-status',
        'source template',
        'spanning-tree portfast']

def write_log(entry):
    """Write an entry to the log file"""
    f = open(LOG_FILE, 'a')
    # Format the time 2013-09-18 11:16:32
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    f.write(now + " " + entry + '\n')
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
        result = result.split('\n')

        configs[i] = result
    
    return configs

def get_id_and_template(interface):
    """Get the VLAN ID and VoIP template name from an interface config

    Arguments:
        interface -- list of configurations for an interface

    Returns:
        vlan -- VLAN ID
        template -- VoIP template name
    """
    vlan = 'x'
    template = 'x'

    for item in interface:
        if item.find(BASE_CONFIG[0]) is not -1:
            vlan = item.split()[-1]

        if item.find(BASE_CONFIG[3]) is not -1:
            template = item.split()[-1]

    return vlan, template

def check_interface_config(interface):
    """Compare the given interfaces config to the BASE_CONFIG

    Arguments:
        interface -- list of configurations for an interface

    Returns:
        True if the interface is configured correctly, False otherwise
    """
    for config_item in BASE_CONFIG:
        # If any of the things from BASE_CONFIG are missing, fail compliance
        if any(config_item in item for item in interface) == False:
            return False

    # If 'speed' or 'duplex' is in the interface config, fail compliance
    if any('speed' in item for item in interface) or any('duplex' in item for item in interface):
        return False

    return True

def main():
    """Main program logic"""
    parser = argparse.ArgumentParser(description='Make sure workstation interfaces are configured correctly')
    parser.add_argument('input_switch_list', metavar='SWITCH_LIST', help='List of switches to check')
    args = parser.parse_args()

    switch_list = []

    # Open the file containing the switches and add them to our switch_list
    f = open(args.input_switch_list, 'r')
    for switch in f:
        switch_list.append(switch.strip())
    f.close()

    switch_interface_results = open("workstation-interface-compliance.csv", 'w')

    # Loop through each switch in the list
    for switch in switch_list:
        write_log("Current switch: " + switch)

        # Make sure that the switch hostname resolves
        if check_host(switch):
            # Try to build the ssh object, connect to it, and do the rest of the program
            try:
                # Build the ssh object
                ssh = netmiko.ConnectHandler(
                        device_type = 'cisco_ios',
                        ip = switch,
                        username = USER,
                        password = SECRET_STRING)
                
                # Connect to the switch
                ssh.enable()

                # Get a list of all interfaces in workstation VLANs
                interfaces = get_workstation_interfaces(ssh)

                # Running configs for interfaces
                configs = get_interface_configs(interfaces, ssh)

                # Go over each interface, and make sure that it's configured correctly
                for interface in configs.keys():
                    vlan, template = get_id_and_template(configs[interface])
                    if check_interface_config(configs[interface]):
                        # YES!
                        switch_interface_results.write(switch + "," + interface + "," + vlan + "," + template + ",Y" + "\n")
                    else:
                        # NO!
                        switch_interface_results.write(switch + "," + interface + "," + vlan + "," + template + ",N" + "\n")

                # We're done with this switch, disconnect
                ssh.disconnect()

            # Something went wrong connecting to the switch, log it
            except:
                write_log("ERROR: Unexpected exception with " + switch)

        # If the switch hostname doesn't resolve, write that to the log
        else:
            write_log("ERROR: Check hostname for " + switch)

# Run the program!
if __name__ == "__main__":
    main()
