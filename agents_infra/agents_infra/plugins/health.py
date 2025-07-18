import socket
import warnings

from ..agents.base import ServerAgent
from ..plugins.plugin import plugin
from ..utils.helpers import is_valid_ip


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
