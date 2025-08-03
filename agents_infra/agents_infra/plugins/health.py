import socket
import time
import warnings
from collections import Sequence

from ..agents.base import ServerAgent
from ..exceptions import BadProcessReturnCode
from ..plugins.plugin import plugin
from ..utils.helpers import execute_shell_command, is_valid_ip
from ..utils.retry import jitter


@plugin(ServerAgent, category='health', built_in=True)
def check_port(
    parent,
    timeout=2,
    payload=None,
    packet_size=0,
    *args,
    **kwargs
):
    port = parent.config.port if parent else kwargs.get('port')
    ip = parent.ip if parent else kwargs.get('ip')
    protocol = parent.protocol if parent else kwargs.get('protocol')

    if not isinstance(port, int):
        raise TypeError(
            'Port number must be a positive integer, got %s' % type(port)
        )
    if port < 0:
        raise ValueError('Port must be a positive number, got %d' % port)

    if protocol not in ('tcp', 'udp'):
        raise ValueError('Unknown transfer protocol: %s' % str(protocol))

    if not isinstance(ip, str) or not is_valid_ip(ip):
        warnings.warn(
            '%s is not a valid IP address. Falling back to local IP address.'
            % str(ip)
        )
        ip = '127.0.0.1'

    s = socket.socket(
        socket.AF_INET,
        (socket.SOCK_STREAM if protocol == 'tcp' else socket.SOCK_DGRAM),
    )
    s.settimeout(timeout)

    port_status = False

    try:
        if protocol == 'tcp':
            s.connect((ip, port))

            port_status = True
        else:
            s.sendto(payload or b'', (ip, port))

            if packet_size > 0:
                data, _ = s.recvfrom(packet_size)

                if len(data) != packet_size:
                    warnings.warn(
                        (
                            'UDP response size mismatch: expected '
                            '%d bytes, got %d bytes' % (packet_size, len(data))
                        )
                    )
                else:
                    port_status = True
            else:
                port_status = True
    finally:
        s.close()

    return {'port_open': port_status}


def _validate_processes(procs):
    if isinstance(procs, basestring):
        procs = [procs]

    if not isinstance(procs, Sequence):
        raise TypeError(
            'Processes must be provided as a string for a single process '
            'or a sequence of strings for multiple processes'
        )

    return procs


@plugin(ServerAgent, category='health', built_in=True)
def check_processes(parent, procs):
    """
    Check whether given process(es) are active.

    Parameters:
        parent (Any): Plugin's parent object.
        procs (str | Sequence): Process name as a string in the case of
            single process or a sequence of process names in the case of
            multiple processes.

    Returns:
        dict: Process statuses including whether they're active and the
            return codes of systemctl operations.
    """
    procs = _validate_processes(procs)

    proc_check_status = {'processes': {}}

    try:
        for proc in procs:
            execute_shell_command(['systemctl', 'is-active', proc])

            proc_check_status['processes'][proc] = {
                'active': True, 'returncode': 0
            }
    except BadProcessReturnCode as e:
        warnings.warn(
            'Process check for %s failed due to error: %s'
            % (str(proc), str(e))
        )

        proc_check_status['processes'][proc] = {
            'active': False, 'returncode': e.returncode
        }

    return proc_check_status


@plugin(ServerAgent, category='health', built_in=True)
def restart_processes(parent, procs, max_retries=3, min_delay=2, max_delay=5):
    """
    Attempt restarting given process(es).

    Parameters:
        parent (Any): Plugin's parent object.
        procs (str | Sequence): Process name as a string in the case of
            single process or a sequence of process names in the case of
            multiple processes.
        max_retries (int, optional): Maximum number of retries on
            failure. Default is 3.
        min_delay (int, optional): Minimum delay between retries
            (in seconds). Default is 2.
        max_delay (int, optional): Maximum delay between retries
            (in seconds). Default is 5.

    Returns:
        dict: Process statuses including whether they have been succesfully
            restarted and the return codes of systemctl operations.
    """
    procs = _validate_processes(procs)

    proc_restart_status = {'processes': {}}

    for proc in procs:
        backoff = jitter(min_delay, max_delay)

        for retry in range(1, max_retries + 1):
            try:
                execute_shell_command(['systemctl', 'restart', proc])

                proc_restart_status['processes'][proc] = {
                    'restarted': True, 'returncode': 0
                }
            except BadProcessReturnCode as e:
                if retry != max_retries:
                    delay = next(backoff)
                    time.sleep(delay)
                else:
                    warnings.warn(
                        'Process restart for %s failed due to error: %s'
                        % (str(proc), str(e))
                    )

                    proc_restart_status['processes'][proc] = {
                        'restarted': False, 'returncode': e.returncode
                    }

    return proc_restart_status
