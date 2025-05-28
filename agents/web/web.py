import os

import pkg_resources

from ..agent import ServerAgent


class WebAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_dir = pkg_resources.resource_filename(__name__, 'logs')
    server_name = 'web'

    def __init__(self, web_processes=None):
        super(WebAgent, self).__init__()

        if 'PORT' not in os.environ:
            raise ValueError('WEB port environment variable is not set.')

        self.port = int(os.environ['PORT'])
        self.processes = web_processes or [
            'uvicorn',
        ]
