import logging

import ConfigParser

from .logtools import maybe_log_message


def get_config_option(
    config, section, option, default=None, logger=None, fallback_logger=None
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

    Returns:
        Any: Option value.
    """
    try:
        return config.get(section, option)
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
        if logger:
            maybe_log_message(
                'Config not found [%s] %s: %s' % (section, option, str(e)),
                logger,
                fallback_logger=fallback_logger,
                level=logging.WARNING,
            )
    return default
