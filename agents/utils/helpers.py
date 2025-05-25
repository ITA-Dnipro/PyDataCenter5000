import logging

import ConfigParser

from .logtools import maybe_log_message


def get_config_option(
    config, section, option, default=None, logger=None, fallback_logger=None
):
    try:
        return config.get(section, option)
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
        maybe_log_message(
            'Config not found [%s] %s: %s' % (section, option, str(e)),
            logger,
            fallback_logger=fallback_logger,
            level=logging.WARNING,
        )
    return default
