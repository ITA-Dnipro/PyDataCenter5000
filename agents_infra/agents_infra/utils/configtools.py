import codecs
import logging
import os
import sys

import ConfigParser
import pkg_resources

from .logtools import maybe_log_message


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
