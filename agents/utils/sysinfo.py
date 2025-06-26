import datetime
import os
import socket

import psutil

from .logtools import maybe_log_message


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


def get_ram_usage(logger):
    """
    Get the current RAM usage percentage.
    """
    try:
        mem = psutil.virtual_memory()
        return mem.percent
    except psutil.Error as e:
        maybe_log_message(
            'Error getting RAM usage: %s' % str(e),
            logger=logger
        )
        return -1.0


def get_cpu_usage(logger, interval=60):
    """
    Get the average CPU usage percentage over the last minute.
    """
    try:
        return psutil.cpu_percent(interval=interval)
    except (psutil.Error, ValueError) as e:
        maybe_log_message(
            'Error getting CPU usage: %s' % str(e),
            logger=logger
        )
        return -1.0


def get_load_average(logger):
    """
    Get the system load average over the last 1 minute.
    """
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError) as e:
        maybe_log_message(
            'Error getting load average: %s' % str(e),
            logger=logger
        )
        return -1.0


def get_disk_usage(logger):
    """
    Get the current disk usage percentage for the root filesystem.
    """
    try:
        usage = psutil.disk_usage('/')
        return usage.percent
    except psutil.Error as e:
        maybe_log_message(
            'Error getting disk usage: %s' % str(e),
            logger=logger
        )
        return -1.0


def generate_report(logger):
    """
    Generate a report containing server resource usage.
    """
    return {
        'cpu': get_cpu_usage(logger),
        'ram': get_ram_usage(logger),
        'disk': get_disk_usage(logger),
        'load_avg': get_load_average(logger),
        'timestamp': datetime.datetime.now().isoformat(),
    }
