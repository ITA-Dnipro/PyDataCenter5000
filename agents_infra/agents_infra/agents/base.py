import abc
import datetime
import json
import logging
import logging.config
import os
import platform
import re
import socket
import subprocess
import sys
import time
from collections import Sequence

import attr
import ConfigParser
import pkg_resources
import psutil
import Queue
import urllib2
from dateutil import parser
from urlparse import urljoin

from ..managers.health_server_manager import HealthServerManager
from ..utils import LOG_CONFIG_PATH, maybe_log_message
from ..utils.configtools import get_config_option, parse_csv_list

PROTOCOLS = ('tcp', 'udp')


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


@attr.s
class CommandHistory(object):
    """Helper class used to validate command fields."""
    command = attr.ib(validator=attr.validators.instance_of(basestring))
    hostname = attr.ib(validator=attr.validators.instance_of(basestring))
    status = attr.ib(validator=attr.validators.instance_of(basestring))
    timestamp = attr.ib(
        validator=lambda instance, attribute, value: parser.parse(value)
    )
    result = attr.ib(default=None)
    id = attr.ib(default=None)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """

    __metaclass__ = abc.ABCMeta

    controller_url = None
    api_prefix = 'api/'
    auth_token_type = 'Bearer'
    whitelist_commands = None
    critical_processes = None

    def __init__(
        self,
        server_name=None,
        port=None,
        health_port=8081,
        processes=None,
        critical_processes=None,
        interface=None,
        protocol=None,
        whitelist_commands=None,
        command_queue_size=0,
    ):
        self.health_thread = None
        self.server_name = server_name
        self.port = port if port is not None else self.port
        self.health_port = (
            health_port
            if health_port is not None
            else self.health_port
        )
        self.processes = processes if processes is not None else self.processes
        self.interface = interface

        if protocol is not None:
            self.protocol = protocol

        if self.whitelist_commands is None:
            self.whitelist_commands = []

        if whitelist_commands is not None:
            self.whitelist_commands.extend(whitelist_commands)

        # Extend the list of global critical processes with those that
        # are server-specific.
        self.critical_processes = self.critical_processes or []
        if critical_processes is not None:
            self.critical_processes.extend(critical_processes)

        # Init server metadata to prevent AttributeError and to indicate
        # to user that collect_server_metadata hasn't been called.
        self.os_type = self.hostname = self.ip = None
        self.uptime = self.timestamp = None

        # Thread-safe queue to store pending commands.
        self.queue = Queue.Queue(maxsize=max(command_queue_size, 0))

    @classmethod
    def from_config_file(cls, filename=None, log_path=None):
        """
        Create an agent from a configuration (.ini) file.

        Parameters:
            filename (str): Path to configuration file. Default is None.
            log_path (str): Path to where the log files will be stored.
                Default is None.

        Returns:
            ServerAgent: Child instance of ServerAgent.
        """
        agent = cls()

        agent._parse_config_file(filename)
        agent.setup_logging(log_path)

        return agent

    def setup_logging(self, log_path=None):
        """
        Setup agent's logger based on its server_name.

        Parameters:
            log_path (PathLike, optional): Path to where logs will be
                stored.
        """
        log_path = (
            log_path or pkg_resources.
            resource_filename(
                self.__class__.__module__, 'logs/%s.log' % self.server_name
            )
        )

        logging.config.fileConfig(
            LOG_CONFIG_PATH,
            defaults={
                'agent_name': self.server_name,
                'log_path': log_path
            },
        )

    @property
    def logger(self):
        if not self.server_name:
            raise ValueError('Must assign a valid server name to use logger')

        return logging.getLogger(self.server_name)

    @property
    def port(self):
        return getattr(self, '_port', -1)

    @port.setter
    def port(self, value):
        if not isinstance(value, int):
            raise TypeError('Port number must be an integer')
        self._port = value

    @property
    def health_port(self):
        return getattr(self, '_health_port', 8081)

    @health_port.setter
    def health_port(self, value):
        if not isinstance(value, int):
            raise TypeError('Health port must be an integer')
        self._health_port = value

    @property
    def processes(self):
        return getattr(self, '_processes', [])

    @processes.setter
    def processes(self, value):
        if not isinstance(value, Sequence):
            raise TypeError(
                (
                    'Process names must be provided as a string or a sequence '
                    '(list, tuple etc.), not %s' % type(value)
                )
            )
        self._processes = value

    @property
    def protocol(self):
        return getattr(self, '_protocol', None)

    @protocol.setter
    def protocol(self, value):
        if not isinstance(value, (str, unicode)):
            raise TypeError('Protocol must be a string, not %s' % type(value))

        value = value.lower()

        if value not in PROTOCOLS:
            raise ValueError('Unknown protocol value %s' % value)

        self._protocol = value

    def _parse_config_file(self, filename=None):
        """Parse server's config file using ConfigParser."""
        filename = filename or pkg_resources.resource_filename(
            self.__class__.__module__, 'config.ini'
        )

        config = ConfigParser.ConfigParser()
        config.read(filename)

        if config.sections():
            self.server_name = get_config_option(
                config,
                'server',
                'name',
                default=self.server_name,
                logger=self.logger,
            )

            self.port = get_config_option(
                config,
                'server',
                'port',
                default=self.port,
                logger=self.logger,
                cast=int,
            )

            self.processes = get_config_option(
                config,
                'server',
                'processes',
                default=self.processes,
                logger=self.logger,
                cast=parse_csv_list,
            )

            # Append server-specific critical_processes
            critical_processes = get_config_option(
                config,
                'server',
                'critical_processes',
                logger=self.logger,
                cast=parse_csv_list,
            )

            # Extend avoiding duplicates
            if critical_processes:
                self.critical_processes.extend(
                    proc for proc in critical_processes
                    if proc not in self.critical_processes
                )

            self.interface = get_config_option(
                config, 'server', 'interface', logger=self.logger
            )

            whitelist_commands = get_config_option(
                config,
                'controller',
                'whitelist_commands',
                logger=self.logger,
                cast=parse_csv_list,
            )
            # Add commands to the list of globally allowed commands.
            if whitelist_commands:
                self.whitelist_commands.extend(
                    cmd for cmd in whitelist_commands
                    if cmd not in self.whitelist_commands
                )

    def collect_server_metadata(self):
        """
        Attempt setting server metadata such as the hostname, IP address,
        uptime, and timestamp.
        """
        system = platform.system()
        if not system:
            maybe_log_message('Could not deduce OS type', logger=self.logger)

        self.os_type = system.lower() or 'unknown'

        try:
            self.hostname = socket.gethostname()
        except socket.error as e:
            self.hostname = 'unknown'

            maybe_log_message(
                'Could not get hostname: %s' % str(e), logger=self.logger
            )

        self.ip = None

        if self.interface:
            try:
                self.ip = get_ip_from_interface(self.interface)
            except (KeyError, AttributeError) as e:
                maybe_log_message(
                    (
                        'Could not deduce IP address from interface '
                        '%s: %s' % (self.interface, str(e))
                    ),
                    logger=self.logger,
                )

        if not self.ip and self.hostname != 'UNKNOWN':
            try:
                self.ip = socket.gethostbyname(self.hostname)
            except (socket.gaierror, socket.error) as e:
                maybe_log_message(
                    'Could not deduce IP address from hostname: %s' % str(e),
                    self.logger,
                )

        self.uptime = -1

        if 'linux' in self.os_type:
            self.uptime = get_linux_uptime()

        if self.uptime < 0:
            maybe_log_message(
                "Could not get system's uptime", logger=self.logger
            )

        self.timestamp = datetime.datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S'
        )

    def is_port_open(self, timeout=2, payload=None, packet_size=0):
        """
        Check if the port is open.

        Returns:
            bool: Port status.

        Raises:
            ValueError: If the port not assigned a valid number.
        """
        if self.port == -1:
            raise ValueError(
                'Port not set: server agent must assign a valid port number'
            )

        if not self.ip:
            return False

        if not self.protocol:
            raise ValueError(
                'Protocol not set: server agent must set a valid transfer '
                'protocol (TCP or UDP)'
            )

        s = socket.socket(
            socket.AF_INET,
            (
                socket.SOCK_STREAM if self.protocol == 'tcp'
                else socket.SOCK_DGRAM
            ),
        )
        s.settimeout(timeout)

        try:
            if self.protocol == 'tcp':
                s.connect((self.ip, self.port))
            else:
                s.sendto(payload or b'', (self.ip, self.port))

            if packet_size > 0:
                data, _ = s.recvfrom(packet_size)
                if len(data) != packet_size:
                    maybe_log_message(
                        (
                            'UDP response size mismatch: expected '
                            '%d bytes, got %d bytes' % (packet_size, len(data))
                        ),
                        logger=self.logger,
                    )

                    return False

            return True
        except (socket.error, socket.timeout) as e:
            maybe_log_message(
                'Port check failed due to error: %s' % str(e),
                logger=self.logger,
            )

            return False
        finally:
            s.close()

    def _is_process_running(self):
        try:
            output = subprocess.Popen(['ps', '-eo', 'comm'],
                                      stdout=subprocess.PIPE).communicate()[0]

            if hasattr(output, 'decode'):
                output = output.decode('utf-8')

            normalized_lines = output.lower().splitlines()

            return any(
                re.search(r'\b{0}\b'.format(re.escape(proc)), line)
                for proc in self.processes
                for line in normalized_lines
                )

        except OSError as e:
            maybe_log_message(
                'Process check failed: %s' % e,
                logger=self.logger,
                exc_info=True,
            )

            return False

    def is_ssh_service_active(self):
        try:
            proc = subprocess.Popen(
                ['systemctl', 'is-active', 'ssh'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate()

            if hasattr(stdout, 'decode'):
                stdout = stdout.decode('utf-8')

            stdout = stdout.strip().lower()

            return stdout == 'active'

        except OSError as e:
            maybe_log_message(
                'SSH service check failed: %s' % e, self.logger, exc_info=True
            )
            return False

    @abc.abstractmethod
    def is_service_healthy(self):
        """
        Check if the specific service (SMTP, DNS, etc.) is running and
        healthy.
        """
        return self._is_process_running() and self.is_ssh_service_active()

    @abc.abstractmethod
    def maybe_restart_service(self):
        pass

    def status_to_dict(self):
        return {
            'os': self.os_type,
            'hostname': self.hostname,
            'ip': self.ip,
            'server_name': self.server_name,
            'uptime': self.uptime,
            'timestamp': self.timestamp,
            'healthy': self.is_service_healthy(),
        }

    def status_to_json(self, log=False):
        """
        Dump host metadata to json file.

        Parameters:
            log (bool): Whether to log JSON status string to the logfile.
                Default is False.

        Returns:
            str: JSON status string.
        """
        try:
            status = json.dumps(self.status_to_dict(), default=str)

            if log:
                try:
                    self.logger.info(status)
                except (IOError, OSError) as e:
                    maybe_log_message(
                        'Error logging to file: %s' % str(e),
                        logger=self.logger,
                    )

            return status
        except TypeError as e:
            maybe_log_message(
                ('JSON serialization of status failed '
                 'due to error: %s' % str(e)),
                logger=self.logger,
            )

    def status_to_txt(self):
        """Dump host metadata to txt file as key-value pairs."""
        data = self.status_to_dict()

        try:
            for k, v in data.items():
                self.logger.info(u'%s: %s' % (k, v))
        except (IOError, OSError) as e:
            maybe_log_message(
                'Error logging to file: %s' % str(e), logger=self.logger
            )

    def post_data(
        self,
        url,
        payload,
        to_controller=True,
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
        fail_silently=True,
        **kwargs
    ):
        """
        Sends a POST request with JSON data to the specified URL with
        retry logic. Retries up to `max_retries` times with `delay`
        seconds between attempts. Logs all attempts and failures.

        Parameters:
            url (str): Endpoint URL or, for `to_controller=True`,
                suffix of controller's endpoint, i.e.,
                <controller_url>/<api_prefix>/url.
            payload (Any): Data to send via POST request. If not a string,
                JSON serialization will be attempted.
            api_key (str, optiona): API key for authorization. Default
                is None.
            max_retries (int, optional): Maximum number of retry attempts.
                Default is 3.
            delay (int, optional): Delay (in seconds) between retries.
                Default is 5.
            timeout (int, optional): POST request timeout (in seconds).
                Default is 5.
            to_controller (bool, optional): Whether data is to be sent
                to controller. Default is False.
            **kwargs: Key-value pairs to be appended to the header.
        """
        if to_controller:
            if not self.controller_url:
                maybe_log_message(
                    (
                        "Couldn't send POST request to controller: "
                        'controller URL is not set'
                    ),
                    logger=self.logger,
                )
                return

            base_api_url = urljoin(self.controller_url, self.api_prefix)
            url = urljoin(base_api_url, url)

        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers.update(
                {'Authorization': '%s %s' % (self.auth_token_type, api_key)}
            )
        if kwargs:
            headers.update(kwargs)

        if not isinstance(payload, str):
            payload = json.dumps(payload)

        for attempt in range(1, max_retries + 1):
            try:
                maybe_log_message(
                    '[Attempt %d] Sending data to %s' % (attempt, url),
                    logger=self.logger,
                    level=logging.INFO
                )

                request = urllib2.Request(url, data=payload, headers=headers)

                response = urllib2.urlopen(request, timeout=timeout)
                result = response.read()
                status_code = response.getcode()

                maybe_log_message(
                    'POST request status: %d' % status_code,
                    logger=self.logger,
                    level=logging.INFO
                )

                response.close()

                maybe_log_message(
                    'POST request succeeded on attempt %d: %s' % (
                        attempt, result
                    ),
                    logger=self.logger,
                    level=logging.INFO,
                )

                return result
            except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
                maybe_log_message(
                    'Attempt %d failed: %s' % (attempt, e),
                    logger=self.logger,
                    level=logging.ERROR,
                )

                if attempt < max_retries:
                    maybe_log_message(
                        'Retrying in %d seconds...' % delay,
                        logger=self.logger,
                        level=logging.WARNING,
                    )
                    time.sleep(delay * attempt)
                else:
                    maybe_log_message(
                        'All %d attempts failed. Data not sent. '
                        'Last error: %s' % (max_retries, e),
                        logger=self.logger,
                        level=logging.CRITICAL,
                    )

                    if not fail_silently:
                        raise RuntimeError(
                            'POST failed after %d attempts' % max_retries
                        )

    def fetch_command_from_controller(
        self, suffix='command/fetch/', timeout=5, api_key=None, **kwargs
    ):
        """
        Send GET request to controller to fetch the first pending
        command for a given server.
        """
        if not self.controller_url or not self.hostname:
            maybe_log_message(
                (
                    "Couldn't fetch controller command: controller URL or "
                    'hostname not set'
                ),
                logger=self.logger,
            )
            return

        base_api_url = urljoin(self.controller_url, self.api_prefix)
        fetch_api_url = urljoin(base_api_url, suffix)
        url = '%s?hostname=%s' % (fetch_api_url, self.hostname)

        headers = {'Accept': 'application/json'}
        if api_key:
            headers.update(
                {'Authorization': '%s %s' % (self.auth_token_type, api_key)}
            )
        if kwargs:
            headers.update(kwargs)

        request = urllib2.Request(url, headers=headers)

        try:
            response = urllib2.urlopen(request, timeout=timeout)

            data = response.read()
            response.close()

            status_code = response.getcode()

            maybe_log_message(
                (
                    'GET request to controller succeded with '
                    'status: %s' % status_code
                ),
                logger=self.logger,
                level=logging.INFO,
            )

            if status_code == 204 or not data.strip():
                maybe_log_message(
                    'No pending commands for server %s' % self.hostname,
                    logger=self.logger,
                    level=logging.INFO,
                )

                return

            data = json.loads(data)

            return data
        except (urllib2.HTTPError, urllib2.URLError, socket.timeout) as e:
            maybe_log_message(
                (
                    'Failed to fetch command - GET request failed '
                    'due to error: %s' % str(e)
                ),
                logger=self.logger,
                exc_info=True,
            )
        except Exception as e:
            maybe_log_message(
                'GET request failed due to unexpected error: %s' % str(e),
                logger=self.logger,
                exc_info=True,
            )

    def maybe_add_command_to_queue(self, data, block=False, timeout=None):
        """
        Add command to queue if it passes field validation and if
        whitelisted by the server.
        """
        if not isinstance(data, CommandHistory):
            try:
                data = CommandHistory.from_dict(data)
            except (TypeError, ValueError) as e:
                maybe_log_message(
                    'Command validation failed due to error: %s' % str(e),
                    logger=self.logger,
                )

                return

        if data.command in self.whitelist_commands:
            try:
                self.queue.put(data, block=block, timeout=timeout)
            except Queue.Full:
                maybe_log_message(
                    'Queue is full - could not append command',
                    logger=self.logger,
                )

    def get_command_from_queue(self, block=False, timeout=None):
        try:
            return self.queue.get(block=block, timeout=timeout)
        except Queue.Empty:
            maybe_log_message(
                'Queue is empty - could not retrieve command',
                logger=self.logger,
            )

    def get_cpu_usage(self, interval=60):
        """
        Get the average CPU usage percentage over the last minute.
        """
        try:
            return psutil.cpu_percent(interval=interval)
        except (psutil.Error, ValueError) as e:
            maybe_log_message(
                'Error getting CPU usage: %s' % str(e), logger=self.logger
            )
            return -1.0

    def get_ram_usage(self):
        """
        Get the current RAM usage percentage.
        """
        try:
            mem = psutil.virtual_memory()
            return mem.percent
        except psutil.Error as e:
            maybe_log_message(
                'Error getting RAM usage: %s' % str(e), logger=self.logger
            )
            return -1.0

    def get_load_average(self):
        """
        Get the system load average over the last 1 minute.
        """
        try:
            return os.getloadavg()[0]
        except (OSError, AttributeError) as e:
            maybe_log_message(
                'Error getting load average: %s' % str(e), logger=self.logger
            )
            return -1.0

    def get_disk_usage(self):
        """
        Get the current disk usage percentage for the root filesystem.
        """
        try:
            usage = psutil.disk_usage('/')
            return usage.percent
        except psutil.Error as e:
            maybe_log_message(
                'Error getting disk usage: %s' % str(e), logger=self.logger
            )
            return -1.0

    def generate_report(self):
        """
        Generate a report containing server resource usage.
        """
        return {
            'cpu': self.get_cpu_usage(),
            'ram': self.get_ram_usage(),
            'disk': self.get_disk_usage(),
            'load_avg': self.get_load_average(),
            'timestamp': datetime.datetime.now().isoformat(),
        }
