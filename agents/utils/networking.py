import socket

import psutil


def get_ip_from_interface(interface):
    """
    Attempt getting server's primary IP address associated with a given
    interface name.

    Parameters:
        interface (str): Interface name.

    Returns:
        str: On success, IP address is returned.
    """
    net_if_dict = psutil.net_if_addrs()
    if interface not in net_if_dict:
        return

    addresses = net_if_dict[interface]

    for address in addresses:
        if address.address.startswith('127.'):
            continue

        if address.family == socket.AF_INET:
            return address.address


def get_linux_uptime():
    """Get uptime on Linux OS."""
    with open('/proc/uptime', 'r') as f:
        return float(f.readline().split()[0])
