import codecs
import logging
import os
import sys

import attr
import ConfigParser
import pkg_resources

from .logtools import maybe_log_message

DEFAULT_API_PREFIX = 'api/'
DEFAULT_AUTH_TOKEN_TYPE = 'Bearer'
DEFAULT_INTERFACE = 'enp0s3'


def load_global_config():
    """Attempt loading agents global config file at agents_infra/global.ini."""
    config = ConfigParser.ConfigParser()
    files = config.read(
        pkg_resources.resource_filename('agents_infra', 'global.ini')
    )

    if not files:
        sys.stderr.write(
            '[WARN] Global config file not found - '
            'falling back to default values'
        )

    if config.sections():
        return config


def parse_csv_list(value):
    """Parse a comma-separated string into a list of strings."""
    if not isinstance(value, (str, unicode)):
        raise TypeError('Expected a string as input, got %s' % type(value))

    if not value:
        return []

    return [elem.strip() for elem in value.split(',')]


def get_config_option(
    config,
    section,
    option,
    default=None,
    logger=None,
    fallback_logger=None,
    cast=None,
):
    """
    Helper function to get a config option from a config parser falling
    back to a default value if data not found. If NoSectionError or
    NoOptionError arises and a logger is provided, logging is attempted.

    Parameters:
        config (ConfigParser.ConfigParser): Config parser.
        section (str): Section name.
        option (str): Option name.
        default (Any): Fallback value. Default is None.
        logger (logging.Logger): Primary logger. Default is None (no logging).
        fallback_logger (logging.Logger): Fallback logger. Default is
            None.
        cast (Callable): Callable to convert the option value to a required
            type or form. For example, use `int` for integers and `float`
            for floats. To implement custom logic, a lambda-function
            should be passed. On cast failure or if cast function is not
            provided, the original string returned by ConfigParser will
            be returned. Default is None.

    Returns:
        Any: Option value.

    Notes:
        Note that by default, section names are case-sensitive, whereas
        option-names are case-insensitive.
    """
    option_value = None
    try:
        option_value = config.get(section, option)

        if cast:
            try:
                option_value = cast(option_value)
            except (TypeError, ValueError) as e:
                maybe_log_message(
                    (
                        'Could not cast option value '
                        '%s due to error: %s' % (option_value, str(e))
                    ),
                    logger,
                    fallback_logger=fallback_logger,
                )
        return option_value

    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
        if logger:
            maybe_log_message(
                'Config not found [%s] %s: %s' % (section, option, str(e)),
                logger,
                fallback_logger=fallback_logger,
                level=logging.WARNING,
            )

    return default


class Config(object):
    def __init__(
        self,
        name='',
        api_prefix=DEFAULT_API_PREFIX,
        url='',
        critical_processes=None,
        whitelist_commands=None,
        port=-1,
        health_port=None,
        auth_token_type=DEFAULT_AUTH_TOKEN_TYPE,
        interface=DEFAULT_INTERFACE,
        post_agent_log_url=None,
        send_logs_to_controller=False,
        env=None,
        role=None,
        region=None,
        **kwargs
    ):
        self.name = name

        self.api_prefix = api_prefix
        self.url = url

        self.critical_processes = (
            critical_processes if critical_processes is not None else []
        )
        self.whitelist_commands = (
            whitelist_commands if whitelist_commands is not None else []
        )

        self.port = port
        self.health_port = health_port
        self.auth_token_type = auth_token_type
        self.interface = interface
        self.post_agent_log_url = post_agent_log_url
        self.send_logs_to_controller = send_logs_to_controller

        self.env = env
        self.role = role
        self.region = region

        # For additional fields
        for key, value in kwargs.items():
            setattr(self, key, value)

    # -------------------- VALIDATION --------------------

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, basestring):
            raise TypeError('name must be a string')
        self._name = value

    @property
    def api_prefix(self):
        return self._api_prefix

    @api_prefix.setter
    def api_prefix(self, value):
        if not isinstance(value, basestring):
            raise TypeError('api_prefix must be a string')
        self._api_prefix = value

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        if not isinstance(value, basestring):
            raise TypeError('url must be a string')
        self._url = value

    @property
    def critical_processes(self):
        return self._critical_processes

    @critical_processes.setter
    def critical_processes(self, value):
        if not isinstance(value, list):
            raise TypeError('critical_processes must be a list')
        self._critical_processes = list(value)  # <- copy

    @property
    def whitelist_commands(self):
        return self._whitelist_commands

    @whitelist_commands.setter
    def whitelist_commands(self, value):
        if not isinstance(value, list):
            raise TypeError('whitelist_commands must be a list')
        self._whitelist_commands = list(value)  # <- copy

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, value):
        if not isinstance(value, int):
            raise TypeError('port must be an integer')
        self._port = value

    @property
    def health_port(self):
        return self._health_port

    @health_port.setter
    def health_port(self, value):
        if value is not None and not isinstance(value, int):
            raise TypeError('health_port must be an integer or None')
        self._health_port = value

    @property
    def auth_token_type(self):
        return self._auth_token_type

    @auth_token_type.setter
    def auth_token_type(self, value):
        if value is not None and not isinstance(value, basestring):
            raise TypeError('auth_token_type must be a string or None')
        self._auth_token_type = value

    @property
    def interface(self):
        return self._interface

    @interface.setter
    def interface(self, value):
        if value is not None and not isinstance(value, basestring):
            raise TypeError('interface must be a string or None')
        self._interface = value

    @property
    def post_agent_log_url(self):
        return self._post_agent_log_url

    @post_agent_log_url.setter
    def post_agent_log_url(self, value):
        if value is not None and not isinstance(value, basestring):
            raise TypeError('post_agent_log_url must be a string or None')
        self._post_agent_log_url = value

    @property
    def send_logs_to_controller(self):
        return self._send_logs_to_controller

    @send_logs_to_controller.setter
    def send_logs_to_controller(self, value):
        if not isinstance(value, bool):
            raise TypeError('send_logs_to_controller must be a boolean')
        self._send_logs_to_controller = value

    # --------------- FACTORY METHOD ------------------

    @classmethod
    def from_dict(cls, params):
        return cls(**params)

    # --------------- UTILS --------------------------

    def get(self, key, default=None):
        return getattr(self, key, default)

    def update(self, updates):
        if isinstance(updates, Config):
            updates = updates.__dict__
        elif not isinstance(updates, dict):
            raise TypeError('Expected dict or Config instance')

        for key, value in updates.items():
            current = getattr(self, key, None)

            # Handle pre-existing global configurations (extend or override)
            if isinstance(current, list):
                if isinstance(value, list):
                    current.extend([v for v in value if v not in current])
                else:
                    if value not in current:
                        current.append(value)
            else:
                setattr(self, key, value)


def parse_config_file(filename=None):
    """
    Generic utility function to parse a given config file.

    Args:
        filename (str): path to config.ini file.

    Returns:
        (Config, dict): config object and tags dict.
    """

    config_files = [
        filename or pkg_resources.resource_filename(__name__, 'config.ini')
    ]

    parser = ConfigParser.ConfigParser()
    parser.read(config_files)

    config = {}
    tags = {}

    config['path'] = filename

    for section in parser.sections():
        for key, value in parser.items(section):
            value = value.strip()

            # Simple explicit type handling
            if key == 'port':
                value = int(value)
            elif key in ('critical_processes', 'whitelist_commands'):
                value = parse_csv_list(value)
            elif key == 'health_port':
                value = int(value)

            if section == 'server' and key in ('env', 'role', 'region'):
                if value and isinstance(value, basestring) and value.strip():
                    tags[key] = value.strip().lower()
            else:
                config[key] = value

    return Config.from_dict(config), tags


def write_config_options(config_path, section, options_to_update):
    """
    Atomically updates or removes options in a given section of a .ini file.
    - If a value is an empty string or None, the option is removed.
    - Otherwise, the option is set.
    """
    config = ConfigParser.ConfigParser()
    config.read(config_path)

    if not config.has_section(section):
        config.add_section(section)

    for key, value in options_to_update.items():
        if value not in ('', None):
            config.set(section, key, str(value))
        elif config.has_option(section, key):
            config.remove_option(section, key)

    temp_path = config_path + '.tmp'
    with codecs.open(temp_path, 'w', encoding='utf-8') as temp_configfile:
        config.write(temp_configfile)
    os.rename(temp_path, config_path)
