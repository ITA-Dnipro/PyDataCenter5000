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
    try:
        net_if_dict = psutil.net_if_addrs()
    except psutil.Error:
        return

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


def is_port_open(
    port,
    ip,
    protocol,
    logger,
    timeout=2,
    payload=None,
    packet_size=0
):
    """
    Check if the port is open.

    Returns:
        bool: Port status.

    Raises:
        ValueError: If the port not assigned a valid number.
    """
    if port == -1:
        raise ValueError(
            'Port not set: server agent must assign a valid port number'
        )

    if not ip:
        return False

    if not protocol:
        raise ValueError(
            'Protocol not set: server agent must set a valid transfer '
            'protocol (TCP or UDP)'
        )

    s = socket.socket(
        socket.AF_INET,
        (
            socket.SOCK_STREAM if protocol == 'tcp'
            else socket.SOCK_DGRAM
        ),
    )
    s.settimeout(timeout)

    try:
        if protocol == 'tcp':
            s.connect((ip, port))
        else:
            s.sendto(payload or b'', (ip, port))

        if packet_size > 0:
            data, _ = s.recvfrom(packet_size)
            if len(data) != packet_size:
                maybe_log_message(
                    (
                        'UDP response size mismatch: expected '
                        '%d bytes, got %d bytes' % (packet_size, len(data))
                    ),
                    logger=logger,
                )

                return False

        return True
    except (socket.error, socket.timeout) as e:
        maybe_log_message(
            'Port check failed due to error: %s' % str(e),
            logger=logger,
        )

        return False
    finally:
        s.close()
