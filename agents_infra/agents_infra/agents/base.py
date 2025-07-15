import abc
import inspect
import json
import logging
import logging.config
import re
import socket
import subprocess
import time
import warnings
from collections import Sequence

import ConfigParser
import pkg_resources
import psutil
import Queue
import urllib2
from urlparse import urljoin

from ..command import CommandHistory, CommandStatus, dispatch_command
from ..exceptions import BadProcessReturnCode
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


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """

    __metaclass__ = abc.ABCMeta

    _plugins = None

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

        # Server identity refers to data necessary for connectivity to
        # controller, i.e., hostname and IP address.
        self.evaluate_identity()

        # Thread-safe queue to store pending commands. If maxsize <= 0,
        # the queue is treated as 'infinite'.
        self.command_queue = Queue.Queue(maxsize=max(command_queue_size, 0))

        # Initialize tags
        self.tags = {}

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

    def aggregate_reports(self, category=None):
        """
        Aggregate reports for a given category.

        Parameters:
            category (str, optional): Report category.
        """
        report_data = {'server_name': self.server_name}

        # Update report with server's identity data.
        if category == 'status':
            report_data.update({'hostname': self.hostname, 'ip': self.ip})

        if self._plugins:
            for name, plugin in self._plugins.items():
                if plugin.enabled and (
                    category is None or plugin.category == category
                ):
                    try:
                        report_data[name] = plugin(self)
                    except Exception as e:
                        maybe_log_message(
                            'Plugin %s failed due to error: %s' % (
                                name, str(e)
                            ),
                            logger=self.logger,
                            exc_info=True,
                        )

        return report_data

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

            # Read tags from the [server] section
            tags = {}
            for tag_key in ['env', 'role', 'region']:
                tag_value = get_config_option(
                    config,
                    'server',
                    tag_key,
                    logger=self.logger,
                )
                if tag_value and tag_value.strip():
                    tags[tag_key] = tag_value.strip().lower()
            if tags:
                self.tags = tags

    def evaluate_identity(self):
        """
        Attempt setting server identity which includes the hostname and
        IP address.
        """
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
    def is_service_healthy(self, timeout=2, payload=None, packet_size=0):
        """
        Check if the specific service (SMTP, DNS, etc.) is running and
        healthy.
        """
        if self.port < 0 or self.ip is None or self.protocol is None:
            return False

        port_status = False

        try:
            with warnings.catch_warnings(record=True) as records:
                # Check port status via plugin.
                port_status = self.check_port(
                    timeout=timeout, payload=payload, packet_size=packet_size
                )['port_open']

                for record in records:
                    maybe_log_message(
                        (
                            'Warning while checking port status: %s'
                            % record.message
                        ),
                        logger=self.logger,
                        level=logging.WARNING,
                    )
        except (socket.error, socket.timeout) as e:
            maybe_log_message(
                'Port check failed due to error: %s' % str(e),
                logger=self.logger,
            )

        return (
            port_status
            and self._is_process_running()
            and self.is_ssh_service_active()
        )

    @abc.abstractmethod
    def maybe_restart_service(self):
        pass

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
        if not isinstance(data, dict):
            maybe_log_message(
                'Expected data as a dict, got %s' % type(data),
                logger=self.logger,
            )

            return

        try:
            command_history = CommandHistory.from_dict(data)
        except (TypeError, ValueError) as e:
            maybe_log_message(
                'Command validation failed due to error: %s' % str(e),
                logger=self.logger,
            )

            return

        if command_history.command.tag in self.whitelist_commands:
            try:
                self.command_queue.put(
                    command_history, block=block, timeout=timeout
                )
            except Queue.Full:
                maybe_log_message(
                    'Queue is full - could not append command',
                    logger=self.logger,
                )
        else:
            maybe_log_message(
                'Command %s not permitted' % command_history.command.tag,
                logger=self.logger,
                level=logging.WARNING,
            )

    def get_command_from_queue(self, block=False, timeout=None):
        try:
            return self.command_queue.get(block=block, timeout=timeout)
        except Queue.Empty:
            maybe_log_message(
                'Queue is empty - could not retrieve command',
                logger=self.logger,
            )

    def execute_command(self, **kwargs):
        """
        Pull command from the queue and delegate execution to
        CommandDispatcher.
        """
        command_history = self.get_command_from_queue(**kwargs)

        if command_history:
            try:
                result = dispatch_command(command_history.command, self)

                command_history.status = CommandStatus.DONE
            except BadProcessReturnCode as e:
                maybe_log_message(
                    'Command failed due to error: %s.\nstderr: %s' % (
                        str(e), result
                    ),
                    logger=self.logger,
                )

                command_history.status = CommandStatus.FAILED

            command_history.result = result

            return command_history
