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
    if parent is not None:
        port = parent.port
        ip = parent.ip
        protocol = parent.protocol
    else:
        if (
            'port' not in kwargs
            or 'ip' not in kwargs
            or 'protocol' not in kwargs
        ):
            raise TypeError(
                'Must provide valid port number, IP address and '
                'data transfer protocol for port check'
            )

        if not isinstance(port, int):
            raise TypeError(
                'Port number must be an integer, not %s' % type(port)
            )

    if not is_valid_ip(ip):
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
