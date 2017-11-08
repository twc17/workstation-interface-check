#!/usr/bin/python3
'''modify_interfaces.py
Usage:
    modify_interfaces.py <switch_name> <interface_config> <interface_list> [-p | --pretend]
    modify_interfaces.py (-h | --help)
    modify_interfaces.py (-v | --version)

Positional Arguments:
    <switch_name>           Hostname of switch to connect to
    <interface_config>      File with list of configurations for an interface
    <interface_list>        List of interfaces to modify

Options:
    -p --pretend            Run program in PRETEND mode. Will not make changes to switch
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

PRETEND = arguments['--pretend']

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

# Credentials to log into switches
with open('credentials.txt', 'r') as f:
    USER = f.readline().strip()
    SECRET = f.readline().strip()

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

def persistent_interface_data(interface_config):
    """Get the data from the interface config that should remain the same
    through this process. Description, VLAN, Max MAC (if any)

    Arguments:
        interface_config -- list of configs currently on an interface

    Returns:
        description --  interface description
        vlan -- interface access vlan
        maximum -- max mac allowance
    """
    description = ''
    vlan = 1
    maximum = 1

    for item in interface_config:
        if item.find('description') is not -1:
            description = item
        if item.find('vlan') is not -1:
            vlan = item.split()[-1]
        if item.find('maximum') is not -1:
            maximum = item.split()[-1]

    return description, vlan, maximum

def configure_interface(config_list, interface, description, vlan, maximum, ssh):
    """Default the interface, the reconfigure it with the given config_list

    Arguments:
        config_list -- list of new interface configurations
        interface -- interface to configure
        description -- description to apply to the interface
        vlan -- access vlan that the interface should be in
        maximum -- max mac allowance interface should have
        ssh -- connection to the switch

    Returns:
        result -- commands sent to the switch
    """
    # Add interface command to top of the list
    config_list.insert(0,'interface {}'.format(interface))

    # If there was a description set on the interface, keep in
    if len(description) > 1:
        config_list.append('{}'.format(description))
    
    # Keep VLAN from previous config
    config_list.append('switchport access vlan {}'.format(vlan))

    # Keep maximum MAC allowance (+1 should have alread been added to it in main() )
    config_list.append('switchport port-security maximum {}'.format(maximum))

    return ssh.send_config_set(config_list)

#################################################################################

def main():
    if PRETEND:
        write_log('Starting script for {} in PRETEND mode'.format(SWITCH_NAME))
        write_log('No changes will be made to the switch')
    else:
        write_log('Starting script for {} in LIVE mode'.format(SWITCH_NAME))
        write_log('Changes will be made to the switch')

    if check_host(SWITCH_NAME):
        write_log('nslookup passed for {}'.format(SWITCH_NAME))

        try:
            ssh = netmiko.ConnectHandler(
                    device_type = 'cisco_ios',
                    ip = SWITCH_NAME,
                    username = USER,
                    password = SECRET)

            # Connect to the switch
            write_log('Establishing connection to {}'.format(SWITCH_NAME))
            ssh.enable()

            # Go over each interface in the list
            for interface in INTERFACE_LIST:

                # Get the current interfaces running config
                write_log('Getting running config for interface {}'.format(interface))
                running_config = get_interface_config(interface, ssh)

                # From the current config, grab the description, vlan, and maximum MAC
                description, vlan, maximum = persistent_interface_data(running_config)
                write_log('Saving description: {}, vlan: {}, max: {}, from interface {}'.format(description, vlan, maximum, interface))

                # Configure the interface with the new config, saving the old description, vlan,
                # and adding 1 to the max
                if PRETEND:
                    write_log('The following commands would have been sent to the switch')
                    write_log('interface {}'.format(interface))
                    write_log(description)
                    for item in INTERFACE_CONFIG:
                        write_log(item)
                    write_log('switchport access vlan {}'.format(vlan))
                    write_log('switchport port-security maximum {}'.format(maximum))
                else:
                    # Commenting out for testing
                    # write_log('Programming interface {} with new config'.format(interface))
                    # result = configure_interface(INTERFACE_CONFIG, interface, description, vlan, (maximum + 1), ssh)
                    print("NOT PRETENDING")

            # Write config to memory
            # Commenting out for testing
            #write_log('Writing switch config to memory \n')
            #ssh.send_command_expect('write memory')

            # Disconnect
            ssh.disconnect()

        except:
            write_log('ERROR: Unexpected exception with {}'.format(SWITCH_NAME))

    else:
        write_log('ERROR: nslookup failed for {}'.format(SWITCH_NAME))
        sys.exit(0)

#################################################################################

# Run the program
if __name__ == "__main__":
    main()
