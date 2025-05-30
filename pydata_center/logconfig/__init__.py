import logging
import logging.config
import os


def setup_logging():
    config_path = os.path.join(os.path.dirname(__file__), 'logging.conf')
    logging.config.fileConfig(config_path, disable_existing_loggers=False)
