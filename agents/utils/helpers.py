import logging

import ConfigParser

from .logtools import maybe_log_message


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
    try:
        value = config.get(section, option)

        if cast:
            try:
                value = cast(value)
            except (TypeError, ValueError) as e:
                maybe_log_message(
                    (
                        'Could not cast option value '
                        '%s due to error: %s' % (value, str(e))
                    ),
                    logger,
                    fallback_logger=fallback_logger,
                )
                return value

    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
        if logger:
            maybe_log_message(
                'Config not found [%s] %s: %s' % (section, option, str(e)),
                logger,
                fallback_logger=fallback_logger,
                level=logging.WARNING,
            )
    return value or default
