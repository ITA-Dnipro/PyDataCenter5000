from __future__ import print_function  # compatibility with hooks
import datetime
import json
import socket
import sys
# argparse isn't available in Python2.6,
# used optparse for CLI-arguments instead
from optparse import OptionParser

import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):
    """
    SMTPAgent performs health checks for an SMTP server:
    - verifies if the port is open
    - checks whether specified processes are running
    - attempts to receive the SMTP banner
    Compatible with Python 2.6.
    """
    def __init__(self,
                 server_name='smtp',
                 port=25,
                 processes=None,
                 interface=None,
                 controller_url=None):
        ServerAgent.__init__(
            self,
            server_name=server_name,
            port=port,
            processes=processes or ['postfix', 'exim', 'sendmail', 'master'],
            interface=interface,
            controller_url=controller_url,
        )

    def check_banner(self, host='127.0.0.1'):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(8)
            sock.connect(
                (host, self.port)
            )
            try:
                banner = sock.recv(1024)
            except socket.timeout:
                banner = ''
            sock.close()

            return {
                'status': 'ok' if banner else 'no banner',
                'banner': banner.strip() if banner else None
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def check_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(1)
            s.connect(('localhost', self.port))
            s.close()
            return True
        except Exception:
            return False

    def check_processes(self):
        try:
            import subprocess
            output = subprocess.check_output(
                ['ps', 'aux']
            )
            found = False
            for p in self.processes:
                if p in output:
                    found = True
                    break
            return found
        except Exception:
            return False

    def generate_health_report(self, host='localhost'):
        """
        Aggregates the results
        of all checks into a
        single health report dictionary.
        """
        port_status = self.check_port()
        process_status = self.check_processes()
        banner_info = self.check_banner(host)

        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'server': self.server_name,
            'host': host,
            'port': self.port,
            'port_open': port_status,
            'process_running': process_status,
            'banner_check': banner_info
        }

        return report


def main():
    parser = OptionParser()
    parser.add_option(
        '--host', dest='host',
        default='127.0.0.1',
        help='SMTP server host'
    )
    parser.add_option(
        '--port', dest='port',
        type='int', default=25,
        help='SMTP port'
    )
    parser.add_option(
        '--controller-url',
        dest='controller_url',
        help='Controller URL'
    )
    parser.add_option(
        '--processes', dest='processes',
        help='Comma-separated list of processes'
    )

    (options, args) = parser.parse_args()

    # convert process string to list
    processes = options.processes.split(',') if options.processes else None

    # initialize agent with parsed options
    agent = SMTPAgent(
        port=options.port,
        processes=processes,
        controller_url=options.controller_url
    )

    # generate & print health report
    report = agent.generate_health_report(host=options.host)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
